# azure_function_manager.py
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from typing import Any, Dict, List, Optional
from datetime import datetime

from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient
from azure.core.exceptions import HttpResponseError
from azure.ai.assistant.management.logger_module import logger


class AzureFunctionManager:
    """
    A manager to handle Azure Function Apps by listing available Function Apps,
    retrieving function details, and providing metadata about each function.
    
    """

    _instance = None

    def __init__(self, subscription_id: str, resource_group: str) -> None:
        """
        Initializes the manager with the given subscription and resource group.
        Creates a WebSiteManagementClient using DefaultAzureCredential.

        :param subscription_id: Azure subscription ID.
        :param resource_group: Azure resource group containing the Azure Function Apps.
        """
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.credential = DefaultAzureCredential()
        self.web_client = WebSiteManagementClient(self.credential, self.subscription_id)

        # A set or list to store discovered Azure Function App names once initialized.
        self._function_app_names: set[str] = set()

        # Track whether we’ve loaded the function apps yet.
        self._initialized = False

    @classmethod
    def get_instance(cls, subscription_id: str = None, resource_group: str = None) -> 'AzureFunctionManager':
        """
        Returns a singleton instance of AzureFunctionManager.

        After you create the singleton the first time (with subscription_id and resource_group),
        you can retrieve it subsequently without parameters.

        :param subscription_id: Azure subscription id (required if instance doesn't exist).
        :param resource_group: Azure resource group (required if instance doesn't exist).
        :return: AzureFunctionManager instance.
        """
        if cls._instance is None:
            if subscription_id is None or resource_group is None:
                raise ValueError("subscription_id and resource_group must be provided the first time.")
            cls._instance = cls(subscription_id, resource_group)
        return cls._instance

    def initialize_function_apps(self) -> None:
        """
        Enumerates all function apps (Web Apps with kind="functionapp") in the given resource group,
        storing their names in _function_app_names. 
        """
        try:
            apps = self.web_client.web_apps.list_by_resource_group(self.resource_group)
            for app in apps:
                # Many Azure Function Apps have kind="functionapp". 
                # Some might be "functionapp,linux" or "functionapp,linux,container" etc.
                if app.kind and "functionapp" in app.kind.lower():
                    self._function_app_names.add(app.name)
            self._initialized = True
            logger.info("Azure Function Apps have been successfully initialized.")
        except HttpResponseError as e:
            logger.error(f"Error during initialize_function_apps: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during initialize_function_apps: {e}")

    def list_function_apps(self) -> List[str]:
        """
        Returns a sorted list of the Azure Function App names that have been initialized.
        If initialize_function_apps has not been called, returns an empty list.
        """
        if not self._initialized:
            logger.warning("list_function_apps was called before initialize_function_apps. Returning empty list.")
            return []
        return sorted(self._function_app_names)

    def get_function_app_details(self, function_app_name: str) -> Dict[str, Any]:
        """
        Retrieves detailed information for the specified Azure Function App,
        including provisioning state, location, tags, etc.

        :param function_app_name: The name of the Function App.
        :return: A dictionary containing details about the Function App.
        """
        try:           
            # Retrieve Application Settings (app settings contain connection strings)
            app_config = self.web_client.web_apps.list_application_settings(
                self.resource_group, function_app_name
            )

            app_settings = app_config.properties
            return app_settings
        except HttpResponseError as e:
            logger.error(f"Error retrieving Function App '{function_app_name}': {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error retrieving Function App '{function_app_name}': {e}")
            return {"error": str(e)}

    def list_azure_functions_in_app(self, function_app_name: str) -> List[Dict[str, Any]]:
        """
        Lists the individual Azure Functions within the specified Function App,
        returning essential metadata for each (function name, trigger types, etc.).

        :param function_app_name: The name of the Function App.
        :return: A list of dictionaries with metadata for each function.
        """
        try:
            functions = self.web_client.web_apps.list_functions(self.resource_group, function_app_name)
            result = []
            for func in functions:
                func_details = {
                    "name": func.name,  # typically "functionAppName/functions/functionName"
                    "function_app_name": function_app_name,
                }
                
                config = getattr(func, "config", {})
                if isinstance(config, dict):
                    func_details["bindings"] = config.get("bindings", [])
                else:
                    func_details["bindings"] = []

                result.append(func_details)
            return result
        except HttpResponseError as e:
            logger.error(f"Error listing functions in Function App '{function_app_name}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing functions in '{function_app_name}': {e}")
            return []

    def get_function_details(self, function_app_name: str, function_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves details for a specific function within a Function App by name.
        Because the Azure management library only returns a list of all functions,
        we filter the list to find the matching function_name.

        :param function_app_name: Name of the Function App.
        :param function_name: The short name of the function (e.g., "GetWeather").
        :return: A dictionary of details about the function, or None if not found.
        """
        try:
            all_functions = self.list_azure_functions_in_app(function_app_name)
            for fn in all_functions:
                full_name: str = fn["name"]
                if full_name == function_name:
                    return fn
            return None
        except Exception as e:
            logger.error(f"Error getting details for function '{function_name}' in app '{function_app_name}': {e}")
            return None