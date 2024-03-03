# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
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
import json, time, importlib, sys, os, uuid
import copy


class ChatAssistantClient:
    """
    A class that manages an chat assistant client.

    :param config_json: The configuration data to use to create the chat client.
    :type config_json: str
    :param is_create: A flag to indicate if the assistant client is being created.
    :type is_create: bool
    :param timeout: The HTTP request timeout in seconds.
    :type timeout: Optional[float]
    """
    def __init__(
            self, 
            config_json: str,
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
            self._functions = {}
            self._user_input_processing_cancel_requested = False
            self._tools = []
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
        timeout: Optional[float] = None
    ) -> "ChatAssistantClient":
        """
        Creates a new chat assistant client from the given configuration data.

        :param config_json: The configuration data to use to create the chat client.
        :type config_json: str
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: The new chat assistant client.
        :rtype: ChatAssistantClient
        """
        try:
            # check if config_json contains assistant_id which is not null or empty, if so, set is_create to False
            config_data = json.loads(config_json)
            if "assistant_id" in config_data and config_data["assistant_id"]:
                return ChatAssistantClient(config_json=config_json, is_create=False, timeout=timeout)
            else:
                return ChatAssistantClient(config_json=config_json, is_create=True, timeout=timeout)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            raise InvalidJSONError(f"Invalid JSON format: {e}")

    @classmethod
    def from_config(
        cls, 
        config: AssistantConfig, 
        timeout: Optional[float] = None
    ) -> "ChatAssistantClient":
        """
        Creates a new chat assistant client from the given configuration.

        :param config: The configuration to use to create the assistant client.
        :type config: AssistantConfig
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: The new chat assistant client.
        :rtype: ChatAssistantClient
        """
        try:
            # check if config contains assistant_id which is not null or empty, if so, set is_create to False
            if config.assistant_id:
                return ChatAssistantClient(config.to_json(), is_create=False, timeout=timeout)
            else:
                return ChatAssistantClient(config.to_json(), is_create=True, timeout=timeout)
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
        self._tools = []

    def process_messages(
            self, 
            thread_name : str,
            additional_instructions : Optional[str] = None,
            timeout : Optional[float] = None
    ) -> None:
        """
        Process the messages in given thread.

        :param thread_name: The name of the thread to process.
        :type thread_name: str
        :param additional_instructions: Additional instructions to provide to the assistant.
        :type additional_instructions: Optional[str]
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        assistant_config_manager = AssistantConfigManager.get_instance()
        assistant_config = assistant_config_manager.get_config(self._name)
        assistant_id = assistant_config.assistant_id
        conversation_thread_client = ConversationThreadClient.get_instance(self._ai_client_type)
        threads_config : ConversationThreadConfig = conversation_thread_client.get_config()
        thread_id = threads_config.get_thread_id_by_name(thread_name)

        try:
            logger.info(f"Process messages for chat assistant: {assistant_id} and thread: {thread_id}")

            # call the start_run callback
            run_start_time = str(datetime.now())
            run_id = str(uuid.uuid4())
            self._callbacks.on_run_start(self._name, run_id, run_start_time, "Processing user input")

            conversation = conversation_thread_client.retrieve_conversation(thread_name)
            for message in conversation.text_messages:
                if message.role == "user":
                    self._messages.append({"role": "user", "content": message.content})
                if message.role == "assistant":
                    self._messages.append({"role": "assistant", "content": message.content})

            response = self._ai_client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=self._messages,
                tools=self._tools,
                tool_choice="auto"
            )

            response_message = response.choices[0].message

            # extend conversation with assistant's reply
            conversation_thread_client.create_conversation_thread_message(
                response_message.content,
                thread_name,
                metadata={"chat_assistant": self._name}
            )

            """
            tool_calls = response_message.tool_calls
            if tool_calls != None:
                for tool_call in tool_calls:
                    function_response = self._handle_function_call(tool_call)
                    self._messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": function_response,
                        }
                    )
            """

        except Exception as e:
            logger.error(f"Error occurred during processing run: {e}")
            raise EngineError(f"Error occurred during processing run: {e}")

    def cancel_processing(self) -> None:
        """
        Cancels the processing of the user input.

        :return: None
        :rtype: None
        """
        logger.info("User processing run cancellation requested.")
        self._user_input_processing_cancel_requested = True

    def _handle_required_action(self, name, thread_id, run_id, tool_calls, timeout : Optional[float] = None) -> bool:
        if tool_calls is None:
            logger.error("Processing run requires tool call action but no tool calls provided.")
            self._ai_client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id, timeout=timeout)
            return False

        tool_outputs = self._process_tool_calls(name, run_id, tool_calls)
        if not tool_outputs:
            return False

        self._ai_client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=tool_outputs,
            timeout=timeout
        )
        return True

    def _process_tool_calls(self, name, run_id, tool_calls):
        tool_outputs = []
        for tool_call in tool_calls:
            start_time = time.time()
            function_response = self._handle_function_call(tool_call)
            end_time = time.time()
            logger.debug(f"Total time taken for function {tool_call.function.name} : {end_time - start_time} seconds")
            logger.info(f"Function response: {function_response}")
            # call the on_function_call_processed callback
            self._callbacks.on_function_call_processed(name, run_id, tool_call.function.name, tool_call.function.arguments, str(function_response))
            tool_output = {
                "tool_call_id": tool_call.id,
                "output": function_response,
            }
            tool_outputs.append(tool_output)

        return tool_outputs

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

    def _handle_function_call(self, tool_call):
        logger.info(f"Handling function call: {tool_call.function.name} with arguments: {tool_call.function.arguments}")

        function_name = tool_call.function.name
        function_to_call = self._functions.get(function_name)
        if function_to_call:
            try:
                function_args = json.loads(tool_call.function.arguments)
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
            modified_functions = []
            for function in assistant_config.selected_functions:
                # Create a copy of the function spec to avoid modifying the original
                modified_function = copy.deepcopy(function)
                # Remove the module field from the function spec
                if "function" in modified_function and "module" in modified_function["function"]:
                    del modified_function["function"]["module"]
                modified_functions.append(modified_function)
            self._tools.extend(modified_functions)

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