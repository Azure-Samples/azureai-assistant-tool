# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.ai_client_factory import AIClientFactory, AsyncAIClientType
from azure.ai.assistant.management.attachment import Attachment, AttachmentType
from azure.ai.assistant.management.async_conversation import AsyncConversation
from azure.ai.assistant.management.async_message import AsyncConversationMessage
from azure.ai.assistant.management.conversation_thread_config import ConversationThreadConfig
from azure.ai.assistant.management.message_utils import _extract_image_urls
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.exceptions import EngineError
from azure.ai.assistant.management.logger_module import logger

from openai import AsyncAzureOpenAI, AsyncOpenAI

from openai.types.beta.threads import Message

from typing import Union, List, Optional, Tuple
import threading, asyncio


class AsyncConversationThreadClient:
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
        self._ai_client : Union[AsyncOpenAI, AsyncAzureOpenAI] = AIClientFactory.get_instance().get_client(self._ai_client_type, **client_args)
        self._thread_config = ConversationThreadConfig(self._ai_client_type, self._config_folder)
        self._assistant_config_manager = AssistantConfigManager.get_instance()

    @classmethod
    def get_instance(
        cls, 
        ai_client_type : AsyncAIClientType,
        config_folder : Optional[str] = None,
        **client_args
    ) -> 'AsyncConversationThreadClient':
        """
        Get the singleton instance of the AsyncConversationThreadClient.

        :param ai_client_type: The type of the AI client to use.
        :type ai_client_type: AsyncAIClientType
        :param config_folder: The folder to save the thread config to.
        :type config_folder: str, optional
        :param client_args: The arguments to pass to the AI client.
        :type client_args: dict

        :return: The singleton instance of the AsyncConversationThreadClient.
        :rtype: AsyncConversationThreadClient
        """
        if ai_client_type not in cls._instances:
            with cls._lock:
                if ai_client_type not in cls._instances:
                    instance = cls.__new__(cls)
                    instance.__init_private(ai_client_type, config_folder, **client_args)
                    cls._instances[ai_client_type] = instance
        return cls._instances[ai_client_type]

    async def create_conversation_thread(
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
            thread = await self._ai_client.beta.threads.create(timeout=timeout)
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

    async def _get_conversation_thread_messages(
            self, 
            thread_name : str,
            timeout : Optional[float] = None
    ) -> List[Message]:
        try:
            thread_id = self._thread_config.get_thread_id_by_name(thread_name)
            messages = await self._ai_client.beta.threads.messages.list(
                thread_id=thread_id,
                timeout=timeout
            )
            return messages.data
        except Exception as e:
            logger.error(f"Failed to retrieve thread messages for thread name {thread_name}: {e}")
            raise EngineError(f"Failed to retrieve thread messages or thread name {thread_name}: {e}")

    async def retrieve_conversation(
            self,
            thread_name : str,
            timeout: Optional[float] = None,
            max_text_messages: Optional[int] = None
    ) -> AsyncConversation:
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
            messages = await self._get_conversation_thread_messages(thread_name, timeout)
            logger.info(f"Retrieved messages content: {messages}")
            conversation = await AsyncConversation.create(self._ai_client, messages, max_text_messages)
            return conversation
        except Exception as e:
            error_message = f"Error retrieving messages content: Exception: {e}"
            logger.error(error_message)
            raise EngineError(error_message)

    async def retrieve_message(self, original_message: Message) -> AsyncConversationMessage:
        """
        Retrieves a single conversation message.

        :param original_message: The original message to retrieve.
        :type original_message: Message

        :return: The conversation message.
        :rtype: ConversationMessage
        """
        return await AsyncConversationMessage().create(self._ai_client, original_message)
    
    async def create_conversation_thread_message(
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
            if attachments is not None:
                updated_attachments, image_attachments = await self._update_message_attachments(thread_id, attachments)
            else:
                updated_attachments, image_attachments = [], []

            content = [
                {
                    "type": "text",
                    "text": message
                }
            ]

            image_urls = _extract_image_urls(message)
            for image_url in image_urls:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                        "detail": "high"
                    }
                })

            if image_attachments:
                # Retrieve the conversation to check if the image file is already included
                conversation = await self.retrieve_conversation(thread_name)
                for image_attachment in image_attachments:
                    # if image attachment is not already in the conversation, add it
                    if not conversation.contains_image_file_id(image_attachment.file_id):
                        content.append({
                            "type": "image_file",
                            "image_file": {
                                "file_id": image_attachment.file_id,
                                "detail": "high"
                            }
                        })

            if attachments:
                # Create the message with the attachments
                await self._ai_client.beta.threads.messages.create(
                    thread_id,
                    role=role,
                    metadata=metadata,
                    attachments=updated_attachments,
                    content=content,
                    timeout=timeout
                )
            else:
                # Create the message without attachments
                await self._ai_client.beta.threads.messages.create(
                    thread_id,
                    role=role,
                    metadata=metadata,
                    content=content,
                    timeout=timeout
                )

            logger.info(f"Created message: {message} in thread: {thread_id}, attachments: {attachments}, images: {image_attachments}")
        except Exception as e:
            logger.error(f"Failed to create message: {message} in thread: {thread_id}, files: {attachments}, images: {image_attachments}: {e}")
            raise EngineError(f"Failed to create message: {message} in thread: {thread_id}, files: {attachments}, images: {image_attachments}: {e}")

    async def _update_message_attachments(self, thread_id: str, new_attachments: List[Attachment]) -> Tuple[List[dict], List[Attachment]]:
        try:
            existing_attachments = self._thread_config.get_attachments_of_thread(thread_id)
            existing_attachments_by_id = {att.file_id: att for att in existing_attachments if att.file_id}
            new_file_ids = {att.file_id for att in new_attachments if att.file_id}
            attachments_to_remove = [att for att in existing_attachments if att.file_id not in new_file_ids]

            for attachment in attachments_to_remove:
                self._thread_config.remove_attachment_from_thread(thread_id, attachment.file_id)
                await self._ai_client.files.delete(file_id=attachment.file_id)

            all_updated_attachments = []
            image_attachments = []
            for attachment in new_attachments:
                file_id = attachment.file_id
                file_path = attachment.file_path
                attachment_type = attachment.attachment_type
                tool = attachment.tool

                if file_id is None:
                    if attachment_type == AttachmentType.IMAGE_FILE and tool is None:  # This is a plain image file
                        file_object = await self._ai_client.files.create(file=open(file_path, "rb"), purpose='vision')
                        attachment.file_id = file_object.id
                        image_attachments.append(attachment)
                        self._thread_config.add_attachments_to_thread(thread_id, [attachment])  # Add image attachment to thread config
                    else:  # This is a tool file
                        file_object = await self._ai_client.files.create(file=open(file_path, "rb"), purpose='assistants')
                        attachment.file_id = file_object.id
                        self._thread_config.add_attachments_to_thread(thread_id, [attachment])
                        all_updated_attachments.append(attachment)
                else:
                    current_attachment = existing_attachments_by_id.get(file_id)
                    if current_attachment and current_attachment != attachment:
                        self._thread_config.update_attachment_in_thread(thread_id, current_attachment)
                    if attachment_type == AttachmentType.IMAGE_FILE and tool is None:  # Image file
                        image_attachments.append(current_attachment)
                    else:  # Tool file
                        all_updated_attachments.append(current_attachment)

            self._thread_config.set_attachments_of_thread(thread_id, all_updated_attachments + image_attachments)
            updated_attachments = [{'file_id': att.file_id, 'tools': [att.tool.to_dict()] if att.tool else []} for att in all_updated_attachments]
            return updated_attachments, image_attachments
        except Exception as e:
            logger.error(f"Failed to update attachments for thread {thread_id}: {str(e)}")
            raise

    async def delete_conversation_thread(
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
            await self._ai_client.beta.threads.delete(
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

    async def save_conversation_threads(self) -> None:
        """
        Saves the threads to json based on the AI client type.
        """
        logger.info(f"Save threads to json, ai_client_type: {self._ai_client_type}")
        await asyncio.to_thread(self._thread_config.save_to_json)
    
    async def close(self) -> None:
        """
        Closes the conversation thread client.
        """
        await self._ai_client.close()
        # delete the instance for the AI client type, so that a new instance can be recreated
        del self._instances[self._ai_client_type]