# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.text_message import TextMessage, FileCitation
from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.management.message_utils import _resize_image, _save_image

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
import os, asyncio, base64


class AsyncConversationMessage:
    """
    A class representing a conversation message asynchronously.
    """
    def __init__(self):
        self._ai_client : Union[AsyncOpenAI, AsyncAzureOpenAI] = None
        self._original_message = None
        self._text_message = None
        self._file_messages = []
        self._image_messages = []
        self._image_urls = []
        self._role = None
        self._sender = None
        self._assistant_config_manager = None

    @classmethod
    async def create(cls, 
                     ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI],
                     original_message: Message = None
    ) -> 'AsyncConversationMessage':
        """
        Creates a new instance of the AsyncConversationMessage class.

        :param ai_client: The type of AI client to use for the conversation.
        :type ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI]
        :param original_message: The original message.
        :type original_message: Message

        :return: A new instance of the AsyncConversationMessage class.
        :rtype: AsyncConversationMessage
        """
        instance = cls()
        instance._ai_client = ai_client
        instance._original_message = original_message
        instance._role = original_message.role if original_message else "assistant"
        instance._assistant_config_manager = AssistantConfigManager.get_instance()
        if original_message:
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
                image_message = await AsyncImageMessage.create(
                    self._ai_client, content_item.image_file.file_id, f"{content_item.image_file.file_id}.png"
                )
                self._image_messages.append(image_message)
            elif isinstance(content_item, ImageURLContentBlock):
                self._image_urls.append(content_item.image_url.url)

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
                    file_message = await AsyncFileMessage.create(self._ai_client, file_id, file_name)
                    self._file_messages.append(file_message)
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
        """"
        Returns the text message content of the conversation message.

        :return: The text message content of the conversation message.
        :rtype: Optional[TextMessage]
        """
        return self._text_message

    @text_message.setter
    def text_message(self, value: TextMessage):
        """
        Sets the text message content of the conversation message.

        :param value: The text message content of the conversation message.
        :type value: TextMessage
        """
        self._text_message = value

    @property
    def file_messages(self) -> List['AsyncFileMessage']:
        """
        Returns the file message content of the conversation message.

        :return: The file message content of the conversation message.
        :rtype: List[AsyncFileMessage]
        """
        return self._file_messages

    @property
    def image_messages(self) -> List['AsyncImageMessage']:
        """
        Returns the list of image message contents of the conversation message.

        :return: The list of image message contents of the conversation message.
        :rtype: List[AsyncImageMessage]
        """
        return self._image_messages

    @property
    def image_urls(self) -> List[str]:
        """
        Returns the list of image URLs.

        :return: The list of image URLs.
        :rtype: List[str]
        """
        return self._image_urls

    @property
    def role(self) -> str:
        """
        Returns the role of the sender of the conversation message.

        :return: The role of the sender of the conversation message.
        :rtype: str
        """
        return self._role

    @property
    def sender(self) -> str:
        """
        Returns the name of the sender of the conversation message.

        :return: The name of the sender of the conversation message.
        :rtype: str
        """
        return self._sender

    @property
    def original_message(self) -> Message:
        """
        Returns the original message.

        :return: The original message.
        :rtype: Message
        """
        return self._original_message


class AsyncFileMessage:
    """
    A class representing a file message asynchronously.

    :param ai_client: The type of AI client to use for the conversation.
    :type ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI]
    :param file_id: The file ID.
    :type file_id: str
    :param file_name: The file name.
    :type file_name: str
    """
    def __init__(self, ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI], file_id: str, file_name: str):
        self._ai_client = ai_client
        self._file_id = file_id
        self._file_name = file_name

    @classmethod
    async def create(cls, ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI], file_id: str, file_name: str):
        """
        Creates a new instance of the AsyncFileMessage class.

        :param ai_client: The type of AI client to use for the conversation.
        :type ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI]
        :param file_id: The file ID.
        :type file_id: str
        :param file_name: The file name.
        :type file_name: str

        :return: A new instance of the AsyncFileMessage class.
        :rtype: AsyncFileMessage
        """
        instance = cls(ai_client, file_id, file_name)
        return instance

    @property
    def file_id(self) -> str:
        """
        Returns the file ID.

        :return: The file ID.
        :rtype: str
        """
        return self._file_id

    @property
    def file_name(self) -> str:
        """
        Returns the file name.

        :return: The file name.
        :rtype: str
        """
        return self._file_name

    async def retrieve_file(self, output_folder_name: str) -> str:
        """
        Asynchronously retrieve the file.

        :param output_folder_name: The name of the output folder.
        :type output_folder_name: str

        :return: The path of the retrieved file.
        :rtype: str
        """
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
    """
    A class representing an image message asynchronously.

    :param ai_client: The type of AI client to use for the conversation.
    :type ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI]
    :param file_id: The file ID.
    :type file_id: str
    :param file_name: The file name.
    :type file_name: str
    """
    def __init__(self, ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI], file_id: str, file_name: str):
        self._ai_client = ai_client
        self._file_id = file_id
        self._file_name = file_name

    @classmethod
    async def create(cls, ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI], file_id: str, file_name: str):
        """
        Creates a new instance of the AsyncImageMessage class.

        :param ai_client: The type of AI client to use for the conversation.
        :type ai_client: Union[AsyncOpenAI, AsyncAzureOpenAI]
        :param file_id: The file ID.
        :type file_id: str
        :param file_name: The file name.
        :type file_name: str

        :return: A new instance of the AsyncImageMessage class.
        :rtype: AsyncImageMessage
        """
        instance = cls(ai_client, file_id, file_name)
        return instance

    @property
    def file_id(self) -> str:
        """
        Returns the file ID.

        :return: The file ID.
        :rtype: str
        """
        return self._file_id

    @property
    def file_name(self) -> str:
        """
        Returns the file name.

        :return: The file name.
        :rtype: str
        """
        return self._file_name

    async def get_image_base64(self, target_width: float = 0.5, target_height: float = 0.5) -> str:
        """
        Asynchronously retrieve the image as a base64 encoded string after resizing it.

        :param target_width: The target width as a fraction of the original width.
        :type target_width: float
        :param target_height: The target height as a fraction of the original height.
        :type target_height: float

        :return: The base64 encoded string of the resized image.
        :rtype: str
        """
        logger.info(f"Retrieving and resizing image with file_id: {self.file_id} as base64 encoded string")
        try:
            # Asynchronously get the image content
            async with self._ai_client.files.content(self.file_id) as response:
                image_data = await response.read()
                # Resize the image in a separate thread
                resized_image_data = await asyncio.to_thread(
                    _resize_image, image_data, target_width, target_height
                )
                img_base64 = base64.b64encode(resized_image_data).decode('utf-8')
                
            return img_base64
        except Exception as e:
            logger.error(f"Unexpected error during image base64 encoding {self.file_id}: {e}")
            return None

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
                resized_image_data = await asyncio.to_thread(
                    _resize_image, image_data, 0.5, 0.5
                )
                await asyncio.to_thread(_save_image, resized_image_data, file_path)
                logger.info(f"Resized image saved to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Unexpected error during image processing {self.file_id}: {e}")
            return None