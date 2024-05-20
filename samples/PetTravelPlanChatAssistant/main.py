# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.async_chat_assistant_client import AsyncChatAssistantClient
from azure.ai.assistant.management.ai_client_factory import AsyncAIClientType
from azure.ai.assistant.management.async_assistant_client_callbacks import AsyncAssistantClientCallbacks
from azure.ai.assistant.management.async_conversation_thread_client import AsyncConversationThreadClient
from azure.ai.assistant.management.async_message import AsyncConversationMessage
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.text_message import TextMessage

import os, asyncio, yaml
import azure.identity.aio


# Define a custom callback class that inherits from AssistantClientCallbacks
class MyAssistantClientCallbacks(AsyncAssistantClientCallbacks):
    def __init__(self, message_queue):
        self.message_queue = message_queue

    async def handle_message(self, action, message=""):
        await self.message_queue.put((action, message))

    async def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message=False, message : AsyncConversationMessage = None):
        if run_status == "streaming":
            await self.handle_message("start" if is_first_message else "message", message.text_message.content)
        elif run_status == "completed":
            if message:
                text_message : TextMessage = message.text_message
                if text_message.file_citations:
                    for file_citation in text_message.file_citations:
                        print(f"\nFile citation, file_id: {file_citation.file_id}, file_name: {file_citation.file_name}")

    async def on_run_end(self, assistant_name, run_identifier, run_end_time, thread_name, response=None):
        pass

    async def on_function_call_processed(self, assistant_name, run_identifier, function_name, arguments, response):
        await self.handle_message("function", function_name)


# Define a function to display streamed messages
async def display_streamed_messages(message_queue, assistant_name):
    while True:
        message_type, message = await message_queue.get()
        if message_type == "start":
            # At the start of a new message, include the assistant's name.
            print(f"{assistant_name}: {message}", end="")
        elif message_type == "message":
            # Print the streamed part of the message; `flush=True` ensures it's immediately displayed
            print(message, end="", flush=True)
        elif message_type == "function":
            # Print assistant's name and calling the function on the new line
            print(f"{assistant_name}: called {message} function.")
        message_queue.task_done()


async def get_client_args(ai_client_type : str):
    try:
        client_args = {}
        if ai_client_type == "AZURE_OPEN_AI":
            if os.getenv("AZURE_OPENAI_API_KEY"):
                # Authenticate using an Azure OpenAI API key
                # This is generally discouraged, but is provided for developers
                # that want to develop locally inside the Docker container.
                print("Using Azure OpenAI with key")
                client_args["api_key"] = os.getenv("AZURE_OPENAI_API_KEY")
            else:
                # Authenticate using the default Azure credential chain
                # See https://docs.microsoft.com/azure/developer/python/azure-sdk-authenticate#defaultazurecredential
                # This will *not* work inside a Docker container.
                print("Using Azure OpenAI with default credential")
                default_credential = azure.identity.aio.DefaultAzureCredential(
                    exclude_shared_token_cache_credential=True
                )
                client_args["azure_ad_token_provider"] = azure.identity.aio.get_bearer_token_provider(
                    default_credential, "https://cognitiveservices.azure.com/.default"
                )
        elif ai_client_type == "OPEN_AI":
            # Authenticate using an OpenAI API key
            if os.getenv("OPENAI_API_KEY"):
                print("Using OpenAI with key")
                client_args["api_key"] = os.getenv("OPENAI_API_KEY")
            else:
                raise Exception("OpenAI API key not found.")
        return client_args
    except Exception as e:
        print(f"An error occurred: {e}")
        return {}

async def main():

    assistant_name = "PetTravelPlanChatAssistant"
    try:
        with open(f"config/{assistant_name}_assistant_config.yaml", "r") as file:
            config = yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Configuration file for {assistant_name} not found.")
        return

    try:
        client_args = await get_client_args(config["ai_client_type"])
        # Create a message queue to store streamed messages and a custom callback class
        message_queue = asyncio.Queue()
        callbacks = MyAssistantClientCallbacks(message_queue)

        # Use the AssistantConfigManager to save the assistant configuration locally at the end of the session
        assistant_config_manager = AssistantConfigManager.get_instance('config')

        # Create an instance of the AsyncChatAssistantClient
        assistant_client = await AsyncChatAssistantClient.from_yaml(yaml.dump(config), callbacks=callbacks, **client_args)
        ai_client_type = AsyncAIClientType[assistant_client.assistant_config.ai_client_type]

        print(f"Starting chat with {assistant_client.ai_client} assistant.")
        # Create an instance of the AsyncConversationThreadClient
        conversation_thread_client = AsyncConversationThreadClient.get_instance(ai_client_type)

        # Create a new conversation thread
        thread_name = await conversation_thread_client.create_conversation_thread()

        # Create a task to display streamed messages
        display_task = asyncio.create_task(display_streamed_messages(message_queue, assistant_name))

        while True:
            user_message = input("user: ").strip()
            if user_message.lower() == 'exit':
                print("Exiting chat.")
                break

            # Create a new message in the conversation thread
            await conversation_thread_client.create_conversation_thread_message(user_message, thread_name)

            # Process messages in the conversation thread
            await assistant_client.process_messages(thread_name=thread_name, stream=True)

            print() # Add a newline for better readability

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await message_queue.join()
        display_task.cancel()
        await conversation_thread_client.close()
        assistant_config_manager.save_config(assistant_client.name)

if __name__ == "__main__":
    asyncio.run(main())

