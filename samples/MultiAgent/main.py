from azure.ai.assistant.management.assistant_client import AssistantClient
from azure.ai.assistant.management.chat_assistant_client import ChatAssistantClient
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.message import TextMessage, FileMessage, ImageMessage
from azure.ai.assistant.management.ai_client_factory import AIClientType
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.task_manager import TaskManager, TaskManagerCallbacks, MultiTask

import threading
from threading import Condition
from typing import Dict, List
import json, re


def load_assistant_config(assistant_name: str) -> Dict:
    """
    Loads the YAML configuration for a given assistant.
    """
    try:
        with open(f"config/{assistant_name}_assistant_config.yaml", "r") as file:
            return file.read()
    except Exception as e:
        print(f"Error loading assistant configuration for {assistant_name}: {e}")
        return None


def initialize_assistants(assistant_names: List[str], callback_provider) -> Dict[str, AssistantClient]:
    """
    Initializes all assistants based on their names and configuration files.
    """
    assistants = {}
    for assistant_name in assistant_names:
        config = load_assistant_config(assistant_name)
        if config:
            if assistant_name == "TaskPlannerAgent":
                assistants[assistant_name] = ChatAssistantClient.from_yaml(config, callbacks=callback_provider)
            else:
                assistants[assistant_name] = AssistantClient.from_yaml(config, callbacks=callback_provider)
    return assistants


def extract_json_code_block(text):
    """
    Extracts and returns the content of the first JSON code block found in the given text.
    If no JSON code block markers are found, returns the original input text.
    """
    pattern = r"```json\n([\s\S]*?)\n```"
    match = re.search(pattern, text)
    return match.group(1) if match else text


class MultiAgentOrchestrator(TaskManagerCallbacks, AssistantClientCallbacks):
    """
    Orchestrates the multi-agent task execution.
    """
    def __init__(self, ai_client_type : AIClientType):
        self.task_completion_events = {}
        self.assistants: Dict[str, AssistantClient] = {}
        self.conversation_thread_client = ConversationThreadClient.get_instance(ai_client_type)
        self.condition = Condition()
        self.task_started = False
        super().__init__()

    def on_task_started(self, task : MultiTask, schedule_id):
        print(f"Task {task.id} started with schedule ID: {schedule_id}")
        with self.condition:
            self.task_completion_events[schedule_id] = threading.Event()
            self.task_started = True
            self.condition.notify_all()
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
                if isinstance(message, TextMessage):
                    if message.sender == assistant_name:
                        print(f"\n{message.sender}: {message.content}")
                elif isinstance(message, FileMessage):
                    print(f"\n{message.sender}: provided file {message.file_name}")
                    message.retrieve_file(assistant_client.assistant_config.output_folder_path)
                elif isinstance(message, ImageMessage):
                    print(f"\n{message.sender}: provided image {message.file_name}")
                    message.retrieve_image(assistant_client.assistant_config.output_folder_path)

    def on_task_completed(self, task : MultiTask, schedule_id, result):
        print(f"Task {task.id} completed with schedule ID: {schedule_id}. Result: {result}")
        event = self.task_completion_events.get(schedule_id)
        if event:
            event.set()
        self.task_started = False

    def on_task_failed(self, task : MultiTask, schedule_id, error) -> None:
        print(f"Task {task.id} failed with schedule ID: {schedule_id}. Error: {error}")
        event = self.task_completion_events.get(schedule_id)
        if event:
            event.set()
        self.task_started = False

    def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message=False, message=None):
        if run_status == "in_progress":
            print(".", end="", flush=True)

    def on_function_call_processed(self, assistant_name, run_identifier, function_name, arguments, response):
        if "error" in response:
            print(f"\n{assistant_name}: Function call {function_name} with arguments {arguments}, result failed with: {response}")
        else:
            print(f"\n{assistant_name}: Function call {function_name} with arguments {arguments}, result OK.")

    def wait_for_all_tasks(self):
        with self.condition:
            while not self.task_started:
                self.condition.wait()

            print("Task has started, waiting for completion...")
            for event in self.task_completion_events.values():
                event.wait()

    @property
    def assistants(self):
        return self._assistants
    
    @assistants.setter
    def assistants(self, value):
        self._assistants = value


def main():
    assistant_names = ["CodeConversionAgent", "CodeInspectionAgent", "TaskPlannerAgent"]
    orchestrator = MultiAgentOrchestrator(AIClientType.AZURE_OPEN_AI)
    assistants = initialize_assistants(assistant_names, orchestrator)
    orchestrator.assistants = assistants
    task_manager = TaskManager(orchestrator)

    while True:
        user_request = input("user (type 'exit' to quit): ").strip()
        if user_request.lower() == 'exit':  # Allow the user to exit the chat
            print("Exiting chat.")
            break
        if not user_request:
            continue
        task_list = assistants["TaskPlannerAgent"].process_messages(user_request=user_request)
        try:
            tasks = json.loads(extract_json_code_block(task_list))
            print(f"Here is the plan for the agents: {tasks}")
        except json.JSONDecodeError:
            continue
        multi_task = MultiTask(tasks)
        task_manager.schedule_task(multi_task)
        orchestrator.wait_for_all_tasks()

if __name__ == "__main__":
    main()