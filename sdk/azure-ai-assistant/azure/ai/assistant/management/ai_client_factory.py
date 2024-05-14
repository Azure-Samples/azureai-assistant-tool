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
            api_version: str = None,
            **client_args
    ) -> Union[OpenAI, AzureOpenAI, AsyncOpenAI, AsyncAzureOpenAI]:
        """
        Get an AI client, synchronous or asynchronous, based on the given type and API version.

        :param client_type: The type of AI client to get.
        :type client_type: Union[AIClientType, AsyncAIClientType]
        :param api_version: The API version to use.
        :type api_version: str
        :param client_args: Additional keyword arguments for configuring the AI client.
        :type client_args: Dict
        
        :return: The AI client.
        :rtype: Union[OpenAI, AzureOpenAI, AsyncOpenAI, AsyncAzureOpenAI]
        """
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", api_version) or "2024-04-01-preview"
        client_key = (client_type, api_version)
        if client_key in self._clients:
            return self._clients[client_key]

        if isinstance(client_type, AIClientType):
            if client_type == AIClientType.AZURE_OPEN_AI:
                self._clients[client_key] = AzureOpenAI(api_version=api_version, azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), **client_args)
            elif client_type == AIClientType.OPEN_AI:
                self._clients[client_key] = OpenAI(**client_args)
                
        elif isinstance(client_type, AsyncAIClientType):
            if client_type == AsyncAIClientType.AZURE_OPEN_AI:
                self._clients[client_key] = AsyncAzureOpenAI(api_version=api_version, azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), **client_args)
            elif client_type == AsyncAIClientType.OPEN_AI:
                self._clients[client_key] = AsyncOpenAI(**client_args)
        else:
            raise ValueError(f"Invalid client type: {client_type}")

        return self._clients[client_key]
