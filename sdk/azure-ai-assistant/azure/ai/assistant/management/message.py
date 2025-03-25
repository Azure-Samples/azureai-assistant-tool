# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.
import os
import base64
from typing import Union, Optional, List, Tuple

# Imports for OpenAI / AzureOpenAI:
from openai import AzureOpenAI, OpenAI
from openai.types.beta.threads import (
    ImageFileContentBlock,
    ImageURLContentBlock,
    TextContentBlock,
    Message as OpenAIMessage,
    FileCitationAnnotation, 
    FilePathAnnotation
)

# Imports for Azure AI Agents / Projects
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    ThreadMessage,
    MessageTextContent,
    MessageImageFileContent,
    MessageTextFileCitationAnnotation,
    MessageTextFilePathAnnotation
)

from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.text_message import TextMessage, FileCitation, UrlCitation
from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.management.message_utils import _resize_image, _save_image
from azure.ai.assistant.management.attachment import AttachmentType
from azure.ai.assistant.management.ai_client_factory import AIClient


class ConversationMessage:
    """
    A class representing a conversation message that can come either from 
    OpenAI's `Message` or Azure AI Agents' `ThreadMessage`.

    :param ai_client: The AI client (OpenAI, AzureOpenAI, or AIProjectClient).
    :rtype ai_client: AIClient
    :param original_message: Either an OpenAI `Message` or a `ThreadMessage` from Azure.
    :rtype original_message: Union[OpenAIMessage, ThreadMessage, None]
    """

    def __init__(
        self,
        ai_client: AIClient,
        original_message: Union[OpenAIMessage, ThreadMessage, None] = None
    ):
        self._ai_client = ai_client
        self._original_message = original_message

        self._text_message: Optional[TextMessage] = None
        self._file_messages: List[FileMessage] = []
        self._image_messages: List[ImageMessage] = []
        self._image_urls: List[str] = []
        self._url_citations: List[UrlCitation] = []
        self._role: str = "assistant"
        self._sender: Optional[str] = None

        self._assistant_config_manager = AssistantConfigManager.get_instance()

        if original_message is not None:
            if isinstance(original_message, OpenAIMessage):
                self._role = original_message.role or "assistant"
                self._sender = self._get_sender_name_openai(original_message)
                self._process_openai_message_contents(original_message)
            elif isinstance(original_message, ThreadMessage):
                self._role = original_message.role.value or "assistant"
                self._sender = self._get_sender_name_azure(original_message)
                self._process_azure_thread_message_contents(original_message)

    def _process_openai_message_contents(self, openai_message: OpenAIMessage):
        for content_item in openai_message.content:
            if isinstance(content_item, TextContentBlock):
                citations, file_citations = self._process_openai_text_annotations(content_item)
                content_value = content_item.text.value
                if citations:
                    # E.g. append references at the end
                    content_value += "\n" + "\n".join(citations)
                self._text_message = TextMessage(content_value, file_citations)

            elif isinstance(content_item, ImageFileContentBlock):
                # Store reference to an ImageMessage
                self._image_messages.append(
                    ImageMessage(self._ai_client, content_item.image_file.file_id, f"{content_item.image_file.file_id}.png")
                )

            elif isinstance(content_item, ImageURLContentBlock):
                self._image_urls.append(content_item.image_url.url)

    def _process_openai_text_annotations(
        self, 
        content_item: TextContentBlock
    ) -> Tuple[List[str], List[FileCitation]]:
        citations = []
        file_citations = []

        if content_item.text.annotations:
            for index, annotation in enumerate(content_item.text.annotations):
                # Add bracketed references in the text
                content_item.text.value = content_item.text.value.replace(
                    annotation.text, f" [{index}]"
                )

                if isinstance(annotation, FilePathAnnotation):
                    file_id = annotation.file_path.file_id
                    file_name = annotation.text.split("/")[-1]
                    self._file_messages.append(FileMessage(self._ai_client, file_id, file_name))
                    citations.append(f"[{index}] {file_name}")
                    file_citations.append(FileCitation(file_id, file_name))

                elif isinstance(annotation, FileCitationAnnotation):
                    try:
                        file_id = annotation.file_citation.file_id
                        file_name = self._ai_client.files.retrieve(file_id).filename
                    except Exception as e:
                        logger.error(f"Failed to retrieve filename for file_id {file_id}: {e}")
                        file_name = f"Unknown_{file_id}"

                    citations.append(f"[{index}] {file_name}")
                    file_citations.append(FileCitation(file_id, file_name))

        return citations, file_citations

    def _get_sender_name_openai(self, message: OpenAIMessage) -> str:
        if message.role == "assistant":
            # Optionally use assistant name from config manager
            name = self._assistant_config_manager.get_assistant_name_by_assistant_id(
                message.assistant_id
            )
            return name if name else "assistant"
        elif message.role == "user":
            if message.metadata:
                return message.metadata.get("chat_assistant", "user")
            else:
                return "user"
        else:
            # Possibly "system" or other role
            return message.role or "assistant"

    def _process_azure_thread_message_contents(self, thread_message: ThreadMessage):
        for idx, text_content in enumerate(thread_message.text_messages):
            text_value = text_content.text.value
            # Now we capture file citations, references, AND url citations
            citations, file_citations, url_citations = self._process_azure_text_annotations(text_content, idx)

            if citations:
                text_value += "\n" + "\n".join(citations)

            # Create a TextMessage that includes both file and URL citations
            self._text_message = TextMessage(
                content=text_value,
                file_citations=file_citations,
                url_citations=url_citations
            )

        # Handle any image attachments as before
        for image_content in thread_message.image_contents:
            file_id = image_content.image_file.file_id
            file_name = f"{file_id}.png"
            self._image_messages.append(ImageMessage(self._ai_client, file_id, file_name))

    def _process_azure_text_annotations(
        self,
        text_content: MessageTextContent,
        block_index: int
    ) -> Tuple[List[str], List[FileCitation], List[UrlCitation]]:
        
        citations = []
        file_citations: List[FileCitation] = []
        url_citations: List[UrlCitation] = []

        if text_content.text.annotations:
            for index, annotation in enumerate(text_content.text.annotations):
                ref_marker = f"[{block_index}.{index}]"
                # Insert bracket references in the text
                text_content.text.value = text_content.text.value.replace(
                    annotation.text, f" {ref_marker}"
                )

                # Handle file path annotation
                if isinstance(annotation, MessageTextFilePathAnnotation):
                    file_id = annotation.file_path.file_id
                    file_name = os.path.basename(annotation.text)
                    self._file_messages.append(FileMessage(self._ai_client, file_id, file_name))
                    citations.append(f"{ref_marker} {file_name}")
                    file_citations.append(FileCitation(file_id, file_name))

                # Handle file citation annotation
                elif isinstance(annotation, MessageTextFileCitationAnnotation):
                    file_id = annotation.file_citation.file_id
                    try:
                        file_name = self._ai_client.agents.get_file(file_id).filename
                    except Exception as e:
                        logger.error(f"Failed to retrieve filename for file_id {file_id}: {e}")
                        file_name = f"Unknown_{file_id}"
                    citations.append(f"{ref_marker} {file_name}")
                    file_citations.append(FileCitation(file_id, file_name))

                # Handle URL citation (no official type in azure.ai.projects yet)
                elif getattr(annotation, "type", None) == "url_citation":
                    # Here 'annotation' is a dict, not a typed object
                    url_citation_dict = annotation.get("url_citation", {})
                    url = url_citation_dict.get("url")
                    title = url_citation_dict.get("title") or url
                    if url:
                        # [link text](link target)
                        citations.append(f"[{title}]({url})")
                        url_citations.append(UrlCitation(url, title))

        return citations, file_citations, url_citations

    def _get_sender_name_azure(self, thread_message: ThreadMessage) -> str:
        if thread_message.role.value == "assistant":
            # Optionally use assistant name from config manager
            name = self._assistant_config_manager.get_assistant_name_by_assistant_id(
                thread_message.agent_id
            )
            return name if name else "assistant"
        else:
            return "user"

    @property
    def text_message(self) -> Optional[TextMessage]:
        """
        Returns the text message content.

        :return: The text message content.
        :rtype: Optional[TextMessage]
        """
        return self._text_message

    @text_message.setter
    def text_message(self, value: TextMessage):
        """
        Sets the text message content.

        :param value: The text message content.
        :type value: TextMessage
        """
        self._text_message = value

    @property
    def file_messages(self) -> List["FileMessage"]:
        """
        Returns the file message content.

        :return: The file message content.
        :rtype: List[FileMessage]
        """
        return self._file_messages

    @property
    def image_messages(self) -> List["ImageMessage"]:
        """
        Returns the list of image message contents.

        :return: The list of image message contents.
        :rtype: List[ImageMessage]
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
        Returns the role of the sender.

        :return: The role of the sender.
        :rtype: str
        """
        return self._role

    @role.setter
    def role(self, value: str):
        """
        Sets the role of the sender.

        :param value: The role of the sender.
        :type value: str
        """
        self._role = value

    @property
    def sender(self) -> str:
        """
        Returns the sender of the message.

        :return: The sender of the message.
        :rtype: str
        """
        return self._sender or "assistant"

    @sender.setter
    def sender(self, value: str):
        """
        Sets the sender of the message.

        :param value: The sender of the message.
        :type value: str
        """
        self._sender = value

    @property
    def original_message(self) -> Union[OpenAIMessage, ThreadMessage, None]:
        """
        Returns the original message.

        :return: The original message.
        :rtype: Union[OpenAIMessage, ThreadMessage]
        """
        return self._original_message


class FileMessage:
    """
    A class representing a file message.

    :param ai_client: The AI client (OpenAI, AzureOpenAI, or AIProjectClient)
    :type ai_client: AIClient
    :param file_id: The file ID.
    :type file_id: str
    :param file_name: The file name.
    :type file_name: str
    """
    def __init__(
        self, 
        ai_client: AIClient,
        file_id: str, 
        file_name: str
    ):
        self._ai_client = ai_client
        self._file_id = file_id
        self._file_name = file_name

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

    def retrieve_file(self, output_folder_name: str) -> Optional[str]:
        """
        Retrieve the file.

        :param output_folder_name: The name of the output folder.
        :type output_folder_name: str

        :return: The path of the retrieved file.
        :rtype: str
        """
        logger.info(f"Retrieving file with file_id: {self.file_id} to path: {output_folder_name}")
        file_path = os.path.join(output_folder_name, self.file_name)
        try:
            if os.path.exists(file_path):
                logger.info(f"File already exists at {file_path}. Skipping download.")
                return file_path

            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            logger.info(f"Copying file with file_id: {self.file_id} to path: {file_path}")

            if isinstance(self._ai_client, AzureOpenAI) or isinstance(self._ai_client, OpenAI):
                with self._ai_client.with_streaming_response.files.content(self.file_id) as streamed_response:
                    streamed_response.stream_to_file(file_path)
            elif isinstance(self._ai_client, AIProjectClient):
                self._ai_client.agents.save_file(file_id=self.file_id, file_name=self.file_name, target_dir=output_folder_name)

            return file_path
        except Exception as e:
            logger.error(f"Failed to retrieve file {self.file_id}: {e}")
            return None


class ImageMessage:
    """
    A class representing an image message.

    :param ai_client: The AI client (OpenAI, AzureOpenAI, or AIProjectClient).
    :type ai_client: AIClient
    :param file_id: The file ID.
    :type file_id: str
    :param file_name: The file name.
    :type file_name: str
    """
    def __init__(
        self,
        ai_client: AIClient,
        file_id: str, 
        file_name: str
    ):
        self._ai_client = ai_client
        self._file_id = file_id
        self._file_name = file_name

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

    def get_image_base64(self, target_width: float = 0.5, target_height: float = 0.5) -> Optional[str]:
        """
        Retrieve the image as a base64 encoded string after resizing it.

        :param target_width: The target width as a fraction of the original width.
        :type target_width: float
        :param target_height: The target height as a fraction of the original height.
        :type target_height: float

        :return: The base64 encoded string of the resized image.
        :rtype: str
        """
        logger.info(f"Retrieving and resizing image with file_id: {self.file_id} as base64.")
        try:
            if isinstance(self._ai_client, AzureOpenAI) or isinstance(self._ai_client, OpenAI):
                response = self._ai_client.files.content(self.file_id)
                image_data = response.read()

                resized_image_data = _resize_image(image_data, target_width, target_height)
                img_base64 = base64.b64encode(resized_image_data).decode("utf-8")
                return img_base64
            elif isinstance(self._ai_client, AIProjectClient):
                file_content_stream = self._ai_client.agents.get_file_content(self.file_id)
                if not file_content_stream:
                    logger.error(f"No content was retrievable for file_id '{self.file_id}'.")
                    return None

                # Concatenate all chunks into a single bytes object
                image_data = b""
                for chunk in file_content_stream:
                    image_data += chunk

                resized_image_data = _resize_image(image_data, target_width, target_height)
                img_base64 = base64.b64encode(resized_image_data).decode("utf-8")
                return img_base64
        except Exception as e:
            logger.error(f"Unexpected error during image base64 encoding {self.file_id}: {e}")
            return None

    def retrieve_image(self, output_folder_name: str) -> Optional[str]:
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
            logger.info(f"File already exists at {file_path}. Skipping download/resize.")
            return file_path

        os.makedirs(output_folder_name, exist_ok=True)

        try:
            if isinstance(self._ai_client, AzureOpenAI) or isinstance(self._ai_client, OpenAI):
                response = self._ai_client.files.content(self.file_id)
                image_data = response.read()
                resized_image_data = _resize_image(image_data, 0.5, 0.5)
                _save_image(resized_image_data, file_path)
            elif isinstance(self._ai_client, AIProjectClient):
                file_content_stream = self._ai_client.agents.get_file_content(self.file_id)
                if not file_content_stream:
                    logger.error(f"No content was retrievable for file_id '{self.file_id}'.")
                    return None

                # Concatenate all chunks into a single bytes object
                image_data = b""
                for chunk in file_content_stream:
                    image_data += chunk

                resized_image_data = _resize_image(image_data, 0.5, 0.5)
                _save_image(resized_image_data, file_path)
            logger.info(f"Resized image saved to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Unexpected error during image processing {self.file_id}: {e}")
            return None