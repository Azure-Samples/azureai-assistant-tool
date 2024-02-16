# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from openai import OpenAI
from azure.ai.assistant.management.logger_module import logger

instructions = [{"role": "system", "content": "You are tasked to create title of \
                 given text by finding the overall theme. The title must be only \
                 3 words long at max. Returning more than 3 words will be a failure.\n"}]


class ConversationTitleCreator:
    """
    A class to create a title for a conversation thread.

    :param client: The OpenAI client.
    :type client: OpenAI
    :param model: The model to use for creating the title.
    :type model: str
    """
    def __init__(
            self, 
            client : OpenAI, 
            model: str
    ) -> None:
        self.client = client
        self.model = model

    def get_thread_title(self, text) -> str:
        """
        Get the title for a conversation thread.

        :param text: The text to create a title for.
        :type text: str

        :return: The title for the conversation thread.
        :rtype: str
        """
        try:
            messages = instructions
            logger.info("Creating 3 word title from the following text: \n" + text)
            request = "Please return 3 word title from the following text: \n" + text
            messages.append({"role": "user", "content": request})
            response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )
            title = response.choices[0].message.content
            # remove quotes from response if there are any
            title = title.replace('"', '')
            logger.info("ConversationTitleCreator, response: " + title)
            return title
        except Exception as e:
            logger.error("Error: " + str(e))
            return "New Thread"