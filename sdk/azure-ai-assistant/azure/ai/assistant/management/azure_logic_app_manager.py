# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from typing import Any, Dict, List, Optional

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

    @classmethod
    def get_instance(cls, subscription_id: str, resource_group: str) -> 'AzureLogicAppManager':
        """
        Returns a singleton instance of AzureLogicAppManager.
        
        :param subscription_id: Azure subscription id.
        :param resource_group: Azure resource group.
        :return: AzureLogicAppManager instance.
        """
        if cls._instance is None:
            cls._instance = cls(subscription_id, resource_group)
        return cls._instance

    def list_logic_apps(self) -> List[str]:
        """
        Lists all the Logic Apps (workflows) in the specified resource group.
        Each name is suffixed with "(HTTP Trigger)" as an indicator.
        
        :return: A list of logic app names.
        """
        names = []
        try:
            workflows = self.logic_client.workflows.list_by_resource_group(self.resource_group)
            for workflow in workflows:
                names.append(f"{workflow.name} (HTTP Trigger)")
        except Exception as e:
            logger.error(f"Error listing logic apps: {e}")
        return names

    def register_logic_app(self, logic_app_name: str, trigger_name: str) -> None:
        """
        Retrieves and stores the callback URL for a specific Logic App and trigger.
        Raises a ValueError if no callback URL is found.
        
        :param logic_app_name: The name of the logic app.
        :param trigger_name: The name of the trigger (usually the HTTP trigger).
        """
        try:
            callback = self.logic_client.workflow_triggers.list_callback_url(
                resource_group_name=self.resource_group,
                workflow_name=logic_app_name,
                trigger_name=trigger_name,
            )
            if callback.value is None:
                raise ValueError(f"No callback URL returned for Logic App '{logic_app_name}'.")
            self._logic_app_callback_urls[logic_app_name] = callback.value
        except Exception as e:
            logger.error(f"Error registering logic app '{logic_app_name}': {e}")
            raise e

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
            return {"result": f"Successfully invoked {logic_app_name}."}
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
            # Retrieve the workflow which may include its definition.
            workflow = self.logic_client.workflows.get(self.resource_group, logic_app_name)
            # The workflow's definition, if deployed via ARM templates, should be a dictionary.
            definition = getattr(workflow, "definition", {}) or {}
            triggers = definition.get("triggers", {})
            trigger = triggers.get(trigger_name, {})
            # Extract the schema from the trigger inputs.
            schema = trigger.get("inputs", {}).get("schema", {})
            return schema
        except Exception as e:
            logger.error(f"Error getting HTTP trigger schema for '{logic_app_name}': {e}")
            return {}