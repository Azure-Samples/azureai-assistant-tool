# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import uuid
from abc import ABC, abstractmethod

class AsyncTask(ABC):
    def __init__(self):
        self.id = uuid.uuid4()  # Unique identifier for the task

    def set_assistant_name(self, assistant_name):
        """
        Sets the name of the assistant.

        :param assistant_name: The name of the assistant.
        :type assistant_name: str
        """
        self.assistant_name = "multi-assistant" if assistant_name is None else assistant_name

    @abstractmethod
    async def execute(self, callback=None):
        """
        Executes the task.

        :param callback: The callback function to call when the task is complete.
        :type callback: function

        :return: None
        :rtype: None
        """
        pass


class AsyncBasicTask(AsyncTask):
    """
    This class represents a basic task.

    :param user_request: The user request to process.
    :type user_request: str
    """
    def __init__(self, user_request):
        super().__init__()
        self.user_request = user_request

    async def execute(self, callback=None):
        """
        Executes the basic task.

        :param callback: The callback function to call when the task is complete.
        :type callback: function
        """
        if callback:
            await callback()


class AsyncBatchTask(AsyncTask):
    """
    This class represents a batch task.

    :param requests: A list of user requests to process.
    :type requests: list
    """
    def __init__(self, requests):
        super().__init__()
        self.requests = requests

    async def execute(self, callback=None):
        """
        Executes the batch task.

        :param callback: The callback function to call when the task is complete.
        :type callback: function
        """
        if callback:
            await callback()


class AsyncMultiTask(AsyncTask):
    """
    This class represents a multi task.

    :param requests: A list of requests, each request is a dict with 'assistant' and 'task' keys.
                     A single dict is also accepted and will be converted to a list.
    :type requests: list or dict
    """
    def __init__(self, requests):
        super().__init__()
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

    async def execute(self, callback=None):
        """
        Executes the multi task.

        :param callback: The callback function to call when the task is complete.
        :type callback: callable or None
        """
        try:
            if callback:
                await callback()
        except Exception as e:
            print(f"Error during task execution: {e}")
