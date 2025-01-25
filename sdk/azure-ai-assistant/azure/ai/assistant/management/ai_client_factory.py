# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from enum import Enum, auto
from openai import AzureOpenAI, OpenAI, AsyncAzureOpenAI, AsyncOpenAI

import os
from typing import Union, Optional, Tuple, TYPE_CHECKING

# These imports are for type hints only; they won't run at import time.
if TYPE_CHECKING:
    from azure.ai.projects import AIProjectClient as SyncAIProjectClient
    from azure.ai.projects.aio import AIProjectClient as AsyncAIProjectClient

# Create a single alias to represent the union of all possible client return types.
AIClient = Union[
    "OpenAI",
    "AzureOpenAI",
    "AsyncOpenAI",
    "AsyncAzureOpenAI",
    "SyncAIProjectClient",
    "AsyncAIProjectClient",
]

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
    AZURE_OPEN_AI_REALTIME = auto()
    """Azure OpenAI client used with Realtime API"""
    OPEN_AI_REALTIME = auto()
    """OpenAI client used with Realtime API"""
    AZURE_AI_AGENT = auto()
    """Azure AI Agents client"""


class AsyncAIClientType(Enum):
    """
    An enum for the different types of AI clients.
    """
    AZURE_OPEN_AI = auto()
    """Azure OpenAI async client"""
    OPEN_AI = auto()
    """OpenAI async client"""
    AZURE_OPEN_AI_REALTIME = auto()
    """Azure OpenAI async client used with Realtime API"""
    OPEN_AI_REALTIME = auto()
    """OpenAI async client used with Realtime API"""
    AZURE_AI_AGENT = auto()
    """Azure AI Agents async client"""


class AIClientFactory:
    """A factory class to create and cache AI clients."""

    _instance = None
    _clients = {}
    _current_client_type: Optional[Union[AIClientType, AsyncAIClientType]] = None

    def __init__(self) -> None:
        if AIClientFactory._instance is not None:
            raise Exception("AIClientFactory is a singleton class")
        else:
            AIClientFactory._instance = self

    @classmethod
    def get_instance(cls) -> "AIClientFactory":
        if cls._instance is None:
            cls._instance = AIClientFactory()
        return cls._instance

    @property
    def current_client_type(self) -> Optional[Union[AIClientType, AsyncAIClientType]]:
        return self._current_client_type

    def get_client(
        self,
        client_type: Union[AIClientType, AsyncAIClientType],
        api_version: str = None,
        **client_args
    ) -> AIClient:
        """
        Create and return an appropriate AI client (either synchronous or asynchronous).
        
        :param client_type: The type of client to create.
        :type client_type: Union[AIClientType, AsyncAIClientType]
        :param api_version: The API version to use for Azure clients.
        :type api_version: str
        :param client_args: Additional arguments to pass to the client constructor.
        :type client_args: dict

        :return: The created AI client.
        :rtype: AIClient
        """
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", api_version) or "2024-05-01-preview"
        client_key = (client_type, api_version)
        
        if client_key in self._clients:
            if self._clients[client_key].is_closed():
                logger.info(f"Recreating client for {client_key}")
                del self._clients[client_key]
            else:
                self._current_client_type = client_type
                return self._clients[client_key]

        if isinstance(client_type, AIClientType):
            if client_type in {AIClientType.AZURE_OPEN_AI, AIClientType.AZURE_OPEN_AI_REALTIME}:
                from openai import AzureOpenAI
                self._clients[client_key] = AzureOpenAI(
                    api_version=api_version, 
                    azure_endpoint=self._get_http_endpoint(os.getenv("AZURE_OPENAI_ENDPOINT")), 
                    **client_args
                )
            elif client_type in {AIClientType.OPEN_AI, AIClientType.OPEN_AI_REALTIME}:
                from openai import OpenAI
                self._clients[client_key] = OpenAI(**client_args)
            elif client_type == AIClientType.AZURE_AI_AGENT:
                from azure.ai.projects import AIProjectClient
                from azure.identity import DefaultAzureCredential
                conn_str = os.getenv("PROJECT_CONNECTION_STRING")
                if not conn_str:
                    raise ValueError(
                        "No PROJECT_CONNECTION_STRING was found in environment variables. "
                        "Please set PROJECT_CONNECTION_STRING to a valid Azure AI Agents "
                        "connection string to continue."
                    )
                project_client = AIProjectClient.from_connection_string(
                    credential=DefaultAzureCredential(),
                    conn_str=conn_str,
                    **client_args
                )
                self._clients[client_key] = project_client
                    
        elif isinstance(client_type, AsyncAIClientType):
            if client_type in {AsyncAIClientType.AZURE_OPEN_AI, AsyncAIClientType.AZURE_OPEN_AI_REALTIME}:
                from openai import AsyncAzureOpenAI
                self._clients[client_key] = AsyncAzureOpenAI(
                    api_version=api_version, 
                    azure_endpoint=self._get_http_endpoint(os.getenv("AZURE_OPENAI_ENDPOINT")), 
                    **client_args
                )
            elif client_type in {AsyncAIClientType.OPEN_AI, AsyncAIClientType.OPEN_AI_REALTIME}:
                from openai import AsyncOpenAI
                self._clients[client_key] = AsyncOpenAI(**client_args)
            elif client_type == AsyncAIClientType.AZURE_AI_AGENTS:
                from azure.ai.projects.aio import AIProjectClient
                from azure.identity.aio import DefaultAzureCredential
                conn_str = os.getenv("PROJECT_CONNECTION_STRING")
                if not conn_str:
                    raise ValueError(
                        "No PROJECT_CONNECTION_STRING was found in environment variables. "
                        "Please set PROJECT_CONNECTION_STRING to a valid Azure AI Agents "
                        "connection string to continue."
                    )
                project_client = AIProjectClient.from_connection_string(
                    credential=DefaultAzureCredential(),
                    conn_str=conn_str,
                    **client_args
                )
                self._clients[client_key] = project_client

        else:
            raise ValueError(f"Invalid client type: {client_type}")

        self._current_client_type = client_type
        return self._clients[client_key]

    def _get_http_endpoint(self, endpoint: str) -> str:
        if endpoint and "wss://" in endpoint:
            endpoint = endpoint.replace("wss://", "https://").replace("/openai/realtime", "")
        logger.info(f"HTTP endpoint: {endpoint}")
        return endpoint

    def get_azure_client_info(self) -> Tuple[str, str]:
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is not set.")
        return api_version, endpoint
