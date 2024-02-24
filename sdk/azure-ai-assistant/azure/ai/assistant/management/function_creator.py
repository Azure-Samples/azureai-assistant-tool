# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from openai import OpenAI, AzureOpenAI
from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.management.function_config_manager import FunctionConfigManager
import json
import ast

instructions_spec = [{
    "role": "system", 
    "content": f"You are tasked to create function specification of given requirements. "
               f"The function specification shall follow this template: {FunctionConfigManager.get_function_spec_template()}."
               f"As seen in the template, the function spec must have 'type' & 'function' main blocks."
               f"The 'function' must have 'name', 'module', 'description', 'parameters' fields."
               f"The module field value shall be 'functions.user_functions'."
               f"The function name must follow snake case format. The module value must not be changed what is in the template."
               f"Returned spec must be valid json string, otherwise it is considered as failure."
}]

error_handling_imports = """
from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.management.function_config_manager import FunctionConfigManager
"""

example_error_handling_code = """
# FunctionConfigManager is singleton and required for retrieving error messages for possible error types
def new_user_function():
    function_config_manager = FunctionConfigManager()
    if not os.path.isdir(directory):
        error_message = function_config_manager.get_error_message('directory_not_found')
        logger.error(error_message)
        return json.dumps({"function_error": error_message})
    # rest of the function
"""

class FunctionCreator:
    function_config_manager = FunctionConfigManager()
    possible_error_types = function_config_manager.get_error_keys()
    instructions_impl = [{
        "role": "system", 
        "content": f"You are tasked to create function implementation of given function specification using Python programming language. "
                f"The implementation must be valid python code and executable in the following way: "
                f"`python -c 'from functions.user_functions import function_name; function_name()'`. "
                f"For error handling, include these specific imports: {error_handling_imports.strip()} "
                f"Use the following error types for handling different scenarios: {possible_error_types.strip()}. "
                f"As an example of error handling using given error types, consider this code snippet: "
                f"\"\"\"{example_error_handling_code.strip()}\"\"\" "
                f"Ensure your function handles errors gracefully and returns a clear error message in case of exceptions."
    }]

    """
    A class to create a function specification and implementation using AI.

    :param client: The OpenAI client.
    :type client: OpenAI
    :param model: The model to use for creating the function.
    :type model: str
    """
    def __init__(
            self ,
            client : OpenAI,
            model: str
    ) -> None:
        self.client = client
        self.model = model

    def get_function_spec(
            self, 
            requirements : str
    ) -> str:
        """
        Get the function specification for given requirements.

        :param requirements: The requirements for the function.
        :type requirements: str

        :return: The function specification for the given requirements.
        :rtype: str
        """
        try:
            messages = instructions_spec
            logger.info("Creating function spec from the following requirements: \n" + requirements)
            request = "Please return function specification using following requirements: \n" + requirements
            messages.append({"role": "user", "content": request})
            response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )
            spec_text = response.choices[0].message.content
            logger.info("FunctionCreator, get_function_spec, response: " + spec_text)

            # Extract JSON from the response if it exists
            if '```json' in spec_text:
                json_str = spec_text.split('```json\n')[1].split('\n```')[0]
                response_dict = json.loads(json_str)
            else:
                # Convert the string response to a Python dictionary
                response_dict = ast.literal_eval(spec_text)

            return json.dumps(response_dict, indent=4)
        except ValueError as e:
            logger.error("Error in converting to Python dictionary: " + str(e))
            return "Error in Function Specification conversion"
        except Exception as e:
            logger.error("Error: " + str(e))
            return "Error in Function Specification creation"

    def get_function_impl(
            self,
            user_request,
            spec
    ) -> str:
        """
        Get the function implementation for given user request and function specification.

        :param user_request: The user request for the function.
        :type user_request: str
        :param spec: The function specification.
        :type spec: str

        :return: The function implementation for the given user request and function specification.
        :rtype: str
        """
        try:
            messages = self.instructions_impl
            logger.info(f"{user_request} that follows the following spec: \n" + spec + " and returns result using json.dumps() and where 'result' is key and value is the result.")
            request = f"{user_request} that follows the following spec: \n" + spec + " and returns result using json.dumps() and where 'result' is key and value is the result."
            messages.append({"role": "user", "content": request})
            logger.info("FunctionCreator, get_function_impl, messages: " + str(messages))
            response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )
            function_impl = response.choices[0].message.content
            logger.info("FunctionCreator, get_function_impl, response: " + function_impl)
            return function_impl
        except Exception as e:
            logger.error("Error in Function Implementation creation: " + str(e))
            return "Error in Function Implementation creation"