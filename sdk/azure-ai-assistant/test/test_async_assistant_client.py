# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import pytest
import json
import os

from azure.ai.assistant.management.async_assistant_client import AsyncAssistantClient
from azure.ai.assistant.management.async_conversation_thread_client import AsyncConversationThreadClient
from azure.ai.assistant.management.ai_client_factory import AsyncAIClientType
from azure.ai.assistant.management.attachment import Attachment, AttachmentType
from test_assistant_client import generate_test_config
from test_assistant_client import RESOURCES_PATH


@pytest.mark.asyncio
async def test_async_assistant_client_from_json():
    config = generate_test_config()
    config_json = json.dumps(config)

    client = await AsyncAssistantClient.from_json(config_json)
    assert client.name == "assistant_test"
    assert client._ai_client_type == AsyncAIClientType.OPEN_AI
    assert client._ai_client is not None
    assert client._callbacks is not None
    assert client._functions == {}
    await client.purge()

@pytest.mark.asyncio
async def test_async_assistant_client_sync_from_cloud():
    config = generate_test_config()
    config_json = json.dumps(config)

    client = await AsyncAssistantClient.from_json(config_json)
    client = await client.sync_from_cloud()
    assert client.name == "assistant_test"
    assert client._ai_client_type == AsyncAIClientType.OPEN_AI
    assert client._ai_client is not None
    assert client._callbacks is not None
    assert client._functions == {}
    await client.purge()

@pytest.mark.asyncio
async def test_async_assistant_client_update():
    config = generate_test_config()
    config_json = json.dumps(config)

    client = await AsyncAssistantClient.from_json(config_json)
    client.assistant_config.instructions = "these are updated instructions"
    config_json = client.assistant_config.to_json()

    client = await AsyncAssistantClient.from_json(config_json)
    assert client.assistant_config.instructions == "these are updated instructions"
    await client.purge()

@pytest.mark.asyncio
async def test_async_assistant_client_purge():
    config = generate_test_config()
    config_json = json.dumps(config)

    client = await AsyncAssistantClient.from_json(config_json)
    await client.purge()

@pytest.mark.asyncio
async def test_async_assistant_client_add_fetch_current_datetime_function():
    updates = {
        "functions": [
            {
                "type": "function",
                "function": {
                    "name": "fetch_current_datetime",
                    "module": "azure.ai.assistant.functions.file_functions",
                    "description": "Get the current time as a JSON string.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
        ]
    }

    config = generate_test_config(updates)
    config_json = json.dumps(config)
    client = await AsyncAssistantClient.from_json(config_json)
    client = await client.sync_from_cloud()
    assert len(client.assistant_config.functions) == 1
    assert client.assistant_config.functions[0]['function']['name'] == "fetch_current_datetime"
    await client.purge()

@pytest.mark.asyncio
async def test_async_assistant_client_create_thread_and_process_message():
    config = generate_test_config()
    config_json = json.dumps(config)

    client = await AsyncAssistantClient.from_json(config_json)
    thread_client = AsyncConversationThreadClient.get_instance(AsyncAIClientType.OPEN_AI)
    thread_name = await thread_client.create_conversation_thread()
    await thread_client.create_conversation_thread_message("Hello!", thread_name)
    await client.process_messages(thread_name)
    conversation = await thread_client.retrieve_conversation(thread_name)
    last_message = conversation.get_last_text_message(client.assistant_config.name)
    assert last_message is not None
    await client.purge()
    await thread_client.close()

@pytest.mark.asyncio
async def test_async_assistant_client_create_thread_and_process_message_with_attachment():
    config = generate_test_config()
    config_json = json.dumps(config)

    client = await AsyncAssistantClient.from_json(config_json)
    thread_client = AsyncConversationThreadClient.get_instance(AsyncAIClientType.OPEN_AI)
    thread_name = await thread_client.create_conversation_thread()
    attachment = Attachment(file_path=str(RESOURCES_PATH / "scenery.png"), attachment_type=AttachmentType.IMAGE_FILE)
    await thread_client.create_conversation_thread_message(message="What is in the picture?", thread_name=thread_name, attachments=[attachment])
    await client.process_messages(thread_name)
    conversation = await thread_client.retrieve_conversation(thread_name)
    last_message = conversation.get_last_text_message(client.assistant_config.name)
    assert last_message is not None
    await client.purge()
    await thread_client.close()

@pytest.mark.asyncio
async def test_assistant_client_create_thread_and_process_message_with_multi_image():
    config = generate_test_config()
    config_json = json.dumps(config)

    client = await AsyncAssistantClient.from_json(config_json)
    thread_client = AsyncConversationThreadClient.get_instance(AsyncAIClientType.OPEN_AI)
    thread_name = await thread_client.create_conversation_thread()
    attachment1 = Attachment(file_path=str(RESOURCES_PATH / "scenery.png"), attachment_type=AttachmentType.IMAGE_FILE)
    attachment2 = Attachment(file_path=str(RESOURCES_PATH / "scenery.png"), attachment_type=AttachmentType.IMAGE_FILE)
    await thread_client.create_conversation_thread_message(message="What is in the picture?", thread_name=thread_name, attachments=[attachment1, attachment2])
    await client.process_messages(thread_name)
    conversation = await thread_client.retrieve_conversation(thread_name)
    last_message = conversation.get_last_message("user")
    assert last_message is not None
    assert last_message.image_messages is not None
    assert len(last_message.image_messages) == 2
    assert last_message.image_messages[0].file_id is not None
    assert conversation.contains_image_file_id(last_message.image_messages[0].file_id)
    assert last_message.image_messages[1].file_id is not None
    assert conversation.contains_image_file_id(last_message.image_messages[1].file_id)
    
    await client.purge()
    await thread_client.close()
