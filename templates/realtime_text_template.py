import threading
import os

from azure.ai.assistant.audio.realtime_audio import RealtimeAudio
from azure.ai.assistant.management.realtime_assistant_client import RealtimeAssistantClient
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.message import ConversationMessage


ASSISTANT_NAME = "ASSISTANT_NAME"
CONFIG_DIR = "config"


class RealtimeAssistantEventHandler(AssistantClientCallbacks):
    """
    Handles callbacks from the RealtimeAssistantClient, printing relevant events
    and streaming the assistant's audio responses.
    """

    def __init__(self, response_event: threading.Event = None):
        """
        :param response_event: An event that signals when the assistant has finished responding.
        """
        super().__init__()
        self._realtime_audio = None
        self._response_event = response_event

    def set_realtime_audio(self, realtime_audio: RealtimeAudio):
        """
        Sets the RealtimeAudio instance for streaming audio.

        :param realtime_audio: The RealtimeAudio instance to handle audio data.
        """
        self._realtime_audio = realtime_audio

    def on_connected(self, assistant_name, assistant_type, thread_name):
        pass

    def on_disconnected(self, assistant_name, assistant_type):
        pass

    def on_run_start(self, assistant_name, run_identifier, run_start_time, user_input):
        pass

    def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message=False, message: ConversationMessage = None):
        """
        Handles partial streaming responses. If this is the first message of a response,
        print the assistant's name and the prompt. Otherwise, just print any updates.
        """
        if run_status == "streaming" and message and message.text_message and message.text_message.content:
            if is_first_message:
                print(f"{assistant_name}: {message.text_message.content}", end="", flush=True)
            else:
                print(message.text_message.content, end="", flush=True)

    def on_run_end(self, assistant_name, run_identifier, run_end_time, thread_name, response=None):
        if self._response_event:
            self._response_event.set()

    def on_run_failed(self, assistant_name, run_identifier, run_end_time, error_code, error_message, thread_name):
        print(f"Run {run_identifier} failed at {run_end_time} with error: {error_code} - {error_message}")
        if self._response_event:
            self._response_event.set()

    def on_run_audio_data(self, assistant_name, run_identifier, audio_data):
        """
        Streams audio data to the RealtimeAudio player as it's received.
        """
        if self._realtime_audio and self._realtime_audio.audio_player:
            self._realtime_audio.audio_player.enqueue_audio_data(audio_data)
        else:
            print("WARNING: RealtimeAudio or AudioPlayer not set. Cannot enqueue audio data.")


def main():
    """
    Main function to run the realtime assistant. Initializes required objects,
    starts the assistant, and handles user inputs.
    """
    config_path = os.path.join(CONFIG_DIR, f"{ASSISTANT_NAME}_assistant_config.yaml")

    # Open assistant configuration file
    if not os.path.isfile(config_path):
        print(f"ERROR: Configuration file for {ASSISTANT_NAME} not found at {config_path}.")
        return

    with open(config_path, "r", encoding="utf-8") as file:
        config_yaml = file.read()

    # Create event for response signaling
    response_event = threading.Event()

    # Create the realtime assistant client
    realtime_event_handler = RealtimeAssistantEventHandler(response_event=response_event)
    assistant_client: RealtimeAssistantClient = RealtimeAssistantClient.from_yaml(
        config_yaml=config_yaml,
        callbacks=realtime_event_handler
    )

    # Create a new conversation thread client and start a new thread
    conversation_thread_client = ConversationThreadClient.get_instance(ai_client_type=assistant_client.ai_client_type)
    thread_name = conversation_thread_client.create_conversation_thread()

    # Create a RealtimeAudio instance and associate it with the event handler
    realtime_audio = RealtimeAudio(realtime_client=assistant_client)
    realtime_event_handler.set_realtime_audio(realtime_audio)

    # Start realtime audio and assistant client
    realtime_audio.start()
    assistant_client.start(thread_name=thread_name)

    print("Realtime assistant started. Type 'exit' to quit.\n")

    try:
        while True:
            # Accept user input
            user_message = input("user: ")
            if user_message.lower() == 'exit':
                print("Exiting chat.")
                break

            # Send user input to assistant
            assistant_client.generate_response(user_input=user_message)

            # Wait until a response has been processed
            response_event.wait()
            response_event.clear()

            # Print a newline for readability
            print()
    except KeyboardInterrupt:
        print("Keyboard interruption detected; exiting.")
    finally:
        # Stop realtime audio and assistant client
        realtime_audio.stop()
        assistant_client.stop()
        print("Realtime assistant stopped.")


if __name__ == "__main__":
    main()
