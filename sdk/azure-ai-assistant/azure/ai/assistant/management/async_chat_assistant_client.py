# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.base_assistant_client import BaseAssistantClient
from azure.ai.assistant.management.async_conversation_thread_client import AsyncConversationThreadClient
from azure.ai.assistant.management.exceptions import EngineError, InvalidJSONError
from azure.ai.assistant.management.logger_module import logger

from openai import AsyncAzureOpenAI, AsyncOpenAI

from typing import Optional, Union
from datetime import datetime
import json, uuid
import copy
import asyncio


class AsyncChatAssistantClient(BaseAssistantClient):
    """
    A class that manages an chat assistant client.

    Use the `from_json` or `from_config` factory methods to create an instance of this class.

    :param config_json: The configuration data to use to create the chat client.
    :type config_json: str
    :param callbacks: The callbacks to use for the assistant client.
    :type callbacks: Optional[AssistantClientCallbacks]
    """
    def __init__(
            self, 
            config_json: str,
            callbacks: Optional[AssistantClientCallbacks] = None
    ) -> None:
        super().__init__(config_json, callbacks, async_mode=True)
        self._tools = None
        self._messages = []
        self._async_client : Union[AsyncOpenAI, AsyncAzureOpenAI] = self._ai_client
        # Init with base settings, leaving async init for the factory method

    async def _async_init(
            self, 
            is_create: bool, 
            timeout: Optional[float]
    ):
        """
        An asynchronous initialization method that loads and sets up the assistant configuration.

        :param is_create: A flag to indicate if the assistant client is being created.
        :type is_create: bool
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]
        """
        await self._init_chat_assistant_client(self._config_data, is_create, timeout=timeout)

    @classmethod
    async def from_json(
        cls,
        config_json: str,
        callbacks: Optional[AssistantClientCallbacks] = None,
        timeout: Optional[float] = None
    ) -> "AsyncChatAssistantClient":
        """
        Creates a AsyncChatAssistantClient instance from JSON configuration data.

        :param config_json: JSON string containing the configuration for the chat assistant.
        :type config_json: str
        :param callbacks: Optional callbacks for the chat assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :return: An instance of AsyncChatAssistantClient.
        :rtype: AsyncChatAssistantClient
        """
        try:
            instance = cls(config_json, callbacks)  # Instance creation without async init
            config_data = json.loads(config_json)
            is_create = not ("assistant_id" in config_data and config_data["assistant_id"])
            await instance._async_init(is_create, timeout)  # Perform async initialization
            return instance
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            raise InvalidJSONError(f"Invalid JSON format: {e}")

    @classmethod
    async def from_config(
        cls,
        config: AssistantConfig,
        callbacks: Optional[AssistantClientCallbacks] = None,
        timeout: Optional[float] = None
    ) -> "AsyncChatAssistantClient":
        """
        Creates a AsyncChatAssistantClient instance from an AssistantConfig object.

        :param config: AssistantConfig object containing the configuration for the chat assistant.
        :type config: AssistantConfig
        :param callbacks: Optional callbacks for the chat assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :return: An instance of AsyncChatAssistantClient.
        :rtype: AsyncChatAssistantClient
        """
        try:
            instance = cls(config.to_json(), callbacks)  # Instance creation without async init
            is_create = not config.assistant_id
            await instance._async_init(is_create, timeout)  # Perform async initialization
            return instance
        except Exception as e:
            logger.error(f"Failed to create chat client from config: {e}")
            raise EngineError(f"Failed to create chat client from config: {e}")

    async def _init_chat_assistant_client(
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
            self._messages = [{"role": "system", "content": assistant_config.instructions}]
            self._update_tools(assistant_config)
            await asyncio.to_thread(self._load_selected_functions, assistant_config)
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

    async def process_messages(
            self, 
            thread_name: Optional[str] = None,
            user_request: Optional[str] = None,
            additional_instructions: Optional[str] = None,
            timeout: Optional[float] = None,
            stream: Optional[bool] = False,
            temperature: Optional[float] = None,
            seed: Optional[int] = None
    ) -> Optional[str]:
        """
        Process the messages in given thread.

        :param thread_name: The name of the thread to process.
        :type thread_name: Optional[str]
        :param user_request: The user request to process.
        :type user_request: Optional[str]
        :param additional_instructions: Additional instructions to provide to the assistant.
        :type additional_instructions: Optional[str]
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]
        :param stream: A flag to indicate if the response should be streamed.
        :type stream: Optional[bool]

        :return: The response from the assistant.
        :rtype: Optional[str]
        """
        # Ensure at least one of thread_name or user_request is provided
        if thread_name is None and user_request is None:
            raise ValueError("Either thread_name or user_request must be provided.")

        try:
            logger.info(f"Process messages for chat assistant")

            if additional_instructions:
                self._messages.append({"role": "system", "content": additional_instructions})

            # call the start_run callback
            run_start_time = str(datetime.now())
            run_id = str(uuid.uuid4())
            self._callbacks.on_run_start(self._name, run_id, run_start_time, "Processing user input")

            if thread_name:
                conversation_thread_client = AsyncConversationThreadClient.get_instance(self._ai_client_type)
                conversation = await conversation_thread_client.retrieve_conversation(thread_name)
                for message in reversed(conversation.text_messages):
                    if message.role == "user":
                        self._messages.append({"role": "user", "content": message.content})
                    if message.role == "assistant":
                        self._messages.append({"role": "assistant", "content": message.content})
            elif user_request:
                self._messages.append({"role": "user", "content": user_request})

            continue_processing = True
            self._user_input_processing_cancel_requested = False

            response = None
            while continue_processing:

                if self._user_input_processing_cancel_requested:
                    logger.info("User input processing cancellation requested.")
                    self._user_input_processing_cancel_requested = False
                    break

                response = await self._async_client.chat.completions.create(
                    model=self._assistant_config.model,
                    messages=self._messages,
                    tools=self._tools,
                    tool_choice=None if self._tools is None else "auto",
                    stream=stream,
                    temperature=temperature,
                    seed=seed,
                    timeout=timeout
                )

                if response and stream:
                    continue_processing = await self._handle_streaming_response(response, thread_name, run_id)
                elif response:
                    continue_processing = await self._handle_non_streaming_response(response, thread_name, run_id)
                else:
                    # If there's no response, stop the loop
                    continue_processing = False

            self._callbacks.on_run_update(self._name, run_id, "completed", thread_name)

            run_end_time = str(datetime.now())
            self._callbacks.on_run_end(self._name, run_id, run_end_time, thread_name)

            # clear the messages for other than system messages
            self._messages = [{"role": "system", "content": self._assistant_config.instructions}]

            if not stream:
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error occurred during processing run: {e}")
            raise EngineError(f"Error occurred during processing run: {e}")

    async def _handle_non_streaming_response(self, response, thread_name, run_id):
        response_message = response.choices[0].message
        self._messages.append(response_message)

        if response_message.content:
            # extend conversation with assistant's reply
            if thread_name:
                conversation_thread_client = AsyncConversationThreadClient.get_instance(self._ai_client_type)
                await conversation_thread_client.create_conversation_thread_message(
                    response_message.content,
                    thread_name,
                    metadata={"chat_assistant": self._name}
                )
            return False

        tool_calls = response_message.tool_calls
        if tool_calls != None:
            for tool_call in tool_calls:
                function_response = self._handle_function_call(tool_call.function.name, tool_call.function.arguments)
                self._callbacks.on_function_call_processed(self._name, run_id, tool_call.function.name, tool_call.function.arguments, str(function_response))
                self._messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_call.function.name,
                        "content": function_response,
                    }
                )
            return True

    async def _handle_streaming_response(self, response, thread_name, run_id):
        tool_calls, collected_messages = await self._process_response_chunks(response, thread_name, run_id)
        await self._process_tool_calls(tool_calls, run_id)
        await self._update_conversation_with_messages(collected_messages, thread_name)
        return bool(tool_calls)  # Return True if there were tool calls processed, otherwise False

    async def _process_response_chunks(self, response, thread_name, run_id):
        tool_calls = []
        collected_messages = []
        is_first_message = True

        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                self._callbacks.on_run_update(self._name, run_id, "streaming", thread_name, is_first_message, delta.content)
                collected_messages.append(delta.content)
                is_first_message = False
            if delta and delta.tool_calls:
                tool_calls = await asyncio.to_thread(self._append_tool_calls, tool_calls, delta.tool_calls)

        return tool_calls, collected_messages

    def _append_tool_calls(self, tool_calls, tcchunklist):
        for tcchunk in tcchunklist:
            while len(tool_calls) <= tcchunk.index:
                tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
            tc = tool_calls[tcchunk.index]
            tc["id"] += tcchunk.id or ""
            tc["function"]["name"] += tcchunk.function.name or ""
            tc["function"]["arguments"] += tcchunk.function.arguments or ""
        return tool_calls

    async def _process_tool_calls(self, tool_calls, run_id):
        if tool_calls:
            logger.info(f"Tool calls: {tool_calls}")
            self._messages.append({
                "tool_calls": tool_calls,
                "role": 'assistant',
            })
    
        for tool_call in tool_calls:
            function_response = await asyncio.to_thread(
                self._handle_function_call, 
                tool_call['function']['name'], 
                tool_call['function']['arguments']
            )
            self._callbacks.on_function_call_processed(
                self._name, run_id, 
                tool_call['function']['name'], 
                tool_call['function']['arguments'], 
                str(function_response)
            )

            # Appending the processed tool call and its response to self._messages
            self._messages.append({
                "tool_call_id": tool_call['id'],
                "role": "tool",
                "name": tool_call['function']['name'],
                "content": str(function_response),  # Ensure content is stringified if necessary
            })

    async def _update_conversation_with_messages(self, collected_messages, thread_name):
        full_response = ''.join(filter(None, collected_messages))
        if full_response and thread_name:
            conversation_thread_client = AsyncConversationThreadClient.get_instance(self._ai_client_type)
            await conversation_thread_client.create_conversation_thread_message(
                message=full_response, 
                thread_name=thread_name, 
                metadata={"chat_assistant": self._name}
            )
            logger.info("Messages updated in conversation.")

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