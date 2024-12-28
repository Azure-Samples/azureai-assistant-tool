from azure.ai.assistant.audio.realtime_audio import RealtimeAudio
from azure.ai.assistant.management.realtime_assistant_client import RealtimeAssistantClient
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.message import ConversationMessage

import threading

assistant_name = "ASSISTANT_NAME"

class RealtimeAssistantEventHandler(AssistantClientCallbacks):

    def __init__(self, response_event : threading.Event = None):
        self._realtime_audio = None
        self._response_event = response_event

    def set_realtime_audio(self, realtime_audio: RealtimeAudio):
        self._realtime_audio = realtime_audio

    def on_connected(self, assistant_name, assistant_type, thread_name):
        pass

    def on_disconnected(self, assistant_name, assistant_type):
        pass

    def on_run_start(self, assistant_name, run_identifier, run_start_time, user_input):
        pass

    def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message=False, message : ConversationMessage = None):
        if run_status == "streaming":
            if is_first_message:
                print(f"{assistant_name}: {message.text_message.content}", end="")
            else:
                print(message.text_message.content, end="", flush=True)

    def on_run_end(self, assistant_name, run_identifier, run_end_time, thread_name, response=None):
        self._response_event.set()

    def on_run_failed(self, assistant_name, run_identifier, run_end_time, error_code, error_message, thread_name):
        print(f"Run {run_identifier} failed at {run_end_time} with error: {error_code} - {error_message}")
    
    def on_run_audio_data(self, assistant_name, run_identifier, audio_data):
        self._realtime_audio.audio_player.enqueue_audio_data(audio_data)


# open assistant configuration file
try:
    with open(f"config/{assistant_name}_assistant_config.yaml", "r") as file:
        config = file.read()
except FileNotFoundError:
    print(f"Configuration file for {assistant_name} not found.")
    exit(1)

# create event for response
response_event = threading.Event()

# create realtime assistant client
realtime_event_handler = RealtimeAssistantEventHandler(response_event=response_event)
assistant_client : RealtimeAssistantClient = RealtimeAssistantClient.from_yaml(config_yaml=config, callbacks=realtime_event_handler)

# create a new conversation thread client
conversation_thread_client = ConversationThreadClient.get_instance(ai_client_type=assistant_client.ai_client_type)
thread_name = conversation_thread_client.create_conversation_thread()

# create realtime audio instance
realtime_audio = RealtimeAudio(realtime_client=assistant_client)
realtime_event_handler.set_realtime_audio(realtime_audio)

# start realtime audio and assistant client
realtime_audio.start()
assistant_client.start(thread_name=thread_name)

while True:
    # Accept user input
    user_message = input("user: ")
    if user_message.lower() == 'exit':  # Allow the user to exit the chat
        print("Exiting chat.")
        break

    # Process the user messages
    assistant_client.generate_response(user_input=user_message)

    # wait for response
    response_event.wait()
    response_event.clear()

    # add new line for better readability
    print()

# stop realtime audio and assistant client
realtime_audio.stop()
assistant_client.stop()