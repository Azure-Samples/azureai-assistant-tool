# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from openai import OpenAI, AzureOpenAI
from azure.ai.assistant.management.logger_module import logger
import json
import ast

input_file_types = ['cpp', 'cs', 'py', 'java', 'js', 'json', 'xml', 'html', 'css', 'txt', 'md', 'yaml', 'yml', 'sh', 'bat', 'ps1', 'swift', 'go']

instructions_input_file_type = [{
    "role": "system", 
    "content": f"Your task is to find out and return the input file type of given request."
               f"The returned value must be string and one of the following input file types: {input_file_types}."
               f"If the input file type is not one of the given input file types, you must return 'unknown' as string."
               f"You must not return other text than the input file type as string, otherwise it is a as failure."
}]

example_input = ["./folder1/input1.py", "./folder2/input2.py", "./folder3/input3.py"]
example_request = "Please review the python files from given input folders and suggest improvements."
expected_output = ["Please review the ./folder1/input1.py file and suggest improvements.",
                  "Please review the ./folder2/input2.py file and suggest improvements.",
                  "Please review the ./folder3/input3.py file and suggest improvements."]

instructions_request_forming = [{
    "role": "system", 
    "content": f"You are tasked to form a list of requests using given input file list. Following is an example of how to form a request from given input files: \n"
                f"Input files: {example_input}, "
                f"Input request: {example_request}, "
                f"Expected output format: {expected_output}, "
                f"Returned request list must be valid a list, e.g. ['request1', 'request2', 'request3'] which is the expected output format, otherwise it is considered as failure."
                f"Do not return other text than the requested list, inside [] brackets, otherwise it is considered as failure.]"
}]


class TaskRequestCreator:
    """
    A class to create a task request using AI.

    :param client: The OpenAI client.
    :type client: OpenAI
    :param model: The model to use for creating the task request.
    :type model: str
    """
    def __init__(
            self , 
            client : OpenAI, 
            model: str
    ) -> None:
        self._client = client
        self._model = model

    def get_input_file_type(
            self, 
            user_request : str
    ) -> str:
        """
        Get the input file type from a user request.

        :param user_request: The user request.
        :type user_request: str

        :return: The input file type.
        :rtype: str
        """
        try:
            messages = instructions_input_file_type
            logger.info(f"Creating input file type from following request: {user_request} using following instructions: {instructions_input_file_type}")
            request = "Please return input file type from following request: \n" + user_request
            messages.append({"role": "user", "content": request})
            response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages
                )
            input_file_type = response.choices[0].message.content
            logger.info("TaskRequestCreator, input file type: " + input_file_type)
            
            return input_file_type
        except Exception as e:
            error_message = "Error in input file type creation: " + str(e)
            logger.error(error_message)
            return error_message

    def create_request_list(
            self, 
            user_request : str,
            input_files : list
    ) -> list:
        """
        Create a list of requests from a user request and input files.

        :param user_request: The user request.
        :type user_request: str
        :param input_files: The input files.
        :type input_files: list

        :return: The list of requests.
        :rtype: list
        """
        try:
            messages = instructions_request_forming
            logger.info(f"Input request: {user_request}, input files: {input_files}")
            request = f"Input request: {user_request}, input files: {input_files}"
            messages.append({"role": "user", "content": request})
            logger.info("TaskRequestCreator, create_request_list, messages: " + str(messages))
            response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages
                )
            request_list_str = response.choices[0].message.content
            logger.info("TaskRequestCreator, create_request_list, response: " + request_list_str)
            # Convert the string to list
            request_list_str = request_list_str[1:-1]
            items = request_list_str.split("', '")
            # Remove the leading and trailing quote marks for each item and join them with newlines
            request_list = [item.strip("'") for item in items]
            return request_list

        except ValueError as e:
            error_message = "Error in request list conversion: " + str(e)
            logger.error(error_message)
            return error_message
        except Exception as e:
            error_message = "Error in request list creation: " + str(e)
            logger.error(error_message)
            return error_message