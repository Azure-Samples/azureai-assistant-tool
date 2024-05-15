# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
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
                 original_message: Message
    ):
        self._ai_client = ai_client
        self._original_message = original_message
        self._text_message_content = None
        self._file_message_content = None
        self._image_message_content = None
        self._role = original_message.role
        self._sender = None
        self._assistant_config_manager = AssistantConfigManager().get_instance()
        self._sender = self._get_sender_name(original_message)
        self.process_message_contents(original_message)

    def process_message_contents(self, original_message: Message):
        for content_item in original_message.content:
            if isinstance(content_item, TextContentBlock):
                citations, file_citations = self._process_text_annotations(content_item)
                content_value = content_item.text.value
                if citations:
                    content_value += '\n' + '\n'.join(citations)
                self._text_message_content = TextMessageContent(content_value, file_citations)

            elif isinstance(content_item, ImageFileContentBlock):
                self._image_message_content = ImageMessageContent(self._ai_client, content_item.image_file.file_id, f"{content_item.image_file.file_id}.png")

    def _get_sender_name(self, message: Message) -> str:
        if message.role == "assistant":
            sender_name = self._assistant_config_manager.get_assistant_name_by_assistant_id(message.assistant_id)
            return sender_name if sender_name else "assistant"
        elif message.role == "user":
            if message.metadata:
                sender_name = message.metadata.get("chat_assistant", "assistant")
                # Set the role to assistant if the metadata is set to assistant
                message.role = "assistant"
            else:
                sender_name = "user"
            return sender_name

    def _process_text_annotations(self, content_item: TextContentBlock) -> Tuple[List[str], List['FileCitation']]:
        citations = []
        file_citations = []

        if content_item.text.annotations:
            for index, annotation in enumerate(content_item.text.annotations):
                content_item.text.value = content_item.text.value.replace(annotation.text, f' [{index}]')

                if isinstance(annotation, FilePathAnnotation):
                    file_id = annotation.file_path.file_id
                    file_name = annotation.text.split("/")[-1]
                    self.file_message_content = FileMessageContent(self._ai_client, file_id, file_name)
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
    def text_message_content(self) -> Optional['TextMessageContent']:
        return self._text_message_content

    @property
    def file_message_content(self) -> Optional['FileMessageContent']:
        return self._file_message_content

    @property
    def image_message_content(self) -> Optional['ImageMessageContent']:
        return self._image_message_content

    @property
    def role(self) -> str:
        return self._role

    @property
    def sender(self) -> str:
        return self._sender
    
    @property
    def original_message(self) -> Message:
        return self._original_message


class TextMessageContent:
    def __init__(self, content: str, file_citations: Optional[List['FileCitation']] = None):
        self._content = content
        self._file_citations = file_citations

    @property
    def content(self) -> str:
        return self._content

    @property
    def file_citations(self) -> Optional[List['FileCitation']]:
        return self._file_citations


class FileMessageContent:
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


class ImageMessageContent:
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
        Retrieve the image.

        :param output_folder_name: The name of the output folder.
        :type output_folder_name: str

        :return: The path of the retrieved image.
        :rtype: str
        """
        logger.info(f"Retrieving image with file_id: {self.file_id} to path: {output_folder_name}")
        file_path = self._save_and_resize_image(self.file_id, output_folder_name)
        return file_path

    def _save_and_resize_image(
            self,
            file_id,
            output_folder_path,
            target_width=0.5,
            target_height=0.5
    ) -> str:
        
        if not output_folder_path:
            logger.warning("Output folder path is not set. Cannot process files.")
            return None

        file_path = os.path.join(output_folder_path, f"{file_id}.png")
        if os.path.exists(file_path):
            logger.info(f"File already exists at {file_path}. Skipping download and resize.")
            return file_path

        try:
            with self._ai_client.with_streaming_response.files.content(file_id) as streamed_response:
                with Image.open(io.BytesIO(streamed_response.read())) as img:
                    new_width = int(img.width * target_width)
                    new_height = int(img.height * target_height)
                    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    resized_img.save(file_path)
            logger.info(f"Resized image saved to {file_path}")
            return file_path
        except UnidentifiedImageError as e:
            logger.error(f"Cannot identify image file {file_id}: {e}")
        except IOError as e:
            logger.error(f"IO error during image processing {file_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during image processing {file_id}: {e}")
        return None


class FileCitation:
    """
    A class representing a file citation.

    :param file_id: The ID of the file.
    :type file_id: str
    :param file_name: The name of the file.
    :type file_name: str
    """
    def __init__(
            self, 
            file_id : str,
            file_name : str
    ) -> None:
        self._file_id = file_id
        self._file_name = file_name

    @property
    def file_id(self) -> str:
        """
        Returns the ID of the file.

        :return: The ID of the file.
        :rtype: str
        """
        return self._file_id

    @property
    def file_name(self) -> str:
        """
        Returns the name of the file.

        :return: The name of the file.
        :rtype: str
        """
        return self._file_name