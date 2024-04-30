from azure.ai.assistant.management.async_assistant_client import AsyncAssistantClient
from azure.ai.assistant.management.ai_client_factory import AsyncAIClientType
from azure.ai.assistant.management.async_conversation_thread_client import AsyncConversationThreadClient

import asyncio


async def main():

    assistant_name = "ASSISTANT_NAME"

    # open assistant configuration file
    try:
        with open(f"config/{assistant_name}_assistant_config.yaml", "r") as file:
            config = file.read()
    except FileNotFoundError:
        print(f"Configuration file for {assistant_name} not found.")
        exit(1)

    # retrieve the assistant client
    assistant_client = await AsyncAssistantClient.from_yaml(config)

    # create a new conversation thread client
    ai_client_type = AsyncAIClientType[assistant_client.assistant_config.ai_client_type]
    conversation_thread_client = AsyncConversationThreadClient.get_instance(ai_client_type)

    # create a new conversation thread
    thread_name = await conversation_thread_client.create_conversation_thread()

    while True:
        # Accept user input
        user_message = input("user: ")
        if user_message.lower() == 'exit':  # Allow the user to exit the chat
            print("Exiting chat.")
            break

        # Create a message to the conversation thread
        await conversation_thread_client.create_conversation_thread_message(user_message, thread_name)

        # Process the user messages
        await assistant_client.process_messages(thread_name=thread_name)

        # Retrieve the conversation
        conversation = await conversation_thread_client.retrieve_conversation(thread_name)

        # Print the last assistant response from the conversation
        assistant_message = conversation.get_last_text_message(assistant_client.name)
        print(f"{assistant_message.sender}: {assistant_message.content}")

        # add new line for better readability
        print()

if __name__ == "__main__":
    asyncio.run(main())