# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.ai_client_factory import AIClientFactory, AIClientType
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.attachment import Attachment, AttachmentType
from azure.ai.assistant.management.message import ConversationMessage
from azure.ai.assistant.management.logger_module import logger

from typing import Dict, Any, List
import json, copy, os, uuid, base64, io


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


def _analyze_image(img_base64: str, system_input: str, user_input: str) -> str:
    """
    Analyzes the given image and returns the analysis result.

    :param img_base64 (str): Base64 encoded image data.
    :param system_input (str): System input for the analysis.
    :param user_input (str): User input for the analysis.
    :return: The analysis result.
    :rtype: str
    """

    try:
        current_client_type = AIClientFactory.get_instance().current_client_type
        ai_client, thread_client = _initialize_clients(current_client_type)
    except Exception as e:
        error_message = f"Failed to initialize AI or thread client: {str(e)}"
        print(error_message)
        return json.dumps({"function_error": error_message})
    
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": system_input
                }
            ],
            "role": "user",
            "content": [
                {
                    "type": "text", 
                    "text": user_input
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}",
                        "detail": "high"
                    }
                },
            ],
        }
    ]

    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.1,
            max_tokens=2000
        )
        
        # Extract the analysis result from the response
        analysis = response.choices[0].message.content
        return json.dumps({"result": analysis})
    
    except Exception as e:
        error_message = f"An error occurred: {e}"
        print(error_message)
        return json.dumps({"function_error": error_message})


def _screenshot_to_bytes() -> bytes:
    """
    Captures a screenshot and returns it as binary data.

    :return: The screenshot as binary data.
    :rtype: bytes
    """
    try:
        from PIL import Image
    except ImportError:
        return json.dumps({"function_error": "Missing module 'Pillow'. Please install it using `pip install Pillow`."})

    try:
        import mss
    except ImportError:
        return json.dumps({"function_error": "Missing module 'mss'. Please install it using `pip install mss`."})

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            screenshot = sct.grab(monitor)
            img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
        
        # Convert the image to binary data
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        img_bytes = img_byte_arr.read()
        return img_bytes

    except mss.exception.ScreenShotError as e:
        error_message = "Failed to capture screenshot due to a screen capture error."
        logger.error(f"{error_message} Details: {e}")
        return json.dumps({"function_error": error_message})
    except Exception as e:
        error_message = f"Failed to capture screenshot: {str(e)}"
        logger.exception(error_message)
        return json.dumps({"function_error": error_message})


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


def look_at_screen(focus_topic: str) -> str:
    """
    Analyze the current screen by capturing a screenshot and returning an analysis of it. The analysis focuses on highlighted areas if present.

    :param focus_topic: The topic to focus on in the analysis.
    :type focus_topic: str
    :return: The analysis result as a JSON string.
    :rtype: str
    """    
    # Capture a screenshot and convert it to base64
    img_bytes = _screenshot_to_bytes()
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")

     # Save the screenshot to the output folder
    #file_name = f"{_create_identifier('screenshot')}.png"
    #img_path = os.path.join("output", file_name)
    #with open(img_path, "wb") as img_file:
    #    img_file.write(img_bytes)
    print(f"look_at_screen, focus_topic: {focus_topic}")
    return _analyze_image(img_base64=img_base64, 
                          system_input="You are an AI assistant analyzing a screenshot. Some portions may be highlighted. If a highlight is described or detected, focus your analysis primarily on that portion, ignoring the rest unless it is needed for context. If no highlights are described, provide a general overview of what’s in the image.", 
                          user_input=f"Analyze the screenshot, focusing on all highlighted areas in {focus_topic}.")


def take_screenshot() -> str:
    """
    Captures a screenshot and displays it to the user.

    :return: The path to the saved screenshot.
    :rtype: str
    """
     # Attempt to dynamically import required modules
    try:
        from PIL import Image
    except ImportError:
        return json.dumps({"function_error": "Missing module 'Pillow'. Please install it using `pip install Pillow`."})

    try:
        import mss
    except ImportError:
        return json.dumps({"function_error": "Missing module 'mss'. Please install it using `pip install mss`."})
    
    try:
        current_client_type = AIClientFactory.get_instance().current_client_type
        ai_client, thread_client = _initialize_clients(current_client_type)
        if not ai_client or not thread_client:
            return json.dumps({"function_error": "Failed to initialize AI or thread client."})

        # capture a screenshot
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            screenshot = sct.grab(monitor)
            img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')

        # Create the output folder if it does not exist
        output_dir = os.path.abspath("output")
        os.makedirs(output_dir, exist_ok=True)

        # Save the screenshot to the output folder
        file_name = f"{_create_identifier('screenshot')}.png"
        img_path = os.path.join(output_dir, file_name)
        img.save(img_path)

        attachment = Attachment(file_path=img_path, attachment_type=AttachmentType.IMAGE_FILE)
        current_thread_id = thread_client.get_config().get_current_thread_id()
        thread_name = thread_client.get_config().get_thread_name_by_id(current_thread_id)
        thread_client.create_conversation_thread_message(
            message="Captured screenshot",
            thread_name=thread_name,
            attachments=[attachment],
            metadata={"chat_assistant": "function"}
        )

        return json.dumps({"result": "Screenshot captured and displayed."})
    
    except mss.exception.ScreenShotError as e:
        error_message = "Failed to capture screenshot due to a screen capture error."
        logger.error(f"{error_message} Details: {e}")
        return json.dumps({"function_error": error_message})
    
    except Exception as e:
        error_message = f"Failed to capture screenshot: {str(e)}"
        logger.exception(error_message)
        return json.dumps({"function_error": error_message})