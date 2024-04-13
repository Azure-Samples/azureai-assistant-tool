# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.async_task import AsyncBasicTask, AsyncBatchTask, AsyncMultiTask
from azure.ai.assistant.management.async_task_manager_callbacks import AsyncTaskManagerCallbacks

import asyncio
import uuid
from datetime import datetime


class AsyncTaskManager:
    _instance = None
    """
    This class is responsible for scheduling and executing tasks.

    :param callbacks: The callbacks to use for task execution.
    :type callbacks: AsyncTaskManagerCallbacks
    """
    def __init__(self, callbacks : AsyncTaskManagerCallbacks):
        self._callbacks = callbacks
        self._scheduled_tasks = []

    @classmethod
    def get_instance(cls, callbacks) -> 'AsyncTaskManager':
        """
        Gets the singleton instance of the task manager.

        :param callbacks: The callbacks to use for task execution.
        :type callbacks: AsyncTaskManagerCallbacks

        :return: The singleton instance of the task manager.
        :rtype: AsyncTaskManager
        """
        if cls._instance is None:
            cls._instance = AsyncTaskManager(callbacks)
        return cls._instance

    def create_basic_task(self, user_request) -> AsyncBasicTask:
        """
        Creates a basic task.

        :param user_request: The user request to use for the task.
        :type user_request: str

        :return: The basic task.
        :rtype: AsyncBasicTask
        """
        return AsyncBasicTask(user_request)

    def create_batch_task(self, requests) -> AsyncBatchTask:
        """
        Creates a batch task.

        :param requests: A list of user requests to use for the task.
        :type requests: list

        :return: The batch task.
        :rtype: AsyncBatchTask
        """
        return AsyncBatchTask(requests)

    def create_multi_task(self, requests) -> AsyncMultiTask:
        """
        Creates a multi task.

        :param requests: A list of user requests to use for the task.
        :type requests: list

        :return: The multi task.
        :rtype: AsyncMultiTask
        """
        return AsyncMultiTask(requests)

    async def schedule_task(self, task, assistant_name=None, start_time=None, interval_seconds=0, recurrence_count=1):
        """
        Schedules a task for execution.

        :param task: The task to schedule.
        :type task: Task
        :param assistant_name: The name of the assistant to use for the task.
        :type assistant_name: str
        :param start_time: The start time for the task.
        :type start_time: datetime
        :param interval_seconds: The interval in seconds for recurring tasks.
        :type interval_seconds: int
        :param recurrence_count: The number of times to recur the task.
        :type recurrence_count: int

        :return: The ID of the scheduled task.
        :rtype: str
        """
        schedule_id = str(uuid.uuid4())
        task.set_assistant_name(None if isinstance(task, AsyncMultiTask) else assistant_name)
        if start_time is None or (start_time - datetime.now()).total_seconds() <= 0:
            asyncio.create_task(self._execute_task(task, schedule_id, interval_seconds, recurrence_count))
        else:
            delay = (start_time - datetime.now()).total_seconds()
            asyncio.get_event_loop().call_later(delay, asyncio.create_task, self._execute_task(task, schedule_id, interval_seconds, recurrence_count))
        return schedule_id

    async def _execute_task(self, task, schedule_id, interval_seconds=0, recurrence_count=1):
        try:
            await self._callbacks.on_task_started(task, schedule_id)
            await self._run_task_with_recurrence(task, schedule_id, interval_seconds, recurrence_count)
        except Exception as e:
            self._callbacks.on_task_failed(task, schedule_id, str(e))

    async def _run_task_with_recurrence(self, task, schedule_id, interval_seconds, recurrence_count):
        async def callback():
            await self._callbacks.on_task_execute(task, schedule_id)

        while recurrence_count > 0:
            await task.execute(callback=callback)
            recurrence_count -= 1
            if recurrence_count > 0:
                await asyncio.sleep(interval_seconds)
        await self._callbacks.on_task_completed(task, schedule_id, "Success")