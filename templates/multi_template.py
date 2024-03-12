import json, threading
from typing import Dict
from azure.ai.assistant.management.assistant_client import AssistantClient
from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.conversation import Conversation
from azure.ai.assistant.management.message import TextMessage, FileMessage, ImageMessage
from azure.ai.assistant.management.ai_client_factory import AIClientType
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.task_manager import TaskManager, TaskManagerCallbacks, MultiTask


assistant_names = ["ASSISTANT_NAME1", "ASSISTANT_NAME2"]
ai_client_type : AIClientType = None
assistants: Dict[str, AssistantClient] = {}

class MultiAgentOrchestrator(TaskManagerCallbacks):
    def __init__(self, assistants : Dict[str, AssistantClient], ai_client_type : AIClientType):
        self.task_completion_events = {}
        self.assistants: Dict[str, AssistantClient] = assistants
        self.conversation_thread_client = ConversationThreadClient(ai_client_type)
        super().__init__()

    def on_task_started(self, task : MultiTask, schedule_id):
        print(f"Task {task.id} started with schedule ID: {schedule_id}")
        self.task_completion_events[schedule_id] = threading.Event()
        self.thread_name = self.conversation_thread_client.create_conversation_thread()

    def on_task_execute(self, task : MultiTask, schedule_id):
        print(f"Task {task.id} execute with schedule ID: {schedule_id}")
        for assistant_name in task.requests.keys():
            assistant_client = self.assistants[assistant_name]
            self.conversation_thread_client.create_conversation_thread_message(task.requests[assistant_name], self.thread_name)
            assistant_client.process_messages(self.thread_name)
            conversation = self.conversation_thread_client.retrieve_conversation(self.thread_name)
            for message in reversed(conversation.messages):
                if isinstance(message, TextMessage):
                    if message.sender == assistant_name:
                        print(f"{message.sender}: {message.content}")
                elif isinstance(message, FileMessage):
                    message.retrieve_file(assistant_client.assistant_config.output_folder_path)
                elif isinstance(message, ImageMessage):
                    message.retrieve_image(assistant_client.assistant_config.output_folder_path)

    def on_task_completed(self, task, schedule_id, result):
        print(f"Task {task.name} completed with schedule ID: {schedule_id}. Result: {result}")
        event = self.task_completion_events.get(schedule_id)
        if event:
            event.set()

    def wait_for_all_tasks(self):
        for event in self.task_completion_events.values():
            event.wait()

# create assistant clients from configuration files
for assistant_name in assistant_names:
    try:
        # open assistant configuration file
        with open(f"config/{assistant_name}_assistant_config.json", "r") as file:
            assistant_config = AssistantConfig.from_dict(json.load(file))
            assistants[assistant_name] = AssistantClient.from_config(assistant_config)
            ai_client_type = AIClientType[assistant_config.ai_client_type]

    except FileNotFoundError:
        print(f"Configuration file for {assistant_name} not found.")
        exit(1)
    except KeyError:
        print(f"AI client type not found in the configuration file for {assistant_name}.")
        exit(1)

# create multi agent orchestration
orchestrator = MultiAgentOrchestrator(assistants, ai_client_type)
task_manager = TaskManager(orchestrator)
tasks = [
    {
        "assistant": "ASSISTANT_NAME1",
        "task": "Convert Main.java file in input folder to idiomatic Python implementation and create converted file in the same folder. Inform the full path of converted file at the end"
    },
    {
        "assistant": "ASSISTANT_NAME2",
        "task": "Review the converted Python file and inform about any missing implementations"
    }
]
multi_task = MultiTask(tasks)
task_manager.schedule_task(multi_task)
orchestrator.wait_for_all_tasks()
