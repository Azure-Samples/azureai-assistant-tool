# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from typing import Any
import azure.identity.aio

from quart import Blueprint, jsonify, request, Response, render_template, current_app

import asyncio
import json, os

import os
from azure.ai.client.aio import AzureAIClient
from azure.identity import DefaultAzureCredential

from azure.ai.client.models import (
    AgentEventHandler,
    MessageDeltaTextContent,
    MessageDeltaChunk,
    ThreadMessage,
    ThreadRun,
    RunStep,
)


bp = Blueprint("chat", __name__, template_folder="templates", static_folder="static")

# Assuming your files are stored in the 'files' directory at the project root
file_id_map = {
    "product_info_1.md": "product_info_1.md",
    "product_info_2.md": "product_info_2.md",
}

user_queues = {}

class MyEventHandler(AgentEventHandler):
    def __init__(self, message_queue):
        super().__init__()
        self.message_queue = message_queue
            
    async def on_message_delta(self, delta: "MessageDeltaChunk") -> None:
        for content_part in delta.delta.content:
            if isinstance(content_part, MessageDeltaTextContent):
                text_value = content_part.text.value if content_part.text else "No text"
                print(f"Text delta received: {text_value}")
                await self.message_queue.put(("message", text_value))
                

    async def on_thread_message(self, message: "ThreadMessage") -> None:
        print(f"ThreadMessage created. ID: {message.id}, Status: {message.status}")
        # if (message.status == "completed"):
        #     await self.message_queue.put(("completed_message", ""))
        # return

    async def on_thread_run(self, run: "ThreadRun") -> None:
        print(f"ThreadRun status: {run.status}")

    async def on_run_step(self, step: "RunStep") -> None:
        print(f"RunStep type: {step.type}, Status: {step.status}")

    async def on_error(self, data: str) -> None:
        print(f"An error occurred. Data: {data}")

    async def on_done(self) -> None:
        print("Stream completed.")
        await self.message_queue.put(("stream_end", ""))

    async def on_unhandled_event(self, event_type: str, event_data: Any) -> None:
        print(f"Unhandled Event Type: {event_type}, Data: {event_data}")


    def on_unhandled_event(self, event_type: str, event_data: Any) -> None:
        print(f"Unhandled Event Type: {event_type}, Data: {event_data}")

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
    # config = await read_config("file_search")
    # client_args = {}
    ai_client = AzureAIClient.from_connection_string(
        credential=DefaultAzureCredential(),
        conn_str=os.environ["PROJECT_CONNECTION_STRING"],
    )


    agent = await ai_client.agents.create_agent(
        model="gpt-4-1106-preview", name="my-assistant", instructions="You are helpful assistant"
    )

    print(f"Created agent, agent ID: {agent.id}")

    thread = await ai_client.agents.create_thread()
    print(f"Created thread, thread ID {thread.id}")
    
    bp.ai_client = ai_client
    bp.agent = agent
    bp.thread = thread
    
    user_queues[thread.id] = asyncio.Queue()   

@bp.after_app_serving
async def shutdown_assistant_client():
    await bp.ai_client.agents.delete_agent(bp.agent.id)
    await bp.ai_client.close()

@bp.get("/")
async def index():
    return await render_template("index.html")

@bp.post("/chat")
async def start_chat():
    user_message = await request.get_json()
    if not hasattr(bp, 'ai_client'):
        return jsonify({"error": "Agent is not initialized"}), 500

    if not hasattr(bp, 'thread'):
        return jsonify({"error": "Conversation thread is not initialized"}), 500

    message = await bp.ai_client.agents.create_message(
        thread_id=bp.thread.id, role="user", content=user_message['message']
    )
    print(f"Created message, message ID {message.id}")


    return jsonify({"thread_id": bp.thread.id, "message": "Processing started"}), 200


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

@bp.route('/stream/<thread_id>', methods=['GET'])
async def stream_responses(thread_id: str):
    # Set necessary headers for SSE
    headers = {
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'text/event-stream'
    }

    async with await bp.ai_client.agents.create_stream(
        thread_id=bp.thread.id, assistant_id=bp.agent.id, event_handler=MyEventHandler(user_queues.get(bp.thread.id))
    ) as stream:
        await stream.until_done()

    current_app.logger.info(f"Stream request received for thread ID: {thread_id}")

    if thread_id != bp.thread.id:
        current_app.logger.error(f"Invalid thread ID: {thread_id} does not match {bp.thread.id}")
        return jsonify({"error": "Invalid thread ID"}), 404

    message_queue = user_queues.get(thread_id)
    if not message_queue:
        current_app.logger.error(f"No active session found for thread: {thread_id}")
        return jsonify({"error": "No active session for this thread"}), 404

    current_app.logger.info(f"Starting to stream events for thread: {thread_id}")

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