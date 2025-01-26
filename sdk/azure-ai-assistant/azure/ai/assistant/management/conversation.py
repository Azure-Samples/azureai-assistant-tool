# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.message import ConversationMessage, TextMessage, ImageMessage
from azure.ai.assistant.management.ai_client_factory import AIClient

from openai.types.beta.threads import Message

from typing import Optional, List


class Conversation:
    """
    A class representing a conversation.

    :param ai_client: The AI client (OpenAI, AzureOpenAI, or AIProjectClient).
    :type ai_client: AIClient
    :param messages: The list of messages in the conversation.
    :type messages: List[Message]
    :param max_text_messages: The maximum number of text messages to include in the conversation.
    :type max_text_messages: Optional[int]

    :return: A new instance of the Conversation class.
    :rtype: Conversation
    """
    def __init__(
            self, 
            ai_client : AIClient,
            messages: List[Message], 
            max_text_messages: Optional[int] = None
    ) -> None:
        self._messages = [ConversationMessage(ai_client, message) for message in messages]
        if max_text_messages is not None:
            self._messages = self._messages[:max_text_messages]

    @property
    def messages(self) -> List[ConversationMessage]:
        """
        Returns the list of messages in the conversation.

        :return: The list of messages in the conversation.
        :rtype: List[ConversationMessage]
        """
        return self._messages

    def get_last_message(self, sender: str) -> ConversationMessage:
        """
        Returns the last message in the conversation from the specified sender.

        :param sender: The sender of the message.
        :type sender: str

        :return: The last message in the conversation from the specified sender.
        :rtype: ConversationMessage
        """
        for message in (self._messages):
            if message.sender == sender:
                return message
        return None
    
    @property
    def text_messages(self) -> List[TextMessage]:
        """
        Returns the list of text message contents in the conversation.

        :return: The list of text message contents in the conversation.
        :rtype: List[TextMessage]
        """
        return [message.text_message for message in self._messages if message.text_message is not None]
    
    def get_last_text_message(self, sender: str) -> TextMessage:
        """
        Returns the last text message content in the conversation from the specified sender.

        :param sender: The sender of the message.
        :type sender: str
        :return: The last text message content in the conversation from the specified sender.
        :rtype: TextMessage
        """
        for message in (self._messages):
            if message.sender == sender and message.text_message is not None:
                return message.text_message
        return None
    
    def contains_file_id(self, file_id: str) -> bool:
        """
        Checks if the list of file messages contains a specific file ID.

        :param file_id: The file ID to check.
        :type file_id: str
        :return: True if the file ID is found, False otherwise.
        :rtype: bool
        """
        image_files_contains = any(image_message.file_id == file_id for message in self.messages for image_message in message.image_messages if image_message is not None)
        files_contains = any(file_message.file_id == file_id for message in self.messages for file_message in message.file_messages if file_message is not None)
        return image_files_contains or files_contains