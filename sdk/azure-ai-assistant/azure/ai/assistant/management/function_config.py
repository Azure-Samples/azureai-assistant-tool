# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import copy
from azure.ai.assistant.management.logger_module import logger


class FunctionConfig:
    """
    A class representing the configuration for a function (Standard or Azure).

    :param function_spec: The specification for the function.
    :type function_spec: dict
    """

    def __init__(self, function_spec: dict) -> None:
        self._type = function_spec.get("type", "function")

        # Standard fields for a function (shared by both normal & azure).
        self._name = ""
        self._module = ""
        self._description = ""
        self._parameters = {}

        # Additional sub-fields that might be in the "function" block
        # but are neither name/module/description/parameters.
        self._function_extras = {}

        # For Azure functions, we might have additional blocks like "input_binding", "output_binding", etc.
        # We'll store them here separately so we can reconstruct them later.
        self._azure_extras = {}

        if self._type == "azure_function":
            # "azure_function" block might look like:
            #   {
            #     "function": { ... },
            #     "input_binding": { ... },
            #     "output_binding": { ... },
            #   }
            azure_block = function_spec.get("azure_function", {})

            # Extract the sub-block that describes the underlying function
            func_block = azure_block.get("function", {})
            self._name = func_block.get("name", "")
            self._module = func_block.get("module", "")
            self._description = func_block.get("description", "")
            self._parameters = func_block.get("parameters", {})

            # If the function sub-block has extra items, store them:
            for k, v in func_block.items():
                if k not in ["name", "module", "description", "parameters"]:
                    self._function_extras[k] = v

            # Store any other sub-blocks in azure_function (e.g. input_binding, output_binding, etc.)
            for k, v in azure_block.items():
                if k != "function":
                    self._azure_extras[k] = v

        else:
            # For a normal function, everything is under "function"
            func_block = function_spec.get("function", {})
            self._name = func_block.get("name", "")
            self._module = func_block.get("module", "")
            self._description = func_block.get("description", "")
            self._parameters = func_block.get("parameters", {})

            for k, v in func_block.items():
                if k not in ["name", "module", "description", "parameters"]:
                    self._function_extras[k] = v

    def get_full_spec(self) -> dict:
        """
        Get the full specification for the function.

        :return: The full specification for the function.
        :rtype: dict
        """
        if self._type == "azure_function":
            # Build the "function" sub-dict
            func_dict = {
                "name": self._name,
                "module": self._module,
                "description": self._description,
                "parameters": self._parameters,
            }
            # Add back any extra fields (beyond name/module/description/parameters)
            for k, v in self._function_extras.items():
                func_dict[k] = v

            # Reassemble azure_function
            azure_function_dict = {
                "function": func_dict
            }
            # Add in the extra azure blocks (e.g. input_binding/output_binding)
            for k, v in self._azure_extras.items():
                azure_function_dict[k] = copy.deepcopy(v)

            return {
                "type": "azure_function",
                "azure_function": azure_function_dict
            }
        else:
            # Normal function
            func_dict = {
                "name": self._name,
                "module": self._module,
                "description": self._description,
                "parameters": self._parameters,
            }
            for k, v in self._function_extras.items():
                func_dict[k] = v

            return {
                "type": "function",
                "function": func_dict
            }

    @property
    def name(self) -> str:
        """
        The name of the function.

        :return: The name of the function.
        :rtype: str
        """
        return self._name


class OpenAPIFunctionConfig:
    """
    A class representing the configuration for an OpenAPI-based function.

    :param openapi_dict: The full specification dict for the OpenAPI function.
    :type openapi_dict: dict
    """
    def __init__(self, openapi_dict) -> None:
        self._type = openapi_dict.get('type', 'openapi')
        self._openapi_data = openapi_dict.get('openapi', {})
        self._auth = openapi_dict.get('auth', {})
        self._name = self._openapi_data.get('name', 'Unnamed OpenAPI Func')
        self._description = self._openapi_data.get('description', '')

    def get_full_spec(self) -> dict:
        """
        Returns the entire OpenAPI function specification,
        including both the 'openapi' block and any 'auth' details.
        
        :return: The full specification dict for this OpenAPI function.
        :rtype: dict
        """
        return {
            "type": self._type,
            "openapi": self._openapi_data,
            "auth": self._auth
        }

    @property
    def name(self) -> str:
        """
        The name of this OpenAPI function, drawn from the 'openapi' block.
        
        :return: The name of this OpenAPI function.
        :rtype: str
        """
        return self._name
    
    @property
    def description(self) -> str:
        """
        The description of this OpenAPI function, drawn from the 'openapi' block.
        
        :return: The description of this OpenAPI function.
        :rtype: str
        """
        return self._description
    
    @property
    def auth(self) -> dict:
        """
        The authentication details for this OpenAPI function.
        
        :return: The authentication details for this OpenAPI function.
        :rtype: dict
        """
        return self._auth