# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.message import ConversationMessage, TextMessage

from openai.types.beta.threads import Message
from openai import AzureOpenAI, OpenAI

from typing import Optional, List, Union


class Conversation:
    """
    A class representing a conversation.

    :param ai_client: The type of AI client to use for the conversation.
    :type ai_client: OpenAI, AzureOpenAI
    :param messages: The list of messages in the conversation.
    :type messages: List[Message]
    :param max_text_messages: The maximum number of text messages to include in the conversation.
    :type max_text_messages: Optional[int]

    :return: A new instance of the Conversation class.
    :rtype: Conversation
    """
    def __init__(
            self, 
            ai_client : Union[OpenAI, AzureOpenAI],
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