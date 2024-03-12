# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.ai_client_factory import AIClientFactory
from azure.ai.assistant.management.ai_client_factory import AIClientType
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.conversation_thread_config import ConversationThreadConfig
from azure.ai.assistant.management.exceptions import EngineError, InvalidJSONError
from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.functions.system_function_mappings import system_functions
from typing import Optional
from openai import AzureOpenAI, OpenAI
from typing import Union
from datetime import datetime
from collections import defaultdict
import json, time, importlib, sys, os, uuid
import copy


class ChatAssistantClient:
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
        try:
            # Parse the configuration data
            config_data = json.loads(config_json)

            # Validate that 'name' is present and not empty
            if "name" not in config_data or not config_data["name"].strip():
                logger.error("The 'name' field in config_data cannot be empty")
                raise ValueError("The 'name' field in config_data cannot be empty")

            # Validate that 'ai_client_type' is present
            if "ai_client_type" not in config_data:
                logger.error("The 'ai_client_type' field is required in config_data")
                raise ValueError("The 'ai_client_type' field is required in config_data")
            
            # validate that 'model' is present
            if "model" not in config_data:
                logger.error("The 'model' field is required in config_data")
                raise ValueError("The 'model' field is required in config_data")

            ai_client_type_str = config_data["ai_client_type"]
            try:
                self._ai_client_type = AIClientType[ai_client_type_str]
            except KeyError:
                error_message = f"Invalid AI client type specified: '{ai_client_type_str}'. Must be one of {[e.name for e in AIClientType]}"
                logger.error(error_message)
                raise ValueError(error_message)

            self._name = config_data["name"]
            client_factory = AIClientFactory.get_instance()
            self._ai_client: Union[OpenAI, AzureOpenAI] = client_factory.get_client(self._ai_client_type)
            self._callbacks = callbacks if callbacks is not None else AssistantClientCallbacks()
            self._functions = {}
            self._user_input_processing_cancel_requested = False
            self._tools = None
            self._messages = []

            # Initialize the assistant client (create or update)
            self._init_chat_assistant_client(config_data, is_create, timeout=timeout)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            raise InvalidJSONError(f"Invalid JSON format: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize chat assistant client: {e}")
            raise EngineError(f"Failed to initialize chat assistant client: {e}")

    @classmethod
    def from_json(
        cls, 
        config_json : str,
        callbacks: Optional[AssistantClientCallbacks] = None,
        timeout: Optional[float] = None
    ) -> "ChatAssistantClient":
        """
        Creates a new chat assistant client from the given configuration data.

        :param config_json: The configuration data to use to create the chat client.
        :type config_json: str
        :param callbacks: The callbacks to use for the assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: The new chat assistant client.
        :rtype: ChatAssistantClient
        """
        try:
            # check if config_json contains assistant_id which is not null or empty, if so, set is_create to False
            config_data = json.loads(config_json)
            if "assistant_id" in config_data and config_data["assistant_id"]:
                return ChatAssistantClient(config_json=config_json, callbacks=callbacks, is_create=False, timeout=timeout)
            else:
                return ChatAssistantClient(config_json=config_json, callbacks=callbacks, is_create=True, timeout=timeout)
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
        Creates a new chat assistant client from the given configuration.

        :param config: The configuration to use to create the assistant client.
        :type config: AssistantConfig
        :param callbacks: The callbacks to use for the assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: The new chat assistant client.
        :rtype: ChatAssistantClient
        """
        try:
            # check if config contains assistant_id which is not null or empty, if so, set is_create to False
            if config.assistant_id:
                return ChatAssistantClient(config.to_json(), callbacks, is_create=False, timeout=timeout)
            else:
                return ChatAssistantClient(config.to_json(), callbacks, is_create=True, timeout=timeout)
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

    def _clear_variables(self):
        # clear the local variables
        self._assistant_config = None
        self._functions = {}
        self._ai_client = None
        self._user_input_processing_cancel_requested = False
        self._ai_client_type = None
        self._name = None
        self._tools = None

    def process_messages(
            self, 
            thread_name: Optional[str] = None,
            user_request: Optional[str] = None,
            additional_instructions: Optional[str] = None,
            timeout: Optional[float] = None,
            stream: Optional[bool] = True,
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

        assistant_config_manager = AssistantConfigManager.get_instance()
        assistant_config = assistant_config_manager.get_config(self._name)
        assistant_id = assistant_config.assistant_id
        if thread_name:
            conversation_thread_client = ConversationThreadClient.get_instance(self._ai_client_type)
            threads_config : ConversationThreadConfig = conversation_thread_client.get_config()
            thread_id = threads_config.get_thread_id_by_name(thread_name)

        try:
            logger.info(f"Process messages for chat assistant: {assistant_id}")

            if additional_instructions:
                self._messages.append({"role": "system", "content": additional_instructions})

            # call the start_run callback
            run_start_time = str(datetime.now())
            run_id = str(uuid.uuid4())
            self._callbacks.on_run_start(self._name, run_id, run_start_time, "Processing user input")

            if thread_name:
                conversation = conversation_thread_client.retrieve_conversation(thread_name)
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

                response = self._ai_client.chat.completions.create(
                    model=assistant_config.model,
                    messages=self._messages,
                    tools=self._tools,
                    tool_choice=None if self._tools is None else "auto",
                    stream=stream,
                    temperature=temperature,
                    seed=seed,
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
            self._messages = [{"role": "system", "content": assistant_config.instructions}]

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
        tool_calls = []
        collected_messages = []
        is_first_message = True

        for chunk in response:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if delta and delta.content:
                chunk_message = delta.content
                collected_messages.append(chunk_message)
                self._callbacks.on_run_update(self._name, run_id, "streaming", thread_name, is_first_message, chunk_message)
                is_first_message = False

            elif delta and delta.tool_calls:
                tcchunklist = delta.tool_calls
                for tcchunk in tcchunklist:
                    if len(tool_calls) <= tcchunk.index:
                        tool_calls.append({"id": "", "type": "function", "function": { "name": "", "arguments": "" } })
                    tc = tool_calls[tcchunk.index]

                    if tcchunk.id:
                        tc["id"] += tcchunk.id
                    if tcchunk.function.name:
                        tc["function"]["name"] += tcchunk.function.name
                    if tcchunk.function.arguments:
                        tc["function"]["arguments"] += tcchunk.function.arguments

        if tool_calls:
            logger.info(f"Tool calls: {tool_calls}")
            self._messages.append(
                {
                    "tool_calls": tool_calls,
                    "role": 'assistant',
                }
            )

        for tool_call in tool_calls:
            function_response = self._handle_function_call(tool_call['function']['name'], tool_call['function']['arguments'])
            self._callbacks.on_function_call_processed(self._name, run_id, tool_call['function']['name'], tool_call['function']['arguments'], str(function_response))

            self._messages.append(
                {
                    "tool_call_id": tool_call['id'],
                    "role": "tool",
                    "name": tool_call['function']['name'],
                    "content": function_response,
                }
            )

        if tool_calls:
            logger.info("Tool calls processed, return True and continue the loop")
            return True

        collected_messages = [m for m in collected_messages if m is not None]
        full_response = ''.join([m for m in collected_messages])

        # extend conversation with assistant's reply for the full response
        if full_response and thread_name:
            conversation_thread_client = ConversationThreadClient.get_instance(self._ai_client_type)
            conversation_thread_client.create_conversation_thread_message(
                full_response,
                thread_name,
                metadata={"chat_assistant": self._name}
            )
        logger.info("No tool calls, return False and stop the loop")
        return False

    def cancel_processing(self) -> None:
        """
        Cancels the processing of the user input.

        :return: None
        :rtype: None
        """
        logger.info("User processing run cancellation requested.")
        self._user_input_processing_cancel_requested = True

    def _update_arguments(self, args):
        """
        Updates the arguments if they contain '/mnt/data/'.
        """
        updated_args = {}
        for key, value in args.items():
            if isinstance(value, str) and '/mnt/data/' in value:
                assistant_config = AssistantConfigManager.get_instance().get_config(self._name)
                replacement_path = assistant_config.output_folder_path
                if not replacement_path.endswith('/'):
                    replacement_path += '/'
                updated_value = value.replace('/mnt/data/', replacement_path)
                updated_args[key] = updated_value
            else:
                updated_args[key] = value
        return updated_args

    def _handle_function_call(self, function_name, function_arguments):
        logger.info(f"Handling function call: {function_name} with arguments: {function_arguments}")

        function_to_call = self._functions.get(function_name)
        if function_to_call:
            try:
                function_args = json.loads(function_arguments)
            except json.JSONDecodeError:
                logger.error(f"Function {function_name} has invalid arguments.")
                return json.dumps({"function_error": function_name, "error": "Invalid JSON arguments."})
            
            # Update the arguments if necessary
            function_args = self._update_arguments(function_args)

            logger.info(f"Calling function: {function_name} with arguments: {function_args}")
            try:
                function_response = function_to_call(**function_args)
                return function_response
            except Exception as e:
                logger.error(f"Error in function call: {function_name}. Error: {str(e)}")
                return json.dumps({"function_error": function_name, "error": str(e)})
        else:
            logger.error(f"Function: {function_name} is not available.")
            return json.dumps({"function_error": function_name, "error": "Function is not available."})

    def _load_selected_functions(self, assistant_config: AssistantConfig):
        functions = {}

        try:
            for func_spec in assistant_config.selected_functions:
                logger.info(f"Loading selected function: {func_spec['function']['name']}")
                function_name = func_spec["function"]["name"]
                module_name = func_spec["function"].get("module", "default.module.path")

                # Check if it is a system function
                if function_name in system_functions:
                    functions[function_name] = system_functions[function_name]
                elif module_name.startswith("functions"):
                    # Dynamic loading for user-defined functions
                    functions[function_name] = self._import_user_function_from_module(module_name, function_name)
                else:
                    logger.error(f"Invalid module name: {module_name}")
                    raise EngineError(f"Invalid module name: {module_name}")
                self._functions = functions
        except Exception as e:
            logger.error(f"Error loading selected functions for assistant: {e}")
            raise EngineError(f"Error loading selected functions for assistant: {e}")

    def _import_system_function_from_module(self, module_name, function_name):
        try:
            logger.info(f"Importing system function: {function_name} from module: {module_name}")
            module = importlib.import_module(module_name)
            # Retrieve the function from the imported module
            return getattr(module, function_name)
        except Exception as e:
            logger.error(f"Error importing system {function_name} from {module_name}: {e}")
            raise EngineError(f"Error importing system {function_name} from {module_name}: {e}")

    def _import_user_function_from_module(self, module_name, function_name):
        try:
            logger.info(f"Importing user function: {function_name} from module: {module_name}")
            module_path = self._get_module_path(module_name)
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if module_name in sys.modules:
                logger.info("Module is loaded, reloading...")
                # Reload the module if it's already loaded
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module  # Update sys.modules with the reloaded module
            else:
                logger.info("Module is not loaded, loading from scratch")
                # Import the module for the first time
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module  # Add it to sys.modules
            spec.loader.exec_module(module)
            return getattr(module, function_name)
        except Exception as e:
            logger.error(f"Error importing {function_name} from {module_name}: {e}")
            return None

    def _get_module_path(self, module_name):
        logger.info("Module_name: {}".format(module_name))
        if getattr(sys, 'frozen', False):
            # Path for PyInstaller bundle
            base_path = os.path.join(os.path.expanduser("~"), 'AssistantStudioData')
            module_path = os.path.join(base_path, module_name.replace('.', os.sep) + '.py')
            logger.info("Module path: {}".format(module_path))
        else:
            # Path for normal Python environment
            module_path = os.path.join(module_name.replace('.', os.sep) + '.py')
            logger.info("Module path: {}".format(module_path))
        return module_path

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

    @property
    def name(self) -> str:
        """
        The name of the chat assistant.

        :return: The name of the chat assistant.
        :rtype: str
        """
        return self._name

    @property
    def assistant_config(self) -> AssistantConfig:
        """
        The chat assistant configuration.

        :return: The assistant configuration.
        :rtype: AssistantConfig
        """
        return self._assistant_config