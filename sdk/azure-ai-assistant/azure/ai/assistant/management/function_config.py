# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.logger_module import logger


class FunctionConfig:
    """
    A class representing the configuration for a function.

    :param function_spec: The specification for the function.
    :type function_spec: dict
    """
    def __init__(
            self, 
            function_spec
    ) -> None:
        self._type = function_spec.get('type', 'function')  # Default to 'function' if not specified
        self._function_data = function_spec.get('function', {})
        self._name = self._function_data.get('name', '')
        self._module = self._function_data.get('module', '')
        self._description = self._function_data.get('description', '')
        self._parameters = self._function_data.get('parameters', {})

    def get_full_spec(self) -> dict:
        """
        Get the full specification for the function.

        :return: The full specification for the function.
        :rtype: dict
        """
        return {
            "type": self._type,
            "function": {
                "name": self._name,
                "module": self._module,
                "description": self._description,
                "parameters": self._parameters
            }
        }

    @property
    def name(self) -> str:
        """
        The name of the function.

        :return: The name of the function.
        :rtype: str
        """
        return self._name