# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.identity import DefaultAzureCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

from enum import Enum, auto
from openai import AzureOpenAI, OpenAI
from datetime import datetime
from typing import Union
import os

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
    _azure_deployment_names: list = None  # Cache for Azure deployment names

    """
    A factory class for creating AI clients.
    """
    def __init__(self) -> None:
        if AIClientFactory._instance is not None:
            raise Exception("AIClientFactory is a singleton class")
        else:
            AIClientFactory._instance = self
            # Read environment variables
            self.azure_subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
            self.azure_openai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
            self.azure_resource_group = os.environ["AZURE_RESOURCE_GROUP"]

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

    def _parse_version(self, version: str) -> datetime:
        # Extract just the date part (YYYY-MM-DD) by assuming the date is always at the start
        # and splitting the string at the first occurrence of a non-numeric character after the date.
        import re  # Regular expressions module

        # Regular expression to match the date part at the beginning of the version string
        match = re.match(r"(\d{4}-\d{2}-\d{2})", version)
        if match:
            version_date_str = match.group(1)
            return datetime.strptime(version_date_str, "%Y-%m-%d")
        else:
            # Handle the case where the version string does not start with a valid date
            raise ValueError(f"Invalid version format: {version}")

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
            # Convert version strings to datetime objects for comparison
            default_version_date = self._parse_version(api_version)
            env_version_date = self._parse_version(api_version_env)
            
            # Use the environment version if it is newer than the default
            if env_version_date > default_version_date:
                api_version = api_version_env
            logger.info(f"Using Azure OpenAI API version: {api_version}")

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
    
    def get_models_list(
            self, 
            client_type: AIClientType, 
            api_version: str = "2024-02-15-preview"
    ) -> list:
        """
        Get a list of models from the AI client with the given type and API version.

        :param client_type: The type of AI client to get the models from.
        :type client_type: AIClientType
        :param api_version: The version of the API to use, defaults to "2024-02-15-preview" or environment variable if set.
        :type api_version: str

        :return: A list of models.
        :rtype: list
        """
        ai_client = self.get_client(client_type, api_version)

        if client_type == AIClientType.OPEN_AI:
            # Assuming OpenAI client has a method to list models. This is a placeholder.
            try:
                models = ai_client.models.list().data  # Placeholder for actual method call
            except AttributeError:
                raise EngineError("The OpenAI client does not support listing models.")
        elif client_type == AIClientType.AZURE_OPEN_AI:
            # Fetch model deployment names for AzureOpenAI
            models = self._fetch_deployment_names_for_azure()
        else:
            raise ValueError(f"Invalid client type: {client_type}")

        return models

    def _fetch_deployment_names_for_azure(self) -> list:
        if self._azure_deployment_names is not None:
            return self._azure_deployment_names

        # return empty list if the subscription id is not set or the endpoint is not set or the resource group is not set
        if not self.azure_subscription_id or not self.azure_openai_endpoint or not self.azure_resource_group:
            return []

        deployment_names = []

        # Initialize the Cognitive Services management client
        cogs_mgmt_client = CognitiveServicesManagementClient(
            credential=DefaultAzureCredential(),
            subscription_id=self.azure_subscription_id,
        )

        # List all cognitive services accounts in the specified resource group
        try:
            accounts = cogs_mgmt_client.accounts.list_by_resource_group(self.azure_resource_group)
            for account in accounts:
                if account.name in self.azure_openai_endpoint:
                    # List all model deployment names in the resource group and account
                    deployments = cogs_mgmt_client.deployments.list(self.azure_resource_group, account.name)
                    for deployment in deployments:
                        deployment_names.append(deployment.name)
                    break  # Assuming only one account matches the endpoint criteria
        except Exception as e:
            logger.error(f"Failed to fetch deployment names from Azure: {e}")
            raise EngineError("Error fetching deployment names from Azure.")

        self._azure_deployment_names = deployment_names # Cache the deployment names
        return deployment_names