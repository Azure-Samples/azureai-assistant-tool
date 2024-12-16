from azure.ai.assistant.audio.realtime_audio import RealtimeAudio
from azure.ai.assistant.management.realtime_assistant_client import RealtimeAssistantClient
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks


assistant_name = "ASSISTANT_NAME"

class RealtimeAssistantEventHandler(AssistantClientCallbacks):

    def set_realtime_audio(self, realtime_audio: RealtimeAudio):
        self._realtime_audio = realtime_audio

    def on_connected(self, assistant_name, assistant_type, thread_name):
        print(f"Assistant {assistant_name} connected to thread {thread_name}.")

    def on_disconnected(self, assistant_name, assistant_type):
        print(f"Assistant {assistant_name} disconnected.")

    def on_run_start(self, assistant_name, run_identifier, run_start_time, user_input):
        print(f"Run {run_identifier} started at {run_start_time} with input: {user_input}")

    def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message=False, message=None):
        print(f"Run {run_identifier} updated with status: {run_status}")

    def on_run_end(self, assistant_name, run_identifier, run_end_time, thread_name, response=None):
        print(f"Run {run_identifier} ended at {run_end_time} with response: {response}")

    def on_run_failed(self, assistant_name, run_identifier, run_end_time, error_code, error_message, thread_name):
        print(f"Run {run_identifier} failed at {run_end_time} with error: {error_code} - {error_message}")
    
    def on_run_audio_data(self, assistant_name, run_identifier, audio_data):
        print(f"Run {run_identifier} received audio data.")
        self._realtime_audio.audio_player.enqueue_audio_data(audio_data)


# open assistant configuration file
try:
    with open(f"config/{assistant_name}_assistant_config.yaml", "r") as file:
        config = file.read()
except FileNotFoundError:
    print(f"Configuration file for {assistant_name} not found.")
    exit(1)

# create realtime assistant client
assistant_client_callbacks = RealtimeAssistantEventHandler()
assistant_client : RealtimeAssistantClient = RealtimeAssistantClient.from_yaml(config_yaml=config, callbacks=assistant_client_callbacks)

# create realtime audio instance
realtime_audio = RealtimeAudio(realtime_client=assistant_client)
assistant_client.callbacks.set_realtime_audio(realtime_audio)
realtime_audio.start()

while True:
    # Accept user input
    user_message = input("user: ")
    if user_message.lower() == 'exit':  # Allow the user to exit the chat
        print("Exiting chat.")
        break

    # Process the user messages
    assistant_client.generate_response(user_input=user_message)

    # add new line for better readability
    print()

# stop realtime audio
realtime_audio.stop()