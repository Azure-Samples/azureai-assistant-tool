# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.message import TextMessage, FileMessage, ImageMessage
from azure.ai.assistant.management.ai_client_factory import AIClientType
from typing import Optional


class Conversation:
    """
    A class representing a conversation.

    :param ai_client_type: The type of AI client to use for the conversation.
    :type ai_client_type: AIClientType
    """
    def __init__(
            self, 
            ai_client_type : AIClientType
    ) -> None:
        self._messages = []
        self._ai_client_type = ai_client_type

    @property
    def text_messages(self) -> list[TextMessage]:
        """
        Returns the list of text messages in the conversation.

        :return: The list of text messages in the conversation.
        :rtype: list[TextMessage]
        """
        return [msg for msg in self._messages if msg.type == "text"]

    @property
    def messages(self) -> list:
        """
        Returns the list of all messages in the conversation.

        :return: The list of all messages in the conversation.
        :rtype: list
        """
        return self._messages

    def get_last_text_message(
            self, 
            sender : str
    ) -> Optional[TextMessage]:
        """
        Returns the last text message sent by the assistant.

        :param sender: The name of the sender.
        :type sender: str

        :return: The last text message sent by the assistant.
        :rtype: Optional[TextMessage]
        """
        for msg in self.text_messages:
            if msg.sender == sender:
                return msg
        return None

    def get_new_text_messages(
            self, 
            previous_conversation : 'Conversation'
    ) -> list[TextMessage]:
        """
        Compares the current conversation's text messages with those of a previous conversation instance
        and returns the new messages that were added since the previous state.

        :param previous_conversation: The previous conversation instance.
        :type previous_conversation: Conversation

        :return: The new text messages that were added since the previous state.
        :rtype: list[TextMessage]
        """
        previous_messages_set = set(map(str, previous_conversation.text_messages))
        new_messages = [msg for msg in self.text_messages if str(msg) not in previous_messages_set]
        return new_messages

    def add_message(
            self, 
            text : str,
            role : str,
            sender : str
    ) -> None:
        """
        Adds a text message to the conversation.

        :param text: The text of the message.
        :type text: str
        :param role: The role of the sender.
        :type role: str
        :param sender: The name of the sender.
        :type sender: str
        """
        self._messages.append(TextMessage(text, self._ai_client_type, role, sender))

    def add_file(
            self, 
            file_id : str,
            file_name : str,
            role : str,
            sender : str
    ) -> None:
        """
        Adds a file message to the conversation.

        :param file_id: The ID of the file.
        :type file_id: str
        :param file_name: The name of the file.
        :type file_name: str
        :param role: The role of the sender.
        :type role: str
        :param sender: The name of the sender.
        :type sender: str
        """
        self._messages.append(FileMessage(file_id, file_name, self._ai_client_type, role, sender))

    def add_image(
            self, 
            file_id : str,
            file_name : str,
            role : str,
            sender : str
    ) -> None:
        """
        Adds an image message to the conversation.

        :param file_id: The ID of the image file.
        :type file_id: str
        :param file_name: The name of the image file.
        :type file_name: str
        :param role: The role of the sender.
        :type role: str
        :param sender: The name of the sender.
        :type sender: str
        """
        self._messages.append(ImageMessage(file_id, file_name, self._ai_client_type, role, sender))