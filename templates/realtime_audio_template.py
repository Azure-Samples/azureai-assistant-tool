import threading
import os

from azure.ai.assistant.audio.realtime_audio import RealtimeAudio
from azure.ai.assistant.management.realtime_assistant_client import RealtimeAssistantClient
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.message import ConversationMessage

ASSISTANT_NAME = "ASSISTANT_NAME"


class RealtimeAssistantEventHandler(AssistantClientCallbacks):
    """
    A custom event handler for the RealtimeAssistantClient that prints status updates
    and handles streaming audio data from the assistant.
    """

    def __init__(self, response_event: threading.Event = None):
        """
        :param response_event: Event used to signal when the assistant run has ended.
        """
        super().__init__()
        self._realtime_audio = None
        self._response_event = response_event

    def set_realtime_audio(self, realtime_audio: RealtimeAudio):
        """
        Associates a RealtimeAudio instance with this event handler for streaming audio data.

        :param realtime_audio: The RealtimeAudio instance used to process assistant audio.
        """
        self._realtime_audio = realtime_audio

    def on_connected(self, assistant_name, assistant_type, thread_name):
        """
        Called when successfully connected to the assistant.
        """
        pass

    def on_disconnected(self, assistant_name, assistant_type):
        """
        Called when disconnected from the assistant.
        """
        pass

    def on_run_start(self, assistant_name, run_identifier, run_start_time, user_input):
        """
        Called at the start of a run (assistant processing user input).
        """
        pass

    def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message=False, message: ConversationMessage = None):
        """
        Called when there's progress on the run. Streams partial text output as it's received.
        """
        if run_status == "streaming":
            # Print the assistant's name and the first chunk of text, then partial updates
            if is_first_message:
                print(f"\n{assistant_name}: {message.text_message.content}", end="")
            else:
                print(message.text_message.content, end="", flush=True)

    def on_run_end(self, assistant_name, run_identifier, run_end_time, thread_name, response=None):
        """
        Called when a run finishes successfully.
        """
        # Signal that the assistant run has ended
        if self._response_event is not None:
            self._response_event.set()

    def on_run_failed(self, assistant_name, run_identifier, run_end_time, error_code, error_message, thread_name):
        """
        Called when a run fails.
        """
        print(f"Run {run_identifier} failed at {run_end_time} with error: {error_code} - {error_message}")
        # Signal that the assistant run has ended (even though it failed)
        if self._response_event is not None:
            self._response_event.set()

    def on_run_audio_data(self, assistant_name, run_identifier, audio_data):
        """
        Called when audio data is received from the assistant. 
        Enqueues the data for playback via the RealtimeAudio player.
        """
        if self._realtime_audio and self._realtime_audio.audio_player:
            self._realtime_audio.audio_player.enqueue_audio_data(audio_data)
        else:
            print("Could not process audio data: RealtimeAudio or its audio_player is not set.")


def main():
    """
    Main function to set up and run the RealtimeAssistantClient demo with a single
    response cycle. Extend or customize this for your full application logic.
    """
    config_file_path = os.path.join("config", f"{ASSISTANT_NAME}_assistant_config.yaml")

    # Open assistant configuration file
    if not os.path.isfile(config_file_path):
        print(f"Configuration file for {ASSISTANT_NAME} not found at {config_file_path}.")
        return

    with open(config_file_path, "r") as file:
        config = file.read()

    # Create an event used to wait for the assistant's response
    response_event = threading.Event()

    # Create the event handler with the response event
    realtime_event_handler = RealtimeAssistantEventHandler(response_event=response_event)

    # Create the RealtimeAssistantClient from YAML config
    assistant_client: RealtimeAssistantClient = RealtimeAssistantClient.from_yaml(
        config_yaml=config,
        callbacks=realtime_event_handler
    )

    # Create a conversation thread client and initiate a new thread
    conversation_thread_client = ConversationThreadClient.get_instance(ai_client_type=assistant_client.ai_client_type)
    thread_name = conversation_thread_client.create_conversation_thread()

    # Create a RealtimeAudio instance and bind it to the event handler
    realtime_audio = RealtimeAudio(realtime_client=assistant_client)
    realtime_event_handler.set_realtime_audio(realtime_audio)

    # Start the RealtimeAudio and assistant client
    realtime_audio.start()
    assistant_client.start(thread_name=thread_name)

    print("Starting chat, say `Computer` to start the conversation.")

    try:
        # Wait for the assistant to complete a single response cycle
        response_event.wait()
        response_event.clear()
    except KeyboardInterrupt:
        print("User interrupted the process.")
    finally:
        # Stop the RealtimeAudio and assistant client
        realtime_audio.stop()
        assistant_client.stop()


if __name__ == "__main__":
    main()