# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.async_message import AsyncConversationMessage, TextMessageContent

from openai.types.beta.threads import Message
from openai import AsyncAzureOpenAI, AsyncOpenAI

from typing import Optional, List, Union
import asyncio


class AsyncConversation:
    """
    A class representing a conversation asynchronously.

    :param ai_client: The type of AI client to use for the conversation.
    :type ai_client: AsyncOpenAI, AsyncAzureOpenAI
    """
    def __init__(self) -> None:
        self._messages = []
    
    @classmethod
    async def create(
            cls, 
            ai_client: Union['AsyncOpenAI', 'AsyncAzureOpenAI'],
            messages: List['Message'], 
            max_text_messages: Optional[int] = None
    ) -> 'AsyncConversation':
        # Create an instance
        instance = cls()
        
        # Asynchronously initialize messages
        tasks = [AsyncConversationMessage.create(ai_client, message) for message in messages]
        instance._messages = await asyncio.gather(*tasks)
        
        if max_text_messages is not None:
            instance._messages = instance._messages[:max_text_messages]

        return instance

    @property
    def messages(self) -> List['AsyncConversationMessage']:
        return self._messages

    async def get_last_message(self, sender: str) -> 'AsyncConversationMessage':
        for message in reversed(self._messages):
            if message.sender == sender:
                return message
        return None
    
    @property
    def text_messages(self) -> List['TextMessageContent']:
        """
        Returns the list of text message contents in the conversation.

        :return: The list of text message contents in the conversation.
        :rtype: List[TextMessageContent]
        """
        return [message.text_message_content for message in self._messages if message.text_message_content is not None]
    
    async def get_last_text_message(self, sender: str) -> 'TextMessageContent':
        """
        Returns the last text message content in the conversation from the specified sender.

        :param sender: The sender of the message.
        :type sender: str
        :return: The last text message content in the conversation from the specified sender.
        :rtype: TextMessageContent
        """
        for message in reversed(self._messages):
            if message.sender == sender and message.text_message_content is not None:
                return message.text_message_content
        return None
