# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

class TaskManagerCallbacks:
    def on_task_started(self, task, schedule_id) -> None:
        """Called when a task starts.
        
        :param task: The task that started.
        :type task: Task
        :param schedule_id: The ID of the schedule.
        :type schedule_id: str

        :return: None
        :rtype: None
        """
        pass

    def on_task_completed(self, task, schedule_id, result) -> None:
        """Called when a task completes successfully.
        
        :param task: The task that completed.
        :type task: Task
        :param schedule_id: The ID of the schedule.
        :type schedule_id: str
        :param result: The result of the task.
        :type result: Any

        :return: None
        :rtype: None
        """
        pass

    def on_task_failed(self, task, schedule_id, error) -> None:
        """Called when a task fails or encounters an error.
        
        :param task: The task that failed.
        :type task: Task
        :param schedule_id: The ID of the schedule.
        :type schedule_id: str
        :param error: The error that occurred.
        :type error: Exception

        :return: None
        :rtype: None
        """
        pass

    def on_task_execute(self, task, schedule_id) -> None:
        """Called for a specific event or action during task execution.
        
        :param task: The task that is executing.
        :type task: Task
        :param schedule_id: The ID of the schedule.
        :type schedule_id: str

        :return: None
        :rtype: None
        """
        pass
