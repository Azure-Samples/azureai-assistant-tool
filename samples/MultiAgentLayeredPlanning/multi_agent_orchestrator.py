# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.async_assistant_client import AsyncAssistantClient
from azure.ai.assistant.management.async_assistant_client_callbacks import AsyncAssistantClientCallbacks
from azure.ai.assistant.management.ai_client_factory import AsyncAIClientType
from azure.ai.assistant.management.async_conversation_thread_client import AsyncConversationThreadClient
from azure.ai.assistant.management.async_task_manager import AsyncMultiTask
from azure.ai.assistant.management.async_task_manager_callbacks import AsyncTaskManagerCallbacks

from typing import Dict
import asyncio


class MultiAgentOrchestrator(AsyncTaskManagerCallbacks, AsyncAssistantClientCallbacks):
    """
    Orchestrates the multi-agent task execution.
    """
    def __init__(self):
        self.task_completion_events = {}
        self._assistants: Dict[str, AsyncAssistantClient] = {}
        self.conversation_thread_client = AsyncConversationThreadClient.get_instance(AsyncAIClientType.AZURE_OPEN_AI)
        self.condition = asyncio.Condition()
        self.task_started = False
        super().__init__()

    async def on_task_started(self, task: AsyncMultiTask, schedule_id):
        print(f"\nTask {task.id} started with schedule ID: {schedule_id}")
        async with self.condition:
            self.task_completion_events[schedule_id] = asyncio.Event()
            self.task_started = True
            self.condition.notify_all()
            self.thread_name = await self.conversation_thread_client.create_conversation_thread()

    async def on_task_execute(self, task: AsyncMultiTask, schedule_id):
        print(f"\nTask {task.id} execute with schedule ID: {schedule_id}")
        for request in task.requests:
            assistant_name = request["assistant"]
            assistant_client = self._assistants[assistant_name]
            await self.conversation_thread_client.create_conversation_thread_message(request["task"], thread_name=self.thread_name)
            await assistant_client.process_messages(thread_name=self.thread_name)

    async def on_task_completed(self, task: AsyncMultiTask, schedule_id, result):
        print(f"\nTask {task.id} completed with schedule ID: {schedule_id}. Result: {result}")
        event = self.task_completion_events.get(schedule_id)
        if event:
            event.set()
        self.task_started = False

    async def on_task_failed(self, task: AsyncMultiTask, schedule_id, error):
        print(f"\nTask {task.id} failed with schedule ID: {schedule_id}. Error: {error}")
        event = self.task_completion_events.get(schedule_id)
        if event:
            event.set()
        self.task_started = False

    async def on_run_start(self, assistant_name, run_identifier, run_start_time, user_input):
        if self._assistants[assistant_name].assistant_config.assistant_role == "engineer":
            print(f"\n{assistant_name}: starting the task with input: {user_input}")
        elif self._assistants[assistant_name].assistant_config.assistant_role != "user_interaction":
            print(f"\n{assistant_name}: starting the task")

    async def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message=False, message=None):
        if run_status == "in_progress" and is_first_message:
            print(f"\n{assistant_name}: working on the task", end="", flush=True)
        elif run_status == "in_progress":
            print(".", end="", flush=True)

    async def on_run_end(self, assistant_name, run_identifier, run_end_time, thread_name, response=None):
        if response:
            print(f"{assistant_name}: {response}")
        else:
            conversation = await self.conversation_thread_client.retrieve_conversation(thread_name)
            message = conversation.get_last_text_message(assistant_name)
            print(f"\n{message}")
            if self._assistants[assistant_name].assistant_config.assistant_role == "engineer":
                await self._assistants["FileCreatorAgent"].process_messages(user_request=message.content)

    async def on_function_call_processed(self, assistant_name, run_identifier, function_name, arguments, response = None):
        if "error" in response:
            print(f"\n{assistant_name}: Function call {function_name} with arguments {arguments}, result failed with: {response}")
        else:
            print(f"\n{assistant_name}: Function call {function_name} with arguments {arguments}, result OK.")

    async def wait_for_all_tasks(self):
        async with self.condition:
            while not self.task_started:
                await self.condition.wait()
            for event in self.task_completion_events.values():
                await event.wait()

    @property
    def assistants(self):
        return self._assistants
    
    @assistants.setter
    def assistants(self, value):
        self._assistants = value