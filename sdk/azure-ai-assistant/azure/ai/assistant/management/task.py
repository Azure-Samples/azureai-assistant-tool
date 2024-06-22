# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from abc import ABC, abstractmethod
import os
import glob
import uuid


class Task(ABC):
    """
    This class is the base class for all tasks.
    """
    def __init__(self) -> None:
        self.id = uuid.uuid4()  # Unique identifier for the task

    def set_assistant_name(
            self, 
            assistant_name
    ) -> None:
        """
        Sets the name of the assistant.

        :param assistant_name: The name of the assistant.
        :type assistant_name: str
        """
        if assistant_name is None:
            self.assistant_name = "multi-assistant"
        else:
            self.assistant_name = assistant_name

    @abstractmethod
    def execute(self, callback=None) -> None:
        """
        Executes the task.

        :param callback: The callback function to call when the task is complete.
        :type callback: function

        :return: None
        :rtype: None
        """
        pass


class BasicTask(Task):
    """
    This class represents a basic task.

    :param user_request: The user request to process.
    :type user_request: str
    """
    def __init__(self,
                 user_request: str) -> None:
        super().__init__()
        self.user_request = user_request

    def execute(self, callback=None) -> None:
        """
        Executes the basic task.

        :param callback: The callback function to call when the task is complete.
        :type callback: function
        """
        if callback:
            callback()


class BatchTask(Task):
    """
    This class represents a batch task.

    :param requests: A list of user requests to process.
    :type requests: list
    """
    def __init__(self,
                 requests: list) -> None:
        super().__init__()
        self.requests = requests

    def execute(self, callback=None) -> None:
        """
        Executes the batch task.

        :param callback: The callback function to call when the task is complete.
        :type callback: function
        """
        if callback:
            callback()


class MultiTask(Task):
    """
    This class represents a multi task.

    :param requests: A list of requests, each request is a dict with 'assistant' and 'task' keys.
    :type requests: list
    """
    def __init__(self,
                 requests: list) -> None:
        super().__init__()
        # List of requests, each request is a dict with 'assistant' and 'task' keys
        self.requests = self._validate_and_convert_requests(requests)

    def _validate_and_convert_requests(self, requests):
        """
        Validates and converts the requests to a list of dictionaries if necessary.

        :param requests: A list of requests or a single request dictionary.
        :type requests: list or dict
        :return: A list of request dictionaries.
        :rtype: list
        """
        if isinstance(requests, dict):
            return [requests]
        elif isinstance(requests, list):
            # Check if all items in the list are dictionaries
            if not all(isinstance(request, dict) for request in requests):
                raise ValueError("All items in the requests list must be dictionaries.")
            return requests
        else:
            raise TypeError("Requests should be a dictionary or a list of dictionaries.")

    def execute(self, callback=None) -> None:
        """
        Executes the multi task.

        :param callback: The callback function to call when the task is complete.
        :type callback: function
        """
        if callback:
            callback()