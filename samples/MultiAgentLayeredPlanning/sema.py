# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.async_assistant_client import AsyncAssistantClient
from azure.ai.assistant.management.async_chat_assistant_client import AsyncChatAssistantClient
from azure.ai.assistant.management.async_task_manager import AsyncTaskManager

from samples.MultiAgentLayeredPlanning.multi_agent_orchestrator import MultiAgentOrchestrator

from typing import Dict, List


class SWEngineeringManagerAgent(AsyncChatAssistantClient):

    def __init__(self, conversation_client):
        self.lead_agents = {}
        self.conversation_client = conversation_client
        self.assistant_names = ["FileCreatorAgent"]
        self.orchestrator = MultiAgentOrchestrator()
        self.assistants = None
        self.task_manager = None

    async def async_init(self):
        # Perform all asynchronous initializations here
        self.assistants = await self.initialize_assistants(self.assistant_names, self.orchestrator)
        self.task_manager = AsyncTaskManager(self.orchestrator)

    def load_assistant_config(self, assistant_name: str) -> Dict:
        """
        Loads the YAML configuration for a given assistant.
        """
        try:
            with open(f"config/{assistant_name}_assistant_config.yaml", "r") as file:
                return file.read()
        except Exception as e:
            print(f"Error loading assistant configuration for {assistant_name}: {e}")
            return None

    async def initialize_assistants(self, assistant_names: List[str], orchestrator: MultiAgentOrchestrator) -> Dict[str, AsyncAssistantClient]:
        """
        Initializes all assistants based on their names and configuration files.
        """
        assistants = {}
        for assistant_name in assistant_names:
            config = self.load_assistant_config(assistant_name)
            if config:
                if assistant_name == "TaskPlannerAgent" or assistant_name == "FileCreatorAgent":
                    assistants[assistant_name] = await AsyncChatAssistantClient.from_yaml(config, callbacks=orchestrator)
                else:
                    assistants[assistant_name] = await AsyncAssistantClient.from_yaml(config, callbacks=orchestrator)
        orchestrator.assistants = assistants
        return assistants


    async def delegate_tasks_to_leads(self, customer_requirements):
        high_level_tasks = self.analyze_requirements(customer_requirements)
        for domain, task in high_level_tasks.items():
            if domain in self.lead_agents:
                detailed_tasks = await self.lead_agents[domain].create_detailed_tasks(task)
                await self.lead_agents[domain].assign_tasks_to_engineers(detailed_tasks)