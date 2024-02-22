# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from enum import Enum, auto
from openai import AzureOpenAI, OpenAI
import os
from typing import Union
from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.management.exceptions import EngineError


class AIClientType(Enum):
    """
    An enum for the different types of AI clients.
    """
    AZURE_OPEN_AI = auto()
    """Azure OpenAI client"""
    OPEN_AI = auto()
    """OpenAI client"""

class AIClientFactory:
    _instance = None
    _clients = {}

    """
    A factory class for creating AI clients.
    """
    def __init__(self) -> None:
        if AIClientFactory._instance is not None:
            raise Exception("AIClientFactory is a singleton class")
        else:
            AIClientFactory._instance = self

    @classmethod
    def get_instance(cls) -> "AIClientFactory":
        """
        Get the singleton instance of the AI client factory.

        :return: The singleton instance of the AI client factory.
        :rtype: AIClientFactory
        """
        if cls._instance is None:
            cls._instance = AIClientFactory()
        return cls._instance

    def get_client(
            self, 
            client_type: AIClientType,
            api_version: str = "2024-02-15-preview"
    ) -> Union[OpenAI, AzureOpenAI]:
        """
        Get an AI client with the given type and API version.

        :param client_type: The type of AI client to get.
        :type client_type: AIClientType
        :param api_version: The version of the API to use, defaults to "2024-02-15-preview" or environment variable if set.
        :type api_version: str

        :return: The AI client.
        :rtype: Union[OpenAI, AzureOpenAI]
        """
        # Check for an environment variable to override the default API version
        api_version_env = os.getenv("AZURE_OPENAI_API_VERSION")
        if api_version_env:
            api_version = api_version_env

        # Create a unique key based on client type and API version
        client_key = (client_type, api_version)

        if client_key not in self._clients:
            if client_type == AIClientType.OPEN_AI:
                if not os.getenv("OPENAI_API_KEY"):
                    error_message = "OpenAI API key is not set"
                    logger.warning(error_message)
                    raise EngineError(error_message) 
                self._clients[client_key] = OpenAI()
            elif client_type == AIClientType.AZURE_OPEN_AI:
                if not os.getenv("AZURE_OPENAI_API_KEY"):
                    error_message = "Azure OpenAI API key is not set"
                    logger.warning(error_message)
                    raise EngineError(error_message)
                if not os.getenv("AZURE_OPENAI_ENDPOINT"):
                    error_message = "Azure OpenAI endpoint is not set"
                    logger.warning(error_message)
                    raise EngineError(error_message)

                self._clients[client_key] = AzureOpenAI(
                    api_version=api_version,
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                )
            else:
                raise ValueError(f"Invalid client type: {client_type}")

        return self._clients[client_key]