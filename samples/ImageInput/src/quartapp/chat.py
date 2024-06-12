# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.async_assistant_client import AsyncAssistantClient
from azure.ai.assistant.management.ai_client_factory import AsyncAIClientType
from azure.ai.assistant.management.async_assistant_client_callbacks import AsyncAssistantClientCallbacks
from azure.ai.assistant.management.async_conversation_thread_client import AsyncConversationThreadClient
from azure.ai.assistant.management.async_message import AsyncConversationMessage
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
import azure.identity.aio

from quart import Blueprint, jsonify, request, Response, render_template, current_app, formparser

import asyncio
import json, os


bp = Blueprint("chat", __name__, template_folder="templates", static_folder="static")

# Assuming your files are stored in the 'files' directory at the project root
file_id_map = {
    "product_info_1.md": "product_info_1.md",
    "product_info_2.md": "product_info_2.md",
}

user_queues = {}

class MyAssistantClientCallbacks(AsyncAssistantClientCallbacks):
    def __init__(self, message_queue):
        super().__init__()
        self.message_queue = message_queue

    async def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message=False, message : AsyncConversationMessage = None):
        if run_status == "streaming":
            text_message_content = message.text_message.content
            current_app.logger.info(f"Stream message: {text_message_content}")
            await self.message_queue.put(("message", text_message_content))
        elif run_status == "completed":
            current_app.logger.info("run status completed")
            text_message = message.text_message
            current_app.logger.info(f"message.text_message.content: {text_message.content}")
            if text_message.file_citations:
                for file_citation in text_message.file_citations:
                    current_app.logger.info(f"\nFile citation, file_id: {file_citation.file_id}, file_name: {file_citation.file_name}")
            await self.message_queue.put(("completed_message", text_message.content))

    async def on_run_end(self, assistant_name, run_identifier, run_end_time, thread_name, response=None):
        await self.message_queue.put(("stream_end", ""))

    async def on_function_call_processed(self, assistant_name, run_identifier, function_name, arguments, response):
        #await self.message_queue.put(("function", function_name))
        pass

async def read_config(assistant_name):
    config_path = f"config/{assistant_name}_assistant_config.yaml"
    try:
        # Attempt to read the configuration file
        current_app.logger.info(f"Reading assistant configuration from {config_path}")
        with open(config_path, "r") as file:
            content = file.read()
            return content
    except FileNotFoundError as e:
        current_app.logger.error(f"Configuration file not found at {config_path}: {e}")
        return None
    except Exception as e:
        current_app.logger.error(f"An error occurred: {e}")
        return None

@bp.before_app_serving
async def configure_assistant_client():
    config = await read_config("file_search")
    client_args = {}
    if config:
        if os.getenv("OPENAI_API_KEY"):
            current_app.logger.info("Using OpenAI API key")
            client_args["api_key"] = os.getenv("OPENAI_API_KEY")
        else:
            os.environ['AZURE_OPENAI_API_VERSION'] = '2024-05-01-preview'
            if os.getenv("AZURE_OPENAI_API_KEY"):
                # Authenticate using an Azure OpenAI API key
                # This is generally discouraged, but is provided for developers
                # that want to develop locally inside the Docker container.
                current_app.logger.info("Using Azure OpenAI with key")
                client_args["api_key"] = os.getenv("AZURE_OPENAI_API_KEY")
            else:
                if client_id := os.getenv("AZURE_OPENAI_CLIENT_ID"):
                    # Authenticate using a user-assigned managed identity on Azure
                    # See aca.bicep for value of AZURE_OPENAI_CLIENT_ID
                    current_app.logger.info(
                        "Using Azure OpenAI with managed identity for client ID %s",
                        client_id,
                    )
                    default_credential = azure.identity.aio.ManagedIdentityCredential(client_id=client_id)
                else:
                    # Authenticate using the default Azure credential chain
                    # See https://docs.microsoft.com/azure/developer/python/azure-sdk-authenticate#defaultazurecredential
                    # This will *not* work inside a Docker container.
                    current_app.logger.info("Using Azure OpenAI with default credential")
                    default_credential = azure.identity.aio.DefaultAzureCredential(
                        exclude_shared_token_cache_credential=True
                    )
                client_args["azure_ad_token_provider"] = azure.identity.aio.get_bearer_token_provider(
                    default_credential, "https://cognitiveservices.azure.com/.default"
                )

        # Create an instance of the AssistantConfigManager to save the updated assistant configuration to config folder once assistant client is initialized
        assistant_config_manager = AssistantConfigManager.get_instance('config')

        # Create a new message queue for this session
        message_queue = asyncio.Queue()
        
        # Initialize callbacks with the created message queue
        callbacks = MyAssistantClientCallbacks(message_queue)

        api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        current_app.logger.info(f"Initializing AsyncAssistantClient with callbacks, api_version: {api_version}")

        bp.assistant_client = await AsyncAssistantClient.from_yaml(config, callbacks=callbacks, **client_args)

        current_app.logger.info(f"Assistant client id: {bp.assistant_client.assistant_config.assistant_id}")
        current_app.logger.info(f"Assistant tool resources: {bp.assistant_client.assistant_config.tool_resources.to_dict()}")

        # Save the assistant configuration to the config folder
        assistant_config_manager.save_config(bp.assistant_client.name)

        ai_client_type = AsyncAIClientType[bp.assistant_client.assistant_config.ai_client_type]
        bp.conversation_thread_client = AsyncConversationThreadClient.get_instance(ai_client_type)
        
        # Create a new conversation thread and store its name
        bp.thread_name = await bp.conversation_thread_client.create_conversation_thread()
        current_app.logger.info(f"Conversation thread created with name: {bp.thread_name}")

        # Store the message queue for this thread name in the global dictionary
        user_queues[bp.thread_name] = message_queue
    else:
        current_app.logger.error("Assistant configuration not found")
        raise FileNotFoundError("Assistant configuration not found")

@bp.after_app_serving
async def shutdown_assistant_client():
    if hasattr(bp, 'conversation_thread_client'):
        await bp.conversation_thread_client.close()
        current_app.logger.info("AsyncChatAssistantClient has been closed")

@bp.get("/")
async def index():
    return await render_template("index.html")

@bp.post("/chat")
async def start_chat():
    user_message = await request.form
    current_app.logger.info(f"User message: {user_message}")
    user_files = await request.files
    current_app.logger.info(f"User files: {user_files}")

    if not hasattr(bp, 'assistant_client'):
        return jsonify({"error": "Assistant client is not initialized"}), 500

    if not hasattr(bp, 'thread_name'):
        return jsonify({"error": "Conversation thread is not initialized"}), 500

    # Send user message to the conversation thread
    await bp.conversation_thread_client.create_conversation_thread_message(user_message['message'], bp.thread_name)
    # Process messages in the background, do not await here
    asyncio.create_task(
        bp.assistant_client.process_messages(thread_name=bp.thread_name, stream=True)
    )

    return jsonify({"thread_name": bp.thread_name, "message": "Processing started"}), 200

@bp.route('/fetch-document', methods=['GET'])
async def fetch_document():
    filename = request.args.get('filename')
    current_app.logger.info(f"Fetching document: {filename}")
    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    # Get the file path from the mapping
    file_path = file_id_map.get(filename)
    if not file_path:
        return jsonify({"error": f"No file found for filename: {filename}"}), 404

    # Construct the full path to the file
    full_path = os.path.join('files', file_path)

    if not os.path.exists(full_path):
        return jsonify({"error": f"File not found: {filename}"}), 404

    try:
        # Read the file content asynchronously using asyncio.to_thread
        data = await asyncio.to_thread(read_file, full_path)
        return Response(data, content_type='text/plain')

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def read_file(path):
    with open(path, 'r') as file:
        return file.read()

@bp.route('/stream/<thread_name>', methods=['GET'])
async def stream_responses(thread_name):
    # Set necessary headers for SSE
    headers = {
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'text/event-stream'
    }

    current_app.logger.info(f"Stream request received for thread: {thread_name}")

    if thread_name != bp.thread_name:
        current_app.logger.error(f"Invalid thread name: {thread_name} does not match {bp.thread_name}")
        return jsonify({"error": "Invalid thread name"}), 404

    message_queue = user_queues.get(thread_name)
    if not message_queue:
        current_app.logger.error(f"No active session found for thread: {thread_name}")
        return jsonify({"error": "No active session for this thread"}), 404

    current_app.logger.info(f"Starting to stream events for thread: {thread_name}")

    async def event_stream():
        try:
            while True:
                message_type, message = await message_queue.get()

                if message_type == "message":
                    event_data = json.dumps({'content': message, 'type': message_type})
                    yield f"data: {event_data}\n\n"
                elif message_type == "completed_message":
                    event_data = json.dumps({'content': message, 'type': message_type})
                    yield f"data: {event_data}\n\n"
                elif message_type == "stream_end":
                    event_data = json.dumps({'content': message, 'type': message_type})
                    yield f"data: {event_data}\n\n"
                    return
                elif message_type == "function":
                    function_message = f"Function {message} called"
                    event_data = json.dumps({'content': function_message})
                    yield f"data: {event_data}\n\n"

                message_queue.task_done()

        except asyncio.CancelledError:
            raise
        except Exception as e:
            raise
        finally:
            pass

    return Response(event_stream(), headers=headers)