# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.conversation_thread_config import ConversationThreadConfig
from azure.ai.assistant.management.ai_client_factory import AIClientFactory, AIClientType
from azure.ai.assistant.management.conversation import Conversation
from typing import Optional
from openai import AzureOpenAI, OpenAI
from typing import Union, List
from openai.types.beta.threads import (
    ImageFileContentBlock,
    TextContentBlock
)
from openai.types.beta.threads import Message
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.exceptions import EngineError
from azure.ai.assistant.management.logger_module import logger
import threading


class ConversationThreadClient:
    _instances = {}
    _lock = threading.Lock()
    """
    A class to manage conversation threads.

    :param ai_client_type: The type of the AI client to use.
    :type ai_client_type: AIClientType
    """
    def __init__(
            self, 
            ai_client_type : AIClientType
    ) -> None:
        self._ai_client_type = ai_client_type
        self._ai_client : Union[OpenAI, AzureOpenAI] = AIClientFactory.get_instance().get_client(self._ai_client_type)
        self._thread_config = ConversationThreadConfig(self._ai_client_type, f'config/threads.json')
        self._assistant_config_manager = AssistantConfigManager.get_instance()

    @classmethod
    def get_instance(
        cls, 
        ai_client_type : AIClientType
    ) -> 'ConversationThreadClient':
        """
        Get the singleton instance of the ConversationThreadClient.

        :param ai_client_type: The type of the AI client to use.
        :type ai_client_type: AIClientType

        :return: The singleton instance of the ConversationThreadClient.
        :rtype: ConversationThreadClient
        """
        if ai_client_type not in cls._instances:
            with cls._lock:
                if ai_client_type not in cls._instances:
                    cls._instances[ai_client_type] = cls(ai_client_type)
        return cls._instances[ai_client_type]

    def create_conversation_thread(
            self,
            timeout : Optional[float] = None
    ) -> str:
        """
        Creates a conversation thread.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: float, optional

        :return: The name of the created thread.
        :rtype: str
        """
        try:
            # Create a new conversation thread for the assistant
            thread = self._ai_client.beta.threads.create(timeout=timeout)
            # Add the new thread to the thread config
            self._thread_config.add_thread(thread.id, "New Thread")
            thread_name = self._thread_config.get_thread_name_by_id(thread.id)
            logger.info(f"Created thread Id: {thread.id} for thread name: {thread_name}")
            return thread_name
        except Exception as e:
            logger.error(f"Failed to create thread: {e}")
            raise EngineError(f"Failed to create thread: {e}")

    def set_current_conversation_thread(
            self, 
            thread_name : str
    ) -> None:
        """
        Sets the current conversation thread.

        :param thread_name: The unique name of the thread to set as the current thread.
        :type thread_name: str
        """
        thread_id = self._thread_config.get_thread_id_by_name(thread_name)
        logger.info(f"Setting current thread name: {thread_name} to thread ID: {thread_id}")
        self._thread_config.set_current_thread_by_name(thread_name)

    def is_current_conversation_thread(
            self, 
            thread_name : str
    ) -> bool:
        """
        Checks if the given thread name is the current thread for the given assistant name.

        :param thread_name: The unique name of the thread to check.
        :type thread_name: str

        :return: True if the given thread name is the current thread, False otherwise.
        :rtype: bool
        """
        thread_id = self._thread_config.get_thread_id_by_name(thread_name)
        if thread_id == self._thread_config.get_current_thread_id():
            return True
        return False

    def set_conversation_thread_name(
            self, 
            new_thread_name : str,
            thread_name : str
    ) -> str:
        """
        Sets the current thread name.

        :param new_thread_name: The new name to set for the thread.
        :type new_thread_name: str
        :param thread_name: The unique name of the thread to set the new name for.
        :type thread_name: str

        :return: The updated thread name.
        :rtype: str
        """
        thread_id = self._thread_config.get_thread_id_by_name(thread_name)
        self._thread_config.update_thread_name(thread_id, new_thread_name)
        updated_thread_name = self._thread_config.get_thread_name_by_id(thread_id)
        return updated_thread_name

    def _get_conversation_thread_messages(
            self, 
            thread_name : str,
            timeout : Optional[float] = None
    ) -> List[Message]:
        try:
            thread_id = self._thread_config.get_thread_id_by_name(thread_name)
            messages = self._ai_client.beta.threads.messages.list(
                thread_id=thread_id,
                timeout=timeout
            )
            return messages.data
        except Exception as e:
            logger.error(f"Failed to retrieve thread messages for thread name {thread_name}: {e}")
            raise EngineError(f"Failed to retrieve thread messages or thread name {thread_name}: {e}")

    def retrieve_conversation(
            self,
            thread_name: str,
            timeout: Optional[float] = None,
            max_text_messages: Optional[int] = None
    ) -> Conversation:
        """
        Retrieves the conversation from the given thread name.

        :param thread_name: The name of the thread to retrieve the conversation from.
        :type thread_name: str
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: float, optional
        :param max_text_messages: Specifies the maximum number of the most recent text messages to retrieve. If None, all messages are retrieved.
        :type max_text_messages: int, optional

        :return: The conversation.
        :rtype: Conversation
        """
        try:
            messages = self._get_conversation_thread_messages(thread_name, timeout)
            conversation = self._retrieve_messages(messages, max_text_messages=max_text_messages)
            return conversation
        except Exception as e:
            error_message = f"Error retrieving messages content: Exception: {e}"
            logger.error(error_message)
            raise EngineError(error_message)

    def _retrieve_messages(
            self, 
            messages: List[Message],
            max_text_messages: Optional[int] = None
    ) -> Conversation:

        conversation = Conversation(self._ai_client_type)
        text_messages_count = 0
        for message in messages:
            logger.info(f"Processing message: {message}")
            if message.role == "assistant":
                sender_name = self._assistant_config_manager.get_assistant_name_by_assistant_id(message.assistant_id)
                if sender_name is None:
                    sender_name = "assistant"
            if message.role == "user":
                if message.metadata:
                    sender_name = message.metadata.get("chat_assistant", "assistant")
                    message.role = "assistant"
                else:
                    sender_name = "user"

            for content_item in message.content:
                if isinstance(content_item, TextContentBlock):
                    if max_text_messages is not None and text_messages_count >= max_text_messages:
                        # If we've reached the max number of text messages, return the conversation early
                        return conversation
                    # Add message to conversation and increment counter
                    conversation.add_message(content_item.text.value, message.role, sender_name)
                    text_messages_count += 1

                    file_annotations = content_item.text.annotations
                    if file_annotations:
                        for annotation in file_annotations:
                            file_id = annotation.file_path.file_id
                            sandbox_file_path = annotation.text
                            file_name = sandbox_file_path.split("/")[-1]
                            conversation.add_file(file_id, file_name, message.role, sender_name)
                elif isinstance(content_item, ImageFileContentBlock):
                    file_id = content_item.image_file.file_id
                    file_name = f"{file_id}.png" # file type is currently always png for images
                    conversation.add_image(file_id, file_name, message.role, sender_name)
        return conversation

    def create_conversation_thread_message(
            self, 
            message : str,
            thread_name : str,
            file_paths : Optional[list] = None,
            additional_instructions : Optional[str] = None,
            timeout : Optional[float] = None,
            metadata : Optional[dict] = None
    ) -> None:
        """
        Creates a new assistant thread message.

        :param message: The message to create.
        :type message: str
        :param thread_name: The unique name of the thread to create the message in.
        :type thread_name: str
        :param file_paths: The file paths to add to the message.
        :type file_paths: list, optional
        :param additional_instructions: The additional instructions to add to the message.
        :type additional_instructions: str, optional
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: float, optional
        """
        try:

            # Handle file updates and get file IDs
            thread_id = self._thread_config.get_thread_id_by_name(thread_name)
            file_ids = self._update_message_files(thread_id, file_paths) if file_paths is not None else []

            # Update AssistantConfig with the changed additional instructions
            current_additional_instructions = self._thread_config.get_additional_instructions_of_thread(thread_id)
            if additional_instructions != current_additional_instructions:
                self._thread_config.set_additional_instructions_to_thread(thread_id, additional_instructions)

            # Create the message with file IDs
            self._ai_client.beta.threads.messages.create(
                thread_id,
                role="user",
                metadata=metadata,
                content=message,
                file_ids=file_ids,
                timeout=timeout
            )

            logger.info(f"Created message: {message} in thread: {thread_id}, files: {file_ids}")
        except Exception as e:
            logger.error(f"Failed to create message: {message} in thread: {thread_id}, files: {file_ids}: {e}")
            raise EngineError(f"Failed to create message: {message} in thread: {thread_id}, files: {file_ids}: {e}")

    def _update_message_files(
            self, 
            thread_id : str,
            file_paths : list
    ):
        # Check if file handling is necessary
        existing_files = self._thread_config.get_files_of_thread(thread_id)
        if not file_paths and not existing_files:
            return []

        # Identify files to delete and new files to add
        existing_file_paths = [file['file_path'] for file in existing_files]
        files_to_delete = [file for file in existing_files if file['file_path'] not in file_paths]
        file_paths_to_add = [path for path in file_paths if path not in existing_file_paths]

        # Update AssistantConfig with the new set of files
        if files_to_delete:
            # Remove files from ThreadConfig
            file_ids_to_delete = [file['file_id'] for file in files_to_delete]
            self._thread_config.remove_files_from_thread(thread_id, file_ids_to_delete)
            # Get the updated list of files for the thread
            existing_files = self._thread_config.get_files_of_thread(thread_id)
            # Delete files from client
            for file in files_to_delete:
                self._ai_client.files.delete(file_id=file['file_id'])

        # if no new files to add, return the list of current file IDs for the thread
        if not file_paths_to_add:
            return [file['file_id'] for file in existing_files]

        # Create new files and update ThreadConfig
        new_files = []
        for file_path in file_paths_to_add:
            file_object = self._ai_client.files.create(
                file=open(file_path, "rb"),
                purpose='assistants'
            )
            file_id = file_object.id  # Extracting file ID from the FileObject
            new_files.append({'file_id': file_id, 'file_path': file_path})

        # Update ThreadConfig with the new set of files
        updated_files = [file for file in existing_files if file not in files_to_delete] + new_files
        self._thread_config.add_files_to_thread(thread_id, updated_files)

        # Return the list of all current file IDs for the thread
        return [file['file_id'] for file in updated_files]

    def delete_conversation_thread(
            self, 
            thread_name : str,
            timeout : Optional[float] = None
    ) -> None:
        """
        Deletes the conversation thread with the given thread ID.

        :param thread_name: The unique name of the thread to delete.
        :type thread_name: str
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: float, optional
        """
        try:
            thread_id = self._thread_config.get_thread_id_by_name(thread_name)
            logger.info(f"Deleting thread with ID: {thread_id}, thread name: {thread_name}")
            self._thread_config.remove_thread_by_id(thread_id)
            self._ai_client.beta.threads.delete(
                thread_id=thread_id,
                timeout=timeout
            )
            logger.info(f"Deleted thread with ID: {thread_id}, thread name: {thread_name}")
        except Exception as e:
            logger.error(f"Failed to delete thread with ID: {thread_id}, thread name: {thread_name}: {e}")
            raise EngineError(f"Failed to delete thread with ID: {thread_id} thread name: {thread_name}: {e}")

    def get_conversation_threads(self) -> list:
        """
        Retrieves all conversation threads.

        :return: The conversation threads.
        :rtype: list
        """
        try:

            # TODO possible to get threads from the AI client
            threads = self._thread_config.get_all_threads()
            return threads
        except Exception as e:
            logger.error(f"Failed to retrieve threads: {e}")
            raise EngineError(f"Failed to retrieve threads: {e}")

    def get_config(self) -> dict:
        """
        Retrieves the threads config.

        :return: The threads config.
        :rtype: dict
        """
        try:
            return self._thread_config
        except Exception as e:
            logger.error(f"Failed to retrieve threads config: {e}")
            raise EngineError(f"Failed to retrieve threads config: {e}")

    def save_conversation_threads(self) -> None:
        """
        Saves the threads to json based on the AI client type.
        """
        logger.info(f"Save threads to json, ai_client_type: {self._ai_client_type}")
        self._thread_config.save_to_json()
