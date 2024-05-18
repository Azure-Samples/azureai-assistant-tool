# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.text_message import TextMessage, FileCitation
from azure.ai.assistant.management.logger_module import logger

from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.beta.threads import (
    ImageFileContentBlock,
    ImageURLContentBlock,
    TextContentBlock,
    Message,
    FileCitationAnnotation, 
    FilePathAnnotation
)

from typing import Union, Optional, List, Tuple
from PIL import Image
import os, io, asyncio


class AsyncConversationMessage:
    def __init__(self):
        self._ai_client : Union[AsyncOpenAI, AsyncAzureOpenAI] = None
        self._original_message = None
        self._text_message = None
        self._file_message = None
        self._image_message = None
        self._role = None
        self._sender = None
        self._assistant_config_manager = None

    @classmethod
    async def create(cls, ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI], original_message: Message):
        instance = cls()
        instance._ai_client = ai_client
        instance._original_message = original_message
        instance._role = original_message.role
        instance._assistant_config_manager = AssistantConfigManager.get_instance()
        instance._sender = instance._get_sender_name(original_message)
        await instance._process_message_contents(original_message)
        return instance

    async def _process_message_contents(self, original_message: Message):
        for content_item in original_message.content:
            if isinstance(content_item, TextContentBlock):
                citations, file_citations = await self._process_text_annotations(content_item)
                content_value = content_item.text.value
                if citations:
                    content_value += '\n' + '\n'.join(citations)
                self._text_message = TextMessage(content_value, file_citations)
            elif isinstance(content_item, ImageFileContentBlock):
                self._image_message = await AsyncImageMessage.create(
                    self._ai_client, content_item.image_file.file_id, f"{content_item.image_file.file_id}.png"
                )

    def _get_sender_name(self, message: Message) -> str:
        if message.role == "assistant":
            sender_name = self._assistant_config_manager.get_assistant_name_by_assistant_id(message.assistant_id)
            return sender_name if sender_name else "assistant"
        elif message.role == "user":
            if message.metadata:
                sender_name = message.metadata.get("chat_assistant", "assistant")
                self._role = "assistant"
            else:
                sender_name = "user"
            return sender_name

    async def _process_text_annotations(self, content_item: TextContentBlock) -> Tuple[List[str], List[FileCitation]]:
        citations = []
        file_citations = []

        if content_item.text.annotations:
            for index, annotation in enumerate(content_item.text.annotations):
                content_item.text.value = content_item.text.value.replace(annotation.text, f' [{index}]')

                if isinstance(annotation, FilePathAnnotation):
                    file_id = annotation.file_path.file_id
                    file_name = annotation.text.split("/")[-1]
                    self._file_message = await AsyncFileMessage.create(self._ai_client, file_id, file_name)
                    citations.append(f'[{index}] {file_name}')
                    file_citations.append(FileCitation(file_id, file_name))

                elif isinstance(annotation, FileCitationAnnotation):
                    try:
                        file_id = annotation.file_citation.file_id
                        file_info = await self._ai_client.files.retrieve(file_id)
                        file_name = file_info.filename
                    except Exception as e:
                        logger.error(f"Failed to retrieve filename for file_id {file_id}: {e}")
                        file_name = "Unknown_" + str(file_id)
                    citations.append(f'[{index}] {file_name}')
                    file_citations.append(FileCitation(file_id, file_name))

        return citations, file_citations

    @property
    def text_message(self) -> Optional[TextMessage]:
        return self._text_message

    @property
    def file_message(self) -> Optional['AsyncFileMessage']:
        return self._file_message

    @property
    def image_message(self) -> Optional['AsyncImageMessage']:
        return self._image_message

    @property
    def role(self) -> str:
        return self._role

    @property
    def sender(self) -> str:
        return self._sender

    @property
    def original_message(self) -> Message:
        return self._original_message


class AsyncFileMessage:
    def __init__(self, ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI], file_id: str, file_name: str):
        self._ai_client = ai_client
        self._file_id = file_id
        self._file_name = file_name

    @classmethod
    async def create(cls, ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI], file_id: str, file_name: str):
        instance = cls(ai_client, file_id, file_name)
        return instance

    @property
    def file_id(self) -> str:
        return self._file_id

    @property
    def file_name(self) -> str:
        return self._file_name

    async def retrieve_file(self, output_folder_name: str) -> str:
        logger.info(f"Retrieving file with file_id: {self.file_id} to path: {output_folder_name}")
        file_path = f"{output_folder_name}/{self.file_name}"
        if os.path.exists(file_path):
            logger.info(f"File already exists at {file_path}. Skipping download.")
            return file_path

        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            logger.info(f"Copying file with file_id: {self.file_id} to path: {file_path}")

            async with self._ai_client.files.content(self.file_id) as response:
                data = await response.read()
                await asyncio.to_thread(self._write_to_file, file_path, data)
            return file_path

        except Exception as e:
            logger.error(f"Failed to retrieve file {self.file_id}: {e}")
            return None
        
    @staticmethod
    def _write_to_file(file_path: str, data: bytes):
        """Write data to a file. This function is intended to run in a separate thread."""
        with open(file_path, 'wb') as file:
            file.write(data)


class AsyncImageMessage:
    def __init__(self, ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI], file_id: str, file_name: str):
        self._ai_client = ai_client
        self._file_id = file_id
        self._file_name = file_name

    @classmethod
    async def create(cls, ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI], file_id: str, file_name: str):
        instance = cls(ai_client, file_id, file_name)
        return instance

    @property
    def file_id(self) -> str:
        return self._file_id

    @property
    def file_name(self) -> str:
        return self._file_name

    async def retrieve_image(self, output_folder_name: str) -> str:
        """
        Asynchronously retrieve the image.

        :param output_folder_name: The name of the output folder.
        :type output_folder_name: str

        :return: The path of the retrieved image.
        :rtype: str
        """
        logger.info(f"Retrieving image with file_id: {self.file_id} to path: {output_folder_name}")
        file_path = os.path.join(output_folder_name, f"{self.file_id}.png")

        # Check if the file already exists
        if os.path.exists(file_path):
            logger.info(f"File already exists at {file_path}. Skipping download and resize.")
            return file_path

        # Ensure the output directory exists
        os.makedirs(output_folder_name, exist_ok=True)

        try:
            # Asynchronously get the image content
            async with self._ai_client.files.content(self.file_id) as response:
                image_data = await response.read()
                # Process and save the image in a separate thread
                file_path = await asyncio.to_thread(
                    self._save_and_resize_image, image_data, file_path
                )
                logger.info(f"Resized image saved to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Unexpected error during image processing {self.file_id}: {e}")
            return None

    @staticmethod
    def _save_and_resize_image(image_data: bytes, file_path: str, target_width: float = 0.5, target_height: float = 0.5) -> str:
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                new_width = int(img.width * target_width)
                new_height = int(img.height * target_height)
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                resized_img.save(file_path)
            return file_path
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return None
