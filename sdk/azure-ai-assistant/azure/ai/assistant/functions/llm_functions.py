# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.ai_client_factory import AIClientFactory, AIClientType
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.attachment import Attachment, AttachmentType
from azure.ai.assistant.management.message import ConversationMessage
from azure.ai.assistant.management.logger_module import logger

from typing import Dict, Any, List
import json, copy, os, uuid


def _initialize_clients(client_type):
    try:
        ai_client = AIClientFactory.get_instance().get_client(client_type)
        thread_client = ConversationThreadClient.get_instance(client_type)
        return ai_client, thread_client
    except Exception as e:
        error_message = f"Failed to initialize AI or thread client: {str(e)}"
        logger.exception(error_message)
        return None, None


def _retrieve_and_parse_conversation(thread_client):
    try:
        thread_config = thread_client.get_config()
        thread_id = thread_config.get_current_thread_id()
        logger.info(f"retrieve_and_parse_conversation, thread_id: {thread_id}")

        thread_name = thread_config.get_thread_name_by_id(thread_id)
        # Retrieve max 10 last text messages from the conversation
        conversation = thread_client.retrieve_conversation(
            thread_name=thread_name, max_text_messages=10
        )
        messages = _parse_text_messages(conversation.messages)
        return messages
    except Exception as e:
        error_message = f"Failed to retrieve or parse conversation: {str(e)}"
        logger.exception(error_message)
        return None


def _generate_chat_completion(ai_client, model, messages):
    logger.info(f"generate_chat_completion, messages: {messages}")
    logger.info(f"generate_chat_completion, model: {model}")

    try:
        # Generate the chat completion
        response = ai_client.chat.completions.create(
            model=model,
            messages=messages
        )
        logger.info(f"generate_chat_completion, response: {response}")

        # Extract the content of the first choice
        if response.choices and response.choices[0].message:
            message_content = response.choices[0].message.content
        else:
            message_content = "No response"

        return json.dumps({"result": message_content})
    except Exception as e:
        error_message = f"Failed to generate chat completion: {str(e)}"
        logger.exception(error_message)
        return json.dumps({"function_error": error_message})


def _update_messages_with_prompt(messages : List[ConversationMessage], prompt):
    updated_messages = copy.deepcopy(messages)
    
    new_message = {
        "role": "user",
        "content": [{"type": "text", "text": prompt}]
    }
    
    if not updated_messages:
        updated_messages.append(new_message)
        return updated_messages
    
    for message in reversed(updated_messages):
        if message.get("role") == "user":
            message["content"] = new_message["content"]
            return updated_messages
    
    # If no user message is found, append the new user message
    updated_messages.append(new_message)
    
    return updated_messages


def _parse_text_messages(messages: List['ConversationMessage']) -> List[Dict[str, Any]]:
    parsed_messages = []
    for message in reversed(messages):
        if message.text_message:
            parsed_messages.append({
                "role": message.role,
                "content": [{"type": "text", "text": message.text_message.content}]
            })
    return parsed_messages


def _create_identifier(prefix: str) -> str:
    short_id = uuid.uuid4().hex[:8]
    return f"{prefix}_{short_id}"


def generate_o1_response(prompt: str, model: str = "o1-mini") -> str:
    """
    Generates a chat completion response for the given prompt using the specified OpenAI model.

    :param prompt: The prompt for which the chat completion is to be generated.
    :type prompt: str
    :param model: The model to be used for generating the chat completion.
    :type model: str

    :return: JSON formatted string containing the result or an error message.
    :rtype: str
    """
    current_client_type = AIClientFactory.get_instance().current_client_type
    ai_client, thread_client = _initialize_clients(current_client_type)
    if not ai_client or not thread_client:
        return json.dumps({"function_error": "Failed to initialize AI or thread client."})

    if model not in ["o1-mini", "o1-preview"]:
        return json.dumps({"function_error": "Invalid model specified."})
    
    messages = _retrieve_and_parse_conversation(thread_client)
    if messages is None:
        return json.dumps({"function_error": "Failed to retrieve or parse conversation."})

    messages = _update_messages_with_prompt(messages, prompt)
    return _generate_chat_completion(ai_client, model, messages)


def take_screenshot() -> str:
    """
    Captures a screenshot and displays it to the user.

    :return: The path to the saved screenshot.
    :rtype: str
    """
    try:
        from PIL import Image
        import mss

        current_client_type = AIClientFactory.get_instance().current_client_type
        ai_client, thread_client = _initialize_clients(current_client_type)
        if not ai_client or not thread_client:
            return json.dumps({"function_error": "Failed to initialize AI or thread client."})

        # capture a screenshot
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # 0 is the first monitor; adjust if multiple monitors are used
            screenshot = sct.grab(monitor)
            img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')

        # Create the output folder if it does not exist
        os.makedirs("output", exist_ok=True)
        # Save the screenshot to the output folder
        file_name = f"{_create_identifier('screenshot')}.png"
        img_path = os.path.join("output", file_name)
        img.save(img_path)
        attachment = Attachment(file_path=img_path, attachment_type=AttachmentType.IMAGE_FILE)
        current_thread_id = thread_client.get_config().get_current_thread_id()
        thread_name = thread_client.get_config().get_thread_name_by_id(current_thread_id)
        thread_client.create_conversation_thread_message(message="Captured screenshot", thread_name=thread_name, attachments=[attachment], metadata={"chat_assistant": "function"})

        return json.dumps({"result": "Screenshot captured and displayed."})
    
    except Exception as e:
        error_message = f"Failed to capture screenshot: {str(e)}"
        logger.exception(error_message)
        return json.dumps({"function_error": error_message})