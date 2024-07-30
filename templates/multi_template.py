import threading
from typing import Dict
from azure.ai.assistant.management.assistant_client import AssistantClient
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.message import TextMessage, FileMessage, ImageMessage
from azure.ai.assistant.management.ai_client_factory import AIClientType
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.task_manager import TaskManager, TaskManagerCallbacks, MultiTask


assistant_names = ["ASSISTANT_NAME1", "ASSISTANT_NAME2"]

class MultiAgentOrchestrator(TaskManagerCallbacks, AssistantClientCallbacks):
    def __init__(self, assistant_names, ai_client_type : AIClientType):
        self.task_completion_events = {}
        self.assistants: Dict[str, AssistantClient] = {}
        self.init_assistants(assistant_names)
        self.conversation_thread_client = ConversationThreadClient.get_instance(ai_client_type)
        super().__init__()

    def init_assistants(self, assistant_names):
        # create assistant clients from configuration files
        for assistant_name in assistant_names:
            try:
                with open(f"config/{assistant_name}_assistant_config.yaml", "r") as file:
                    config = file.read()
                    self.assistants[assistant_name] = AssistantClient.from_yaml(config, callbacks=self)
            except Exception as e:
                raise Exception(f"Error loading assistant configuration for {assistant_name}: {e}")

    def on_task_started(self, task : MultiTask, schedule_id):
        print(f"Task {task.id} started with schedule ID: {schedule_id}")
        self.task_completion_events[schedule_id] = threading.Event()
        self.thread_name = self.conversation_thread_client.create_conversation_thread()

    def on_task_execute(self, task : MultiTask, schedule_id):
        print(f"Task {task.id} execute with schedule ID: {schedule_id}")
        for request in task.requests:
            assistant_name = request["assistant"]
            assistant_client = self.assistants[assistant_name]
            self.conversation_thread_client.create_conversation_thread_message(request["task"], self.thread_name)
            assistant_client.process_messages(self.thread_name)
            conversation = self.conversation_thread_client.retrieve_conversation(self.thread_name)
            for message in reversed(conversation.messages):
                if message.text_message:
                    if message.sender == assistant_name:
                        print(f"{message.sender}: {message.text_message.content}")
                if len(message.file_messages) > 0:
                    for file_message in message.file_messages:
                        print(f"{message.sender}: provided file {file_message.file_name}")
                        file_message.retrieve_file(assistant_client.assistant_config.output_folder_path)
                if len(message.image_messages) > 0:
                    for image_message in message.image_messages:
                        print(f"{message.sender}: provided image {image_message.file_name}")
                        image_message.retrieve_image(assistant_client.assistant_config.output_folder_path)

    def on_task_completed(self, task : MultiTask, schedule_id, result):
        print(f"Task {task.id} completed with schedule ID: {schedule_id}. Result: {result}")
        event = self.task_completion_events.get(schedule_id)
        if event:
            event.set()
    
    def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message=False, message=None):
        if run_status == "in_progress":
            print(".", end="", flush=True)
        elif run_status == "completed":
            print(f"\n{assistant_name}: run {run_identifier} completed")

    def on_function_call_processed(self, assistant_name, run_identifier, function_name, arguments, response):
        print(f"\nFunction call {function_name} with arguments {arguments} processed by {assistant_name}")

    def wait_for_all_tasks(self):
        for event in self.task_completion_events.values():
            event.wait()

# Create multi agent orchestration, assumed that all assistants are of AZURE_OPEN_AI type
orchestrator = MultiAgentOrchestrator(assistant_names, AIClientType.AZURE_OPEN_AI)
task_manager = TaskManager(orchestrator)
tasks = [
    {
        "assistant": assistant_names[0],
        "task": "Convert main.py file in current folder to idiomatic Java implementation and create converted file in the output folder. Inform the full path of converted file at the end"
    },
    {
        "assistant": assistant_names[1],
        "task": "Review the converted Java file and inform about missing implementations and any improvements needed"
    },
    {
        "assistant": assistant_names[0],
        "task": "Implement the missing functionalities and create new file with updates in the output folder with the changes. Inform the full path of the new file at the end"
    }
]
multi_task = MultiTask(tasks)
task_manager.schedule_task(multi_task)
orchestrator.wait_for_all_tasks()
