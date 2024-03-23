# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.base_assistant_client import BaseAssistantClient
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.exceptions import EngineError, InvalidJSONError
from azure.ai.assistant.management.logger_module import logger
from typing import Optional
from typing_extensions import Literal, TypedDict
from openai.types.chat.completion_create_params import ResponseFormat
from datetime import datetime
import json, uuid
import copy


class ChatAssistantClient(BaseAssistantClient):
    """
    A class that manages an chat assistant client.

    :param config_json: The configuration data to use to create the chat client.
    :type config_json: str
    :param callbacks: The callbacks to use for the assistant client.
    :type callbacks: Optional[AssistantClientCallbacks]
    :param is_create: A flag to indicate if the assistant client is being created.
    :type is_create: bool
    :param timeout: The HTTP request timeout in seconds.
    :type timeout: Optional[float]
    """
    def __init__(
            self, 
            config_json: str,
            callbacks: Optional[AssistantClientCallbacks] = None,
            is_create: bool = True,
            timeout: Optional[float] = None
    ) -> None:
        super().__init__(config_json, callbacks)
        self._tools = None
        self._messages = []
        self._init_chat_assistant_client(self._config_data, is_create, timeout=timeout)

    @classmethod
    def from_json(
        cls,
        config_json: str,
        callbacks: Optional[AssistantClientCallbacks] = None,
        timeout: Optional[float] = None
    ) -> "ChatAssistantClient":
        """
        Creates a ChatAssistantClient instance from JSON configuration data.

        :param config_json: JSON string containing the configuration for the chat assistant.
        :type config_json: str
        :param callbacks: Optional callbacks for the chat assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :return: An instance of ChatAssistantClient.
        :rtype: ChatAssistantClient
        """
        try:
            config_data = json.loads(config_json)
            is_create = not ("assistant_id" in config_data and config_data["assistant_id"])
            return cls(config_json=config_json, callbacks=callbacks, is_create=is_create, timeout=timeout)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            raise InvalidJSONError(f"Invalid JSON format: {e}")

    @classmethod
    def from_config(
        cls,
        config: AssistantConfig,
        callbacks: Optional[AssistantClientCallbacks] = None,
        timeout: Optional[float] = None
    ) -> "ChatAssistantClient":
        """
        Creates a ChatAssistantClient instance from an AssistantConfig object.

        :param config: AssistantConfig object containing the configuration for the chat assistant.
        :type config: AssistantConfig
        :param callbacks: Optional callbacks for the chat assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :return: An instance of ChatAssistantClient.
        :rtype: ChatAssistantClient
        """
        try:
            config_json = config.to_json()
            is_create = not config.assistant_id
            return cls(config_json=config_json, callbacks=callbacks, is_create=is_create, timeout=timeout)
        except Exception as e:
            logger.error(f"Failed to create chat client from config: {e}")
            raise EngineError(f"Failed to create chat client from config: {e}")

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
            self._messages = [{"role": "system", "content": assistant_config.instructions}]
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

    def process_messages(
            self, 
            thread_name: Optional[str] = None,
            user_request: Optional[str] = None,
            additional_instructions: Optional[str] = None,
            timeout: Optional[float] = None,
            stream: Optional[bool] = False
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
                conversation_thread_client = ConversationThreadClient.get_instance(self._ai_client_type)
                conversation = conversation_thread_client.retrieve_conversation(thread_name, self._assistant_config.max_text_messages)
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

                text_completion_config = self._assistant_config.text_completion_config

                # Using a conditional expression to check if text_completion_config is not None before accessing its attributes
                temperature = None if text_completion_config is None else text_completion_config.temperature
                seed = None if text_completion_config is None else text_completion_config.seed
                frequency_penalty = None if text_completion_config is None else text_completion_config.frequency_penalty
                max_tokens = None if text_completion_config is None else text_completion_config.max_tokens
                presence_penalty = None if text_completion_config is None else text_completion_config.presence_penalty
                top_p = None if text_completion_config is None else text_completion_config.top_p
                response_format = None if text_completion_config is None else {'type': text_completion_config.response_format}

                # Now, use these variables in your API call
                response = self._ai_client.chat.completions.create(
                    model=self._assistant_config.model,
                    messages=self._messages,
                    tools=self._tools,
                    tool_choice=None if self._tools is None else "auto",
                    stream=stream,
                    temperature=temperature,
                    seed=seed,
                    frequency_penalty=frequency_penalty,
                    max_tokens=max_tokens,
                    presence_penalty=presence_penalty,
                    response_format=response_format,
                    top_p=top_p,
                    timeout=timeout
                )

                if response and stream:
                    continue_processing = self._handle_streaming_response(response, thread_name, run_id)
                elif response:
                    continue_processing = self._handle_non_streaming_response(response, thread_name, run_id)
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

    def _handle_non_streaming_response(self, response, thread_name, run_id):
        response_message = response.choices[0].message
        self._messages.append(response_message)

        if response_message.content:
            # extend conversation with assistant's reply
            if thread_name:
                conversation_thread_client = ConversationThreadClient.get_instance(self._ai_client_type)
                conversation_thread_client.create_conversation_thread_message(
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

    def _handle_streaming_response(self, response, thread_name, run_id):
        tool_calls, collected_messages = self._process_response_chunks(response, thread_name, run_id)
        self._process_tool_calls(tool_calls, run_id)
        self._update_conversation_with_messages(collected_messages, thread_name)
        return bool(tool_calls)  # Return True if there were tool calls processed, otherwise False

    def _process_response_chunks(self, response, thread_name, run_id):
        tool_calls = []
        collected_messages = []
        is_first_message = True

        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                self._callbacks.on_run_update(self._name, run_id, "streaming", thread_name, is_first_message, delta.content)
                collected_messages.append(delta.content)
                is_first_message = False
            if delta and delta.tool_calls:
                tool_calls = self._append_tool_calls(tool_calls, delta.tool_calls)

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

    def _process_tool_calls(self, tool_calls, run_id):
        if tool_calls:
            logger.info(f"Tool calls: {tool_calls}")
            self._messages.append({
                "tool_calls": tool_calls,
                "role": 'assistant',
            })
    
        for tool_call in tool_calls:
            function_response = self._handle_function_call(
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

    def _update_conversation_with_messages(self, collected_messages, thread_name):
        full_response = ''.join(filter(None, collected_messages))
        if full_response and thread_name:
            conversation_thread_client = ConversationThreadClient.get_instance(self._ai_client_type)
            conversation_thread_client.create_conversation_thread_message(
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