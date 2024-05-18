# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.text_message import TextMessage, FileCitation
from azure.ai.assistant.management.logger_module import logger

from openai import AzureOpenAI, OpenAI
from openai.types.beta.threads import (
    ImageFileContentBlock,
    ImageURLContentBlock,
    TextContentBlock,
    Message,
    FileCitationAnnotation, 
    FilePathAnnotation
)

from typing import Union, Optional, List, Tuple
from PIL import Image, UnidentifiedImageError
import os, io


class ConversationMessage:
    def __init__(self, 
                 ai_client : Union[OpenAI, AzureOpenAI],
                 original_message: Message = None
    ):
        self._ai_client = ai_client
        self._original_message = original_message
        self._text_message = None
        self._file_message = None
        self._image_message = None
        self._role = original_message.role if original_message else "assistant"
        self._sender = None
        self._assistant_config_manager = AssistantConfigManager.get_instance()
        if original_message:
            self._sender = self._get_sender_name(original_message)
            self._process_message_contents(original_message)

    def _process_message_contents(self, original_message: Message):
        for content_item in original_message.content:
            if isinstance(content_item, TextContentBlock):
                citations, file_citations = self._process_text_annotations(content_item)
                content_value = content_item.text.value
                if citations:
                    content_value += '\n' + '\n'.join(citations)
                self._text_message = TextMessage(content_value, file_citations)

            elif isinstance(content_item, ImageFileContentBlock):
                self._image_message = ImageMessage(self._ai_client, content_item.image_file.file_id, f"{content_item.image_file.file_id}.png")

    def _get_sender_name(self, message: Message) -> str:
        if message.role == "assistant":
            sender_name = self._assistant_config_manager.get_assistant_name_by_assistant_id(message.assistant_id)
            return sender_name if sender_name else "assistant"
        elif message.role == "user":
            if message.metadata:
                sender_name = message.metadata.get("chat_assistant", "assistant")
                # Set the role to assistant if the metadata is set to assistant
                self._role = "assistant"
            else:
                sender_name = "user"
            return sender_name

    def _process_text_annotations(self, content_item: TextContentBlock) -> Tuple[List[str], List[FileCitation]]:
        citations = []
        file_citations = []

        if content_item.text.annotations:
            for index, annotation in enumerate(content_item.text.annotations):
                content_item.text.value = content_item.text.value.replace(annotation.text, f' [{index}]')

                if isinstance(annotation, FilePathAnnotation):
                    file_id = annotation.file_path.file_id
                    file_name = annotation.text.split("/")[-1]
                    self._file_message = FileMessage(self._ai_client, file_id, file_name)
                    citations.append(f'[{index}] {file_name}')
                    file_citations.append(FileCitation(file_id, file_name))

                elif isinstance(annotation, FileCitationAnnotation):
                    try:
                        file_id = annotation.file_citation.file_id
                        file_name = self._ai_client.files.retrieve(file_id).filename
                    except Exception as e:
                        logger.error(f"Failed to retrieve filename for file_id {file_id}: {e}")
                        file_name = "Unknown_" + str(file_id)
                    citations.append(f'[{index}] {file_name}')
                    file_citations.append(FileCitation(file_id, file_name))

        return citations, file_citations

    @property
    def text_message(self) -> Optional[TextMessage]:
        return self._text_message

    @text_message.setter
    def text_message(self, value: TextMessage):
        self._text_message = value

    @property
    def file_message(self) -> Optional['FileMessage']:
        return self._file_message

    @property
    def image_message(self) -> Optional['ImageMessage']:
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


class FileMessage:
    def __init__(self, 
                 ai_client : Union[OpenAI, AzureOpenAI],
                 file_id: str, 
                 file_name: str
    ):
        self._ai_client = ai_client
        self._file_id = file_id
        self._file_name = file_name

    @property
    def file_id(self) -> str:
        return self._file_id

    @property
    def file_name(self) -> str:
        return self._file_name

    def retrieve_file(self, output_folder_name: str) -> str:
        """
        Retrieve the file.

        :param output_folder_name: The name of the output folder.
        :type output_folder_name: str

        :return: The path of the retrieved file.
        :rtype: str
        """
        logger.info(f"Retrieving file with file_id: {self.file_id} to path: {output_folder_name}")
        file_path = f"{output_folder_name}/{self.file_name}"
        try:
            if os.path.exists(file_path):
                logger.info(f"File already exists at {file_path}. Skipping download.")
                return file_path

            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            logger.info(f"Copying file with file_id: {self.file_id} to path: {file_path}")

            with self._ai_client.with_streaming_response.files.content(self.file_id) as streamed_response:
                streamed_response.stream_to_file(file_path)

            return file_path
        except Exception as e:
            logger.error(f"Failed to retrieve file {self.file_id}: {e}")
            return None


class ImageMessage:
    def __init__(self,
                 ai_client : Union[OpenAI, AzureOpenAI],
                 file_id: str, 
                 file_name: str
    ):
        self._ai_client = ai_client
        self._file_id = file_id
        self._file_name = file_name

    @property
    def file_id(self) -> str:
        return self._file_id

    @property
    def file_name(self) -> str:
        return self._file_name

    def retrieve_image(self, output_folder_name: str) -> str:
        """
        Retrieve the image synchronously.

        :param output_folder_name: The name of the output folder.
        :type output_folder_name: str

        :return: The path of the retrieved image.
        :rtype: str
        """
        logger.info(f"Retrieving image with file_id: {self.file_id} to path: {output_folder_name}")
        file_path = os.path.join(output_folder_name, f"{self.file_id}.png")

        if os.path.exists(file_path):
            logger.info(f"File already exists at {file_path}. Skipping download and resize.")
            return file_path

        # Ensure the output directory exists
        os.makedirs(output_folder_name, exist_ok=True)

        try:
            # Get the image content synchronously
            response = self._ai_client.files.content(self.file_id)
            image_data = response.read()
            file_path = self._save_and_resize_image(image_data, file_path)
            logger.info(f"Resized image saved to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Unexpected error during image processing {self.file_id}: {e}")
            return None

    def _save_and_resize_image(self, image_data: bytes, file_path: str, target_width: float = 0.5, target_height: float = 0.5) -> str:
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
