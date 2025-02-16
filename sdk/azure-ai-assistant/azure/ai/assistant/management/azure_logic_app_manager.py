# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from typing import Any, Dict, List, Optional
from datetime import datetime

from azure.identity import DefaultAzureCredential
from azure.mgmt.logic import LogicManagementClient
from azure.ai.assistant.management.logger_module import logger


class AzureLogicAppManager:
    _instance = None
    """
    A manager to handle Azure Logic Apps by listing available workflows,
    retrieving callback URLs, and invoking the apps with a payload.
    """

    def __init__(self, subscription_id: str, resource_group: str) -> None:
        """
        Initializes the manager with the given subscription and resource group.
        Creates a LogicManagementClient using DefaultAzureCredential.
        
        :param subscription_id: Azure subscription ID.
        :param resource_group: Azure resource group containing the Logic Apps.
        """
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.credential = DefaultAzureCredential()
        self.logic_client = LogicManagementClient(self.credential, self.subscription_id)
        # Dictionary to store callback URLs for registered Logic Apps.
        self._logic_app_callback_urls: Dict[str, str] = {}
        # Set to cache logic app names
        self._logic_app_names: set[str] = set()
        self._initialized = False

    @classmethod
    def get_instance(cls, subscription_id: str = None, resource_group: str = None) -> 'AzureLogicAppManager':
        """
        Returns a singleton instance of AzureLogicAppManager.
        
        After the singleton has been created, you can call this method without parameters.
        
        :param subscription_id: Azure subscription id (required if instance doesn't exist).
        :param resource_group: Azure resource group (required if instance doesn't exist).
        :return: AzureLogicAppManager instance.
        """
        if cls._instance is None:
            if subscription_id is None or resource_group is None:
                raise ValueError("subscription_id and resource_group must be provided for the first instantiation.")
            cls._instance = cls(subscription_id, resource_group)
        return cls._instance

    def list_logic_apps(self) -> List[str]:
        """
        If the manager is not yet initialized, returns an empty list.
        Otherwise, returns a sorted list of the Logic App names with (HTTP Trigger) suffix.
        
        :return: A list of logic app names, or an empty list if not initialized.
        """
        if not self._initialized:
            logger.warning("list_logic_apps was called before initialize_logic_apps. Returning empty list.")
            return []
        return sorted([f"{name} (HTTP Trigger)" for name in self._logic_app_names])

    def register_logic_app(self, logic_app_name: str, trigger_name: str) -> None:
        """
        Retrieves and stores the callback URL for a specific Logic App and trigger,
        but only if it has not been registered already.
        Raises a ValueError if no callback URL is found.
        
        :param logic_app_name: The name of the logic app.
        :param trigger_name: The name of the trigger (usually the HTTP trigger).
        """
        # Check if already registered; if so, skip registration.
        if logic_app_name in self._logic_app_callback_urls:
            logger.info(f"Logic App '{logic_app_name}' is already registered; skipping re-registration.")
            return

        try:
            callback = self.logic_client.workflow_triggers.list_callback_url(
                resource_group_name=self.resource_group,
                workflow_name=logic_app_name,
                trigger_name=trigger_name,
            )
            if callback.value is None:
                raise ValueError(f"No callback URL returned for Logic App '{logic_app_name}'.")
            self._logic_app_callback_urls[logic_app_name] = callback.value
            logger.info(f"Logic App '{logic_app_name}' registered with callback URL.")
        except Exception as e:
            logger.error(f"Error registering logic app '{logic_app_name}': {e}")
            raise e

    def initialize_logic_apps(self, trigger_name: str = "manual") -> None:
        """
        Initializes the Logic App manager by listing all available Logic Apps
        in the resource group and registering each one with the specified trigger.
        Sets the _initialized flag on successful completion.
        
        :param trigger_name: The trigger name to use for registration (default is "manual").
        """
        try:
            workflows = self.logic_client.workflows.list_by_resource_group(self.resource_group)
            for workflow in workflows:
                self._logic_app_names.add(workflow.name)
                try:
                    self.register_logic_app(workflow.name, trigger_name)
                except Exception as register_ex:
                    logger.error(f"Failed to register Logic App '{workflow.name}': {register_ex}")
            
            # Mark as initialized once listing/registration is done
            self._initialized = True
            logger.info("Logic Apps have been successfully initialized.")
        except Exception as e:
            logger.error(f"Error during initialize_logic_apps: {e}")

    def get_callback_url(self, logic_app_name: str) -> Optional[str]:
        """
        Retrieves the stored callback URL for the given logic app.
        
        :param logic_app_name: The name of the logic app.
        :return: The callback URL if registered, otherwise None.
        """
        return self._logic_app_callback_urls.get(logic_app_name)

    def invoke_logic_app(self, logic_app_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes the specified Logic App (by using its callback URL) with the given payload.
        
        :param logic_app_name: The name of the logic app.
        :param payload: A dictionary representing the JSON payload.
        :return: A dictionary summarizing success or error details.
        """
        import requests
        callback_url = self.get_callback_url(logic_app_name)
        if not callback_url:
            raise ValueError(f"Logic App '{logic_app_name}' has not been registered with a callback URL.")
        response = requests.post(url=callback_url, json=payload)
        if response.ok:
            return response.json()
        else:
            return {
                "error": f"Error invoking {logic_app_name} ({response.status_code}): {response.text}"
            }

    def get_http_trigger_schema(self, logic_app_name: str, trigger_name: str = "manual") -> Dict[str, Any]:
        """
        Retrieves the JSON schema (or details) for the specified HTTP trigger of a Logic App.
        This method attempts to retrieve the workflow definition and extract details about the trigger.
        
        :param logic_app_name: The name of the logic app.
        :param trigger_name: The name of the trigger (default is "manual").
        :return: A dictionary representing the JSON schema or details of the trigger.
        """
        try:
            workflow = self.logic_client.workflows.get(self.resource_group, logic_app_name)
            definition = getattr(workflow, "definition", {}) or {}
            triggers = definition.get("triggers", {})
            trigger = triggers.get(trigger_name, {})
            schema = trigger.get("inputs", {}).get("schema", {})
            return schema
        except Exception as e:
            logger.error(f"Error getting HTTP trigger schema for '{logic_app_name}': {e}")
            return {}

    def get_logic_app_details(self, logic_app_name: str) -> Dict[str, Any]:
        """
        Retrieves detailed information for the specified Logic App, including workflow metadata,
        callback URL, HTTP trigger schema, parameters, triggers information, and other relevant properties.
        
        :param logic_app_name: The name of the logic app.
        :return: A dictionary containing the Logic App's details.
        """
        try:
            workflow = self.logic_client.workflows.get(self.resource_group, logic_app_name)
            definition = getattr(workflow, "definition", {}) or {}
            
            details = {
                "name": workflow.name,
                "id": getattr(workflow, "id", "N/A"),
                "type": getattr(workflow, "type", "N/A"),
                "location": getattr(workflow, "location", "N/A"),
                "provisioning_state": getattr(workflow, "provisioning_state", "Unknown"),
                "state": getattr(workflow, "state", "Unknown"),
                "created_time": getattr(workflow, "created_time", datetime.now()),
                "changed_time": getattr(workflow, "changed_time", datetime.now()),
                "access_endpoint": self.get_callback_url(logic_app_name) or "Not Registered",
                "tags": workflow.tags if hasattr(workflow, "tags") and workflow.tags is not None else {},
                "parameters": definition.get("parameters", {}),
                "triggers": definition.get("triggers", {}),
                "actions": definition.get("actions", {}),
            }
            return details
        except Exception as e:
            logger.error(f"Error getting details for logic app '{logic_app_name}': {e}")
            return {"error": str(e)}