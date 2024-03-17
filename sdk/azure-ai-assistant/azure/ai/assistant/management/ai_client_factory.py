# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from enum import Enum, auto
from openai import AzureOpenAI, OpenAI, AsyncAzureOpenAI, AsyncOpenAI

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


class AsyncAIClientType(Enum):
    """
    An enum for the different types of AI clients.
    """
    AZURE_OPEN_AI = auto()
    """Azure OpenAI async client"""
    OPEN_AI = auto()
    """OpenAI async client"""


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
            client_type: Union[AIClientType, AsyncAIClientType],
            api_version: str = None
    ) -> Union[OpenAI, AzureOpenAI, AsyncOpenAI, AsyncAzureOpenAI]:
        """
        Get an AI client, synchronous or asynchronous, based on the given type and API version.

        :param client_type: The type of AI client to get.
        :type client_type: Union[AIClientType, AsyncAIClientType]
        :param api_version: The API version to use.
        :type api_version: str
        :return: The AI client.
        :rtype: Union[OpenAI, AzureOpenAI, AsyncOpenAI, AsyncAzureOpenAI]
        """
        # Set the default API version or use environment override
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", api_version or "2024-02-15-preview")

        client_key = (client_type, api_version)
        if client_key in self._clients:
            return self._clients[client_key]

        if isinstance(client_type, AIClientType):
            if client_type == AIClientType.AZURE_OPEN_AI:
                # Instantiate synchronous Azure OpenAI client
                self._check_and_prepare_env_vars(["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"])
                self._clients[client_key] = AzureOpenAI(api_version=api_version, azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"))
            elif client_type == AIClientType.OPEN_AI:
                # Instantiate synchronous OpenAI client
                self._check_and_prepare_env_vars(["OPENAI_API_KEY"])
                self._clients[client_key] = OpenAI()
                
        elif isinstance(client_type, AsyncAIClientType):
            if client_type == AsyncAIClientType.AZURE_OPEN_AI:
                # Instantiate asynchronous Azure OpenAI client
                self._check_and_prepare_env_vars(["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"])
                self._clients[client_key] = AsyncAzureOpenAI(api_version=api_version, azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"))
            elif client_type == AsyncAIClientType.OPEN_AI:
                # Instantiate asynchronous OpenAI client
                self._check_and_prepare_env_vars(["OPENAI_API_KEY"])
                self._clients[client_key] = AsyncOpenAI()
        else:
            raise ValueError(f"Invalid client type: {client_type}")

        return self._clients[client_key]

    def _check_and_prepare_env_vars(self, env_vars: list):
        """Utility method to check for required environment variables and raise an EngineError if not found."""
        for env_var in env_vars:
            value = os.getenv(env_var)
            if not value:
                error_message = f"{env_var} is not set"
                logger.warning(error_message)
                raise EngineError(error_message)