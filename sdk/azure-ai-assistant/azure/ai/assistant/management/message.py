# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.ai_client_factory import AIClientFactory, AIClientType
from azure.ai.assistant.management.logger_module import logger
from typing import Union
from openai import AzureOpenAI, OpenAI
from PIL import Image, UnidentifiedImageError
import os
import io


class MessageBase:
    """
    A class representing a message.

    :param ai_client_type: The type of the AI client.
    :type ai_client_type: AIClientType
    :param role: The role of the sender.
    :type role: str
    :param sender: The name of the sender.
    :type sender: str
    """
    def __init__(
            self, 
            ai_client_type: AIClientType, 
            role: str, 
            sender: str
    ) -> None:
        self._ai_client_type = ai_client_type
        self._role = role
        self._sender = sender

    def _get_ai_client(self) -> Union[OpenAI, AzureOpenAI]:
        try:
            return AIClientFactory.get_instance().get_client(self._ai_client_type)
        except KeyError as e:
            logger.error(f"Invalid AI client type: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to get AI client: {e}")
            raise

    @property
    def role(self) -> str:
        """
        Returns the role of the sender.

        :return: The role of the sender.
        :rtype: str
        """
        return self._role

    @property
    def sender(self) -> str:
        """
        Returns the name of the sender.

        :return: The name of the sender.
        :rtype: str
        """
        return self._sender


class TextMessage(MessageBase):
    """
    A class representing a text message.

    :param content: The content of the message.
    :type content: str
    :param ai_client_type: The type of the AI client.
    :type ai_client_type: AIClientType
    :param role: The role of the sender.
    :type role: str
    :param sender: The name of the sender.
    :type sender: str
    """
    def __init__(
            self, 
            content : str,
            ai_client_type: AIClientType, 
            role : str,
            sender : str
    ) -> None:
        super().__init__(ai_client_type, role, sender)
        self.content = content
        self.type = "text"

    def __str__(self) -> str:
        """
        Returns the string representation of the text message.

        :return: The string representation of the text message.
        :rtype: str
        """
        return f"{self.sender}: {self.content}"


class FileMessage(MessageBase):
    """
    A class representing a file message.

    :param file_id: The ID of the file.
    :type file_id: str
    :param file_name: The name of the file.
    :type file_name: str
    :param ai_client_type: The type of the AI client.
    :type ai_client_type: AIClientType
    :param role: The role of the sender.
    :type role: str
    :param sender: The name of the sender.
    :type sender: str
    """
    def __init__(
            self, 
            file_id : str,
            file_name : str,
            ai_client_type: AIClientType, 
            role : str,
            sender : str
    ) -> None:
        super().__init__(ai_client_type, role, sender)
        self._file_id = file_id
        self._file_name = file_name
        self._type = "file"

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

    @property
    def type(self) -> str:
        """
        Returns the type of the file.

        :return: The type of the file.
        :rtype: str
        """
        return self._type

    def retrieve_file(
            self, 
            output_folder_name
    ) -> str:
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
            # if the file is already downloaded, return the path
            if os.path.exists(file_path):
                logger.info(f"File already exists at {file_path}. Skipping download.")
                return file_path

            ai_client = self._get_ai_client()
            # Create the output directory if it does not exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            logger.info(f"Copying file with file_id: {self.file_id} to path: {file_path}")
            with ai_client.with_streaming_response.files.content(self.file_id) as streamed_response:
                streamed_response.stream_to_file(file_path)

            return file_path
        except Exception as e:
            logger.error(f"Failed to retrieve file {self.file_id}: {e}")
            return None


class ImageMessage(FileMessage):
    """
    A class representing a image message.

    :param file_id: The ID of the file.
    :type file_id: str
    :param file_name: The name of the file.
    :type file_name: str
    :param ai_client_type: The type of the AI client.
    :type ai_client_type: AIClientType
    :param role: The role of the sender.
    :type role: str
    :param sender: The name of the sender.
    :type sender: str
    """
    def __init__(
            self, 
            file_id : str,
            file_name : str,
            ai_client_type: AIClientType, 
            role : str,
            sender : str
    ):
        super().__init__(file_id, file_name, ai_client_type, role, sender)
        self._type = "image_file"

    @property
    def type(self) -> str:
        """
        Returns the type of the file.

        :return: The type of the file.
        :rtype: str
        """
        return self._type

    def retrieve_image(
            self, 
            output_folder_name : str
    ) -> str:
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
            api_client = self._get_ai_client()
            with api_client.with_streaming_response.files.content(file_id) as streamed_response:
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