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
from openai.types.beta.threads import Message, FileCitationAnnotation, FilePathAnnotation
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
    :param config_folder: The folder to save the thread config to.
    :type config_folder: str, optional
    :param client_args: The arguments to pass to the AI client.
    :type client_args: dict
    """
    def __init_private(
            self, 
            ai_client_type, 
            config_folder : Optional[str] = None,
            **client_args
    ):
        self._ai_client_type = ai_client_type
        self._config_folder = config_folder
        self._ai_client : Union[OpenAI, AzureOpenAI] = AIClientFactory.get_instance().get_client(self._ai_client_type, **client_args)
        self._thread_config = ConversationThreadConfig(self._ai_client_type, self._config_folder)
        self._assistant_config_manager = AssistantConfigManager.get_instance()

    @classmethod
    def get_instance(
        cls, 
        ai_client_type : AIClientType,
        config_folder : Optional[str] = None,
        **client_args
    ) -> 'ConversationThreadClient':
        """
        Get the singleton instance of the ConversationThreadClient.

        :param ai_client_type: The type of the AI client to use.
        :type ai_client_type: AIClientType
        :param config_folder: The folder to save the thread config to.
        :type config_folder: str, optional
        :param client_args: The arguments to pass to the AI client.
        :type client_args: dict

        :return: The singleton instance of the ConversationThreadClient.
        :rtype: ConversationThreadClient
        """
        if ai_client_type not in cls._instances:
            with cls._lock:
                if ai_client_type not in cls._instances:
                    instance = cls.__new__(cls)
                    instance.__init_private(ai_client_type, config_folder, **client_args)
                    cls._instances[ai_client_type] = instance
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
            elif message.role == "user":
                if message.metadata:
                    sender_name = message.metadata.get("chat_assistant", "assistant")
                    message.role = "assistant"
                else:
                    sender_name = "user"

            for content_item in message.content:
                if isinstance(content_item, TextContentBlock):
                    if max_text_messages is not None and text_messages_count >= max_text_messages:
                        return conversation

                    citations = []
                    if content_item.text.annotations:
                        for index, annotation in enumerate(content_item.text.annotations):
                            # Replace the text with a footnote marker
                            content_item.text.value = content_item.text.value.replace(annotation.text, f' [{index}]')
                            
                            # Handle file path annotations
                            if isinstance(annotation, FilePathAnnotation):
                                file_id = annotation.file_path.file_id
                                file_name = annotation.text.split("/")[-1]
                                conversation.add_file(file_id, file_name, message.role, sender_name)
                                citations.append(f'[{index}] {file_name}')

                            # Handle file citation annotations
                            elif isinstance(annotation, FileCitationAnnotation):
                                file_id = annotation.file_citation.file_id
                                try:
                                    file_name = self._ai_client.files.retrieve(file_id).filename
                                except Exception as e:
                                    logger.error(f"Failed to retrieve filename for file_id {file_id}: {e}")
                                    file_name = "Unknown_" + str(file_id)
                                citations.append(f'[{index}] {file_name}')

                    # Append citations at the end of the text content
                    if citations:
                        content_item.text.value += '\n' + '\n'.join(citations)

                    conversation.add_message(content_item.text.value, message.role, sender_name)
                    text_messages_count += 1

                elif isinstance(content_item, ImageFileContentBlock):
                    file_id = content_item.image_file.file_id
                    file_name = f"{file_id}.png"  # Assuming file type is currently always png for images
                    conversation.add_image(file_id, file_name, message.role, sender_name)

        return conversation

    def create_conversation_thread_message(
            self, 
            message : str,
            thread_name : str,
            role : Optional[str] = "user",
            attachments : Optional[list] = None,
            timeout : Optional[float] = None,
            metadata : Optional[dict] = None
    ) -> None:
        """
        Creates a new assistant thread message.

        :param message: The message to create.
        :type message: str
        :param thread_name: The unique name of the thread to create the message in.
        :type thread_name: str
        :param role: The role of the message sender. Default is "user".
        :type role: str, optional
        :param attachments: The list of attachments to add to the message.
        :type attachments: list, optional
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: float, optional
        """
        try:

            # Handle file updates and get file IDs
            thread_id = self._thread_config.get_thread_id_by_name(thread_name)
            attachments = self._update_message_attachments(thread_id, attachments) if attachments is not None else []

            if attachments:
                # Create the message with the attachments
                self._ai_client.beta.threads.messages.create(
                    thread_id,
                    role=role,
                    metadata=metadata,
                    attachments=attachments,
                    content=message,
                    timeout=timeout
                )
            else:
                # Create the message without attachments
                self._ai_client.beta.threads.messages.create(
                    thread_id,
                    role=role,
                    metadata=metadata,
                    content=message,
                    timeout=timeout
                )

            logger.info(f"Created message: {message} in thread: {thread_id}, attachments: {attachments}")
        except Exception as e:
            logger.error(f"Failed to create message: {message} in thread: {thread_id}, files: {attachments}: {e}")
            raise EngineError(f"Failed to create message: {message} in thread: {thread_id}, files: {attachments}: {e}")

    def _update_message_attachments(self, thread_id: str, new_attachments: list):
        try:
            existing_attachments = self._thread_config.get_attachments_of_thread(thread_id)
            existing_attachments_by_id = {att['file_id']: att for att in existing_attachments if att['file_id']}
            new_file_ids = {att['file_id'] for att in new_attachments if att['file_id']}
            attachments_to_remove = [att for att in existing_attachments if att['file_id'] not in new_file_ids]

            for attachment in attachments_to_remove:
                self._thread_config.remove_attachment_from_thread(thread_id, attachment['file_id'])
                self._ai_client.files.delete(file_id=attachment['file_id'])

            all_updated_attachments = []
            for attachment in new_attachments:
                file_name = attachment['file_name']
                file_id = attachment.get('file_id')
                file_path = attachment.get('file_path')
                tools = attachment.get('tools', [])

                if file_id is None:
                    file_object = self._ai_client.files.create(file=open(file_path, "rb"), purpose='assistants')
                    new_attachment = {'file_name': file_name, 'file_id': file_object.id, 'file_path': file_path, 'tools': tools}
                    self._thread_config.add_attachments_to_thread(thread_id, [new_attachment])
                    all_updated_attachments.append(new_attachment)
                else:
                    current_attachment = existing_attachments_by_id.get(file_id, {})
                    if not current_attachment or current_attachment['tools'] != tools:
                        current_attachment['tools'] = tools
                        self._thread_config.update_attachment_in_thread(thread_id, current_attachment)
                    all_updated_attachments.append(current_attachment)

            self._thread_config.set_attachments_of_thread(thread_id, all_updated_attachments)
            updated_attachments = [{'file_id': att['file_id'], 'tools': att['tools']} for att in all_updated_attachments]
            return updated_attachments
        except Exception as e:
            logger.error(f"Failed to update attachments for thread {thread_id}: {str(e)}")
            raise

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

    def get_config(self) -> ConversationThreadConfig:
        """
        Retrieves the threads config.

        :return: The threads config.
        :rtype: ConversationThreadConfig
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
