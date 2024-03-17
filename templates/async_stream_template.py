import json
import asyncio
from azure.ai.assistant.management.async_assistant_client import AsyncAssistantClient
from azure.ai.assistant.management.ai_client_factory import AsyncAIClientType
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.async_conversation_thread_client import AsyncConversationThreadClient


# Define a custom callback class that inherits from AssistantClientCallbacks
class MyAssistantClientCallbacks(AssistantClientCallbacks):
    def __init__(self, message_queue):
        self.message_queue = message_queue

    def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message=False, message=None):
        if run_status == "streaming":
            if is_first_message:
                # Indicate the start of a new message
                asyncio.create_task(self.message_queue.put(("start", "")))
            if message is not None:
                asyncio.create_task(self.message_queue.put(("message", message)))

    def on_run_end(self, assistant_name, run_identifier, run_end_time, thread_name):
        asyncio.create_task(self.message_queue.put(("end", "")))


# Define a function to display streamed messages
async def display_streamed_messages(message_queue, assistant_name):
    while True:
        message_type, message = await message_queue.get()

        if message_type == "start":
            # Print the assistant's name only at the beginning of a new streamed message
            print(f"{assistant_name}: ", end="")
        elif message_type == "message":
            # Print the streamed part of the message; `flush=True` ensures it's immediately displayed
            print(message, end="", flush=True)
        elif message_type == "end":
            # When the message ends, ensure to print a newline to cleanly separate from the next prompt
            print()  # This ensures there's always a newline after the assistant's response

        message_queue.task_done()


assistant_name = "ASSISTANT_NAME"

# Define the main function
async def main():
    # Open assistant configuration file
    try:
        with open(f"config/{assistant_name}_assistant_config.json", "r") as file:
            config_json = json.load(file)
        ai_client_type = AsyncAIClientType[config_json["ai_client_type"]]
        message_queue = asyncio.Queue()
        callbacks = MyAssistantClientCallbacks(message_queue)
    except FileNotFoundError:
        print(f"Configuration file for {assistant_name} not found.")
        return
    except KeyError:
        print(f"AI client type not found in the configuration file for {assistant_name}.")
        return

    # Retrieve the assistant client
    assistant_client = await AsyncAssistantClient.from_json(json.dumps(config_json), callbacks=callbacks)

    # Create a new conversation thread client
    conversation_thread_client = AsyncConversationThreadClient.get_instance(ai_client_type)

    # Create a new conversation thread
    thread_name = await conversation_thread_client.create_conversation_thread()

    display_task = asyncio.create_task(display_streamed_messages(message_queue, assistant_name))

    while True:
        try:
            user_message = input("user: ")
            if user_message.lower() == 'exit':  # Allow the user to exit the chat
                print("Exiting chat.")
                break

            # Create a message to the conversation thread
            await conversation_thread_client.create_conversation_thread_message(user_message, thread_name)

            # Process the user messages (await the asynchronous call)
            await assistant_client.process_messages(thread_name=thread_name, stream=True)

            print()  # Add a newline for better readability

        except Exception as e:
            print(f"An error occurred: {e}")
            break

    # Cleanup before exiting
    await message_queue.join()  # Ensure all messages are processed
    display_task.cancel()  # Cleanly cancel the display task
    await conversation_thread_client.close()

# Note that we run the main function using asyncio.run() since main is async
if __name__ == "__main__":
    asyncio.run(main())
