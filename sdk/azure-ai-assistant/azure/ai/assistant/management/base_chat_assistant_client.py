# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.base_assistant_client import BaseAssistantClient
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.exceptions import EngineError
from azure.ai.assistant.management.logger_module import logger

from typing import Optional
import copy, uuid


class BaseChatAssistantClient(BaseAssistantClient):
    """
    Base class for chat assistant clients.

    :param config_json: The JSON string containing the assistant configuration.
    :type config_json: str
    :param callbacks: The callback functions to handle messages from the assistant.
    :type callbacks: Optional[AssistantClientCallbacks]
    :param async_mode: Whether to run the assistant in async mode.
    :type async_mode: bool
    """
    def __init__(
            self,
            config_json: str,
            callbacks: Optional[AssistantClientCallbacks] = None,
            async_mode: bool = False
    ) -> None:
        super().__init__(config_json, callbacks, async_mode)
        self._tools = None
        self._messages = []

    def _init_chat_assistant_client(
            self, 
            config_data: dict,
            is_create: bool = True,
            timeout: Optional[float] = None
    ):
        try:
            # Create or update the assistant
            assistant_config = AssistantConfig.from_dict(config_data)
            if is_create:
                assistant_config.assistant_id = str(uuid.uuid4())
            self._reset_system_messages(assistant_config)
            self._update_tools(assistant_config)
            self._load_selected_functions(assistant_config)
            self._assistant_config = assistant_config

            # Update the local configuration using AssistantConfigManager
            # TODO make optional to save the assistant_config in the config manager
            config_manager = AssistantConfigManager.get_instance()
            config_manager.update_config(self._name, assistant_config.to_json())

        except Exception as e:
            logger.error(f"Failed to initialize assistant instance: {e}")
            raise EngineError(f"Failed to initialize assistant instance: {e}")

    def purge(
            self,
            timeout: Optional[float] = None
    )-> None:
        """
        Purges the chat assistant from the local configuration.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        try:
            logger.info(f"Purging chat assistant with name: {self.name}")
            # retrieve the assistant configuration
            config_manager = AssistantConfigManager.get_instance()
            assistant_config = config_manager.get_config(self.name)

            # remove from the local config
            config_manager.delete_config(assistant_config.name)

            self._clear_variables()

        except Exception as e:
            logger.error(f"Failed to purge chat assistant with name: {self.name}: {e}")
            raise EngineError(f"Failed to purge chat assistant with name: {self.name}: {e}")

    def _append_tool_calls(self, tool_calls, tcchunklist):
        for tcchunk in tcchunklist:
            while len(tool_calls) <= tcchunk.index:
                tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
            tc = tool_calls[tcchunk.index]
            tc["id"] += tcchunk.id or ""
            tc["function"]["name"] += tcchunk.function.name or ""
            tc["function"]["arguments"] += tcchunk.function.arguments or ""
        return tool_calls

    def _update_tools(self, assistant_config: AssistantConfig):
        logger.info(f"Updating tools for assistant: {assistant_config.name}")
        if assistant_config.selected_functions:
            self._tools = []
            modified_functions = []
            for function in assistant_config.selected_functions:
                # Create a copy of the function spec to avoid modifying the original
                modified_function = copy.deepcopy(function)
                # Remove the module field from the function spec
                if "function" in modified_function and "module" in modified_function["function"]:
                    del modified_function["function"]["module"]
                modified_functions.append(modified_function)
            self._tools.extend(modified_functions)
        else:
            self._tools = None

    def _reset_system_messages(self, assistant_config: AssistantConfig):
        instructions = self._replace_file_references_with_content(assistant_config)
        self._messages = [{"role": "system", "content": instructions}]