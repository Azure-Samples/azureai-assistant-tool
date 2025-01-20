# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.base_assistant_client import BaseAssistantClient
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.exceptions import EngineError
from azure.ai.assistant.management.logger_module import logger

from typing import Optional
import uuid


class BaseChatAssistantClient(BaseAssistantClient):
    """
    Base class for chat assistant clients.

    :param config_json: The JSON string containing the assistant configuration.
    :type config_json: str
    :param callbacks: The callback functions to handle messages from the assistant.
    :type callbacks: Optional[AssistantClientCallbacks]
    :param async_mode: Whether to run the assistant in async mode.
    :type async_mode: bool
    :param client_args: Additional keyword arguments for configuring the AI client.
    :type client_args: Dict
    """
    def __init__(
            self,
            config_json: str,
            callbacks: Optional[AssistantClientCallbacks] = None,
            async_mode: bool = False,
            **client_args
    ) -> None:
        super().__init__(config_json, callbacks, async_mode, **client_args)
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
            tools = self._update_tools(assistant_config)
            self._tools = tools if tools else None
            self._load_selected_functions(assistant_config)
            self._assistant_config = assistant_config

            # Update the local configuration using AssistantConfigManager
            # TODO make optional to save the assistant_config in the config manager
            config_manager = AssistantConfigManager.get_instance()
            config_manager.update_config(self._name, assistant_config.to_json())

        except Exception as e:
            logger.error(f"Failed to initialize assistant instance: {e}")
            raise EngineError(f"Failed to initialize assistant instance: {e}")

    def _purge(
            self,
            timeout: Optional[float] = None
    )-> None:
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

    def _reset_system_messages(self, assistant_config: AssistantConfig):
        instructions = self._replace_file_references_with_content(assistant_config)
        self._messages = [{"role": "developer", "content": instructions}]

    def _parse_conversation_messages(self, messages):
        for message in reversed(messages):
            content = []
            if message.text_message:
                content.append({"type": "text", "text": message.text_message.content})
            if len(message.image_messages) > 0:
                for image_message in message.image_messages:
                    img_base64 = image_message.get_image_base64()
                    if img_base64:
                        img_str = f"data:image/jpeg;base64,{img_base64}"
                        content.append({"type": "image_url", "image_url": {"url": img_str, "detail": "high"}})
            if message.image_urls:
                for image_url in message.image_urls:
                    content.append({"type": "image_url", "image_url": {"url": image_url, "detail": "high"}})
            if content:
                self._messages.append({"role": message.role, "content": content})