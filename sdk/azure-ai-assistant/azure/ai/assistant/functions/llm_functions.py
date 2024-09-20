# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.ai_client_factory import AIClientFactory, AIClientType
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.message import ConversationMessage
from azure.ai.assistant.management.logger_module import logger

from typing import Dict, Any, List
import json


def _parse_text_messages(messages: List['ConversationMessage']) -> List[Dict[str, Any]]:
    parsed_messages = []
    for message in reversed(messages):
        if message.text_message:
            parsed_messages.append({
                "role": message.role,
                "content": [{"type": "text", "text": message.text_message.content}]
            })
    return parsed_messages


def get_openai_chat_completion(prompt: str, model: str) -> str:
    """
    Generates a chat completion for the given prompt using the specified model.

    :param prompt: The prompt for which the chat completion is to be generated.
    :type prompt: str
    :param model: The model to be used for generating the chat completion.
    :type model: str

    :return: JSON formatted string containing the result or an error message.
    :rtype: str
    """

    # Initialize AI client and thread client
    try:
        ai_client = AIClientFactory.get_instance().get_client(AIClientType.OPEN_AI)
        thread_client = ConversationThreadClient.get_instance(AIClientType.OPEN_AI)
    except Exception:
        error_message = "Failed to initialize AI or thread client."
        logger.exception(error_message)
        return json.dumps({"function_error": error_message})

    # Retrieve conversation messages from the current thread
    try:
        thread_config = thread_client.get_config()
        thread_id = thread_config.get_current_thread_id()
        logger.info(f"get_openai_chat_completion, thread_id: {thread_id}")

        thread_name = thread_config.get_thread_name_by_id(thread_id)
        conversation = thread_client.retrieve_conversation(
            thread_name=thread_name, max_text_messages=10
        )
        messages = _parse_text_messages(conversation.messages)
    except Exception:
        error_message = "Failed to retrieve or parse conversation."
        logger.exception(error_message)
        return json.dumps({"function_error": error_message})

    # replace the last user message with the prompt
    messages[-1] = {"role": "user", "content": [{"type": "text", "text": prompt}]}

    logger.info(f"get_openai_chat_completion, messages: {messages}")
    logger.info(f"get_openai_chat_completion, model: {model}")

    # Generate the chat completion
    try:
        response = ai_client.chat.completions.create(
            model=model,
            messages=messages
        )
        logger.info(f"get_openai_chat_completion, response: {response}")

        # Extract the content of the first choice
        if response.choices and response.choices[0].message:
            message_content = response.choices[0].message.content
        else:
            message_content = "No response"

        return json.dumps({"result": message_content})
    except Exception as e:
        error_message = "Failed to generate chat completion."
        logger.exception(error_message)
        return json.dumps({"function_error": str(e)})