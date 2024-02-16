# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.task_manager_callbacks import TaskManagerCallbacks
from azure.ai.assistant.management.task import BasicTask, BatchTask, MultiTask, Task
import threading
import uuid, time
from datetime import datetime


class TaskManager:
    _instance = None

    """
    This class is responsible for scheduling and executing tasks.

    :param callbacks: The callbacks to use for task execution.
    :type callbacks: TaskManagerCallbacks
    """
    def __init__(
            self, 
            callbacks : TaskManagerCallbacks
    ) -> None:
        self._callbacks = callbacks
        self._scheduled_tasks = []

    @classmethod
    def get_instance(
        cls, 
        callbacks : TaskManagerCallbacks
    ) -> 'TaskManager':
        """
        Gets the singleton instance of the task manager.

        :param callbacks: The callbacks to use for task execution.
        :type callbacks: TaskManagerCallbacks

        :return: The singleton instance of the task manager.
        :rtype: TaskManager
        """
        if cls._instance is None:
            cls._instance = TaskManager(callbacks)
        return cls._instance

    def create_basic_task(self, user_request : str) -> BasicTask:
        """
        Creates a basic task.

        :param user_request: The user request to use for the task.
        :type user_request: str

        :return: The basic task.
        :rtype: BasicTask
        """
        return BasicTask(user_request)

    def create_batch_task(self, requests : list) -> BatchTask:
        """
        Creates a batch task.

        :param requests: A list of user requests to use for the task.
        :type requests: list

        :return: The batch task.
        :rtype: BatchTask
        """
        return BatchTask(requests)

    def create_multi_task(self, requests: list) -> MultiTask:
        """
        Creates a multi task.

        :param requests: A list of user requests to use for the task.
        :type requests: list

        :return: The multi task.
        :rtype: MultiTask
        """
        return MultiTask(requests)

    def schedule_task(
            self, 
            task : Task,
            assistant_name : str = None,
            start_time : datetime=None,
            interval_seconds : int=0,
            recurrence_count : int=1
        ) -> str:
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
        if isinstance(task, MultiTask):
            task.set_assistant_name(None)
        else:
            task.set_assistant_name(assistant_name)

        if start_time is None or (start_time - datetime.now()).total_seconds() <= 0:
            # Execute immediately or set up recurrence
            task_thread = threading.Thread(target=self._execute_task, args=(task, schedule_id, interval_seconds, recurrence_count))
            task_thread.start()
        else:
            # Schedule for later execution or recurrence
            self._schedule_task(task, schedule_id, start_time, interval_seconds, recurrence_count)
        return schedule_id

    def _schedule_task(self, task, schedule_id, start_time, interval_seconds, recurrence_count):
        delay = (start_time - datetime.now()).total_seconds()
        timer = threading.Timer(delay, self._execute_task, [task, schedule_id, interval_seconds, recurrence_count])
        timer.start()
        self._scheduled_tasks.append((schedule_id, task, timer))

    def _execute_task(self, task, schedule_id, interval_seconds=0, recurrence_count=1):
        try:
            self._callbacks.on_task_started(task, schedule_id)
            self._run_task_with_recurrence(task, schedule_id, interval_seconds, recurrence_count)
        except Exception as e:
            self._callbacks.on_task_failed(task, schedule_id, str(e))

    def _run_task_with_recurrence(self, task, schedule_id, interval_seconds, recurrence_count):
        while recurrence_count > 0:
            task.execute(callback=lambda: self._callbacks.on_task_execute(task, schedule_id))
            recurrence_count -= 1
            if recurrence_count > 0:
                time.sleep(interval_seconds)
        self._callbacks.on_task_completed(task, schedule_id, "Success")
