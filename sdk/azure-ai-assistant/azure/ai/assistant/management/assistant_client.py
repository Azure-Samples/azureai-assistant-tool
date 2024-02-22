# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
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
import json, time, importlib, sys, os


class AssistantClient:
    """
    A class that manages an assistant client.

    The assistant client is used to create, retrieve, update, and delete assistants in the cloud service 
    using the given AI client type and json configuration data.

    :param config_json: The configuration data to use to create the assistant client.
    :type config_json: str
    :param callbacks: The callbacks to use for the assistant client.
    :type callbacks: Optional[AssistantClientCallbacks]
    :param is_create: A flag to indicate if the assistant client is being created.
    :type is_create: bool
    """
    def __init__(
            self, 
            config_json: str,
            callbacks: Optional[AssistantClientCallbacks] = None,
            is_create: bool = True
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

            # Initialize the assistant client (create or update)
            self._init_assistant_client(config_data, is_create)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            raise InvalidJSONError(f"Invalid JSON format: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize assistant client: {e}")
            raise EngineError(f"Failed to initialize assistant client: {e}")

    @classmethod
    def from_json(
        cls, 
        config_json : str,
        callbacks: Optional[AssistantClientCallbacks] = None,
    ) -> "AssistantClient":
        """
        Creates a new assistant client from the given configuration data.

        New assistant client is created in the service and assistant configuration is saved with the given json data.

        :param config_json: The configuration data to use to create the assistant client.
        :type config_json: str
        :param callbacks: The callbacks to use for the assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]

        :return: The new assistant client.
        :rtype: AssistantClient
        """
        try:
            # check if config_json contains assistant_id which is not null or empty, if so, set is_create to False
            config_data = json.loads(config_json)
            if "assistant_id" in config_data and config_data["assistant_id"]:
                return AssistantClient(config_json=config_json, callbacks=callbacks, is_create=False)
            else:
                return AssistantClient(config_json=config_json, callbacks=callbacks, is_create=True)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            raise InvalidJSONError(f"Invalid JSON format: {e}")

    @classmethod
    def from_config(
        cls, 
        config: AssistantConfig, 
        callbacks: Optional[AssistantClientCallbacks] = None
    ) -> "AssistantClient":
        """
        Creates a new assistant client from the given configuration.

        New assistant client is created in the service and assistant configuration is saved with the given configuration.

        :param config: The configuration to use to create the assistant client.
        :type config: AssistantConfig
        :param callbacks: The callbacks to use for the assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]

        :return: The new assistant client.
        :rtype: AssistantClient
        """
        try:
            # check if config contains assistant_id which is not null or empty, if so, set is_create to False
            if config.assistant_id:
                return AssistantClient(config.to_json(), callbacks, is_create=False)
            else:
                return AssistantClient(config.to_json(), callbacks, is_create=True)
        except Exception as e:
            logger.error(f"Failed to create assistant client from config: {e}")
            raise EngineError(f"Failed to create assistant client from config: {e}")

    def sync_from_cloud(self) -> "AssistantClient":
        """
        Synchronizes the assistant client with the cloud service configuration.

        :return: The assistant client with the given name.
        :rtype: AssistantClient
        """
        try:
            # If not registered, retrieve data from cloud and register it to AssistantConfig using AssistantConfigManager
            #TODO fill the config data from the cloud service by default
            config_manager = AssistantConfigManager.get_instance()
            assistant_config = config_manager.get_config(self.name)
            if assistant_config is None:
                raise EngineError(f"Assistant with name: {self.name} does not exist.")

            # Retrieve the assistant from the cloud service and update the local configuration
            assistant = self._retrieve_assistant(assistant_config.assistant_id)
            assistant_config.instructions = assistant.instructions
            assistant_config.model = assistant.model
            assistant_config.knowledge_files = {file_path: file_id for file_path, file_id in zip(assistant_config.knowledge_files.keys(), assistant.file_ids)}
            assistant_config.selected_functions = [
                tool.function.model_dump() for tool in assistant.tools if tool.type == "function"
            ]
            assistant_config.code_interpreter = any(tool.type == "code_interpreter" for tool in assistant.tools)
            assistant_config.knowledge_retrieval = any(tool.type == "retrieval" for tool in assistant.tools)
            assistant_config.assistant_id = assistant.id
            config_manager.update_config(self.name, assistant_config.to_json())
            return self
        except Exception as e:
            logger.error(f"Error retrieving configuration for {self.name}: {e}")
            raise Exception(f"Error retrieving configuration for {self.name}: {e}")

    def _init_assistant_client(
            self, 
            config_data: dict,
            is_create: bool = True
    ):
        try:
            # Create or update the assistant
            assistant_config = AssistantConfig.from_dict(config_data)
            if is_create:
                start_time = time.time()
                self._create_assistant(assistant_config)
                end_time = time.time()
                logger.debug(f"Total time taken for _create_assistant: {end_time - start_time} seconds")
            else:
                start_time = time.time()
                config_manager = AssistantConfigManager.get_instance()
                local_config = config_manager.get_config(self.name)
                # check if the local configuration is different from the given configuration
                if local_config and local_config != assistant_config:
                    logger.debug("Local config is different from the given configuration. Updating the assistant...")
                    self._update_assistant(assistant_config)
                else:
                    logger.debug("Local config is the same as the given configuration. No need to update the assistant.")
                end_time = time.time()
                logger.debug(f"Total time taken for _update_assistant: {end_time - start_time} seconds")

            start_time = time.time()
            self._load_selected_functions(assistant_config)
            end_time = time.time()
            logger.debug(f"Total time taken for _load_selected_functions: {end_time - start_time} seconds")
            self._assistant_config = assistant_config

            # Update the local configuration using AssistantConfigManager
            # TODO make optional to save the assistant_config in the config manager
            config_manager = AssistantConfigManager.get_instance()
            config_manager.update_config(self._name, assistant_config.to_json())

        except Exception as e:
            logger.error(f"Failed to initialize assistant instance: {e}")
            raise EngineError(f"Failed to initialize assistant instance: {e}")

    def _create_assistant(
            self, 
            assistant_config: AssistantConfig
    ):
        try:
            logger.info(f"Creating new assistant with name: {assistant_config.name}")
            # Upload the files for new assistant
            self._upload_new_files(assistant_config)
            file_ids = list(assistant_config.knowledge_files.values())
            tools = self._update_tools(assistant_config)

            assistant = self._ai_client.beta.assistants.create(
                name=assistant_config.name,
                instructions=assistant_config.instructions,
                tools=tools,
                model=assistant_config.model,
                file_ids=file_ids
            )
            # Update the assistant_id in the assistant_config
            assistant_config.assistant_id = assistant.id
            logger.info(f"Created new assistant with ID: {assistant.id}")
        except Exception as e:
            logger.error(f"Failed to create new assistant with name: {assistant_config.name}: {e}")
            raise EngineError(f"Failed to create new assistant with name: {assistant_config.name}: {e}")

    def purge(self)-> None:
        """
        Purges the assistant from the cloud service and the local configuration.

        :return: None
        :rtype: None
        """
        try:
            logger.info(f"Purging assistant with name: {self.name}")
            # retrieve the assistant configuration
            config_manager = AssistantConfigManager.get_instance()
            assistant_config = config_manager.get_config(self.name)

            # remove from the cloud service
            self._delete_assistant(assistant_config)

            # remove from the local config
            config_manager.delete_config(assistant_config.name)

            self._clear_variables()

        except Exception as e:
            logger.error(f"Failed to purge assistant with name: {self.name}: {e}")
            raise EngineError(f"Failed to purge assistant with name: {self.name}: {e}")

    def _clear_variables(self):
        # clear the local variables
        self._assistant_config = None
        self._functions = {}
        self._ai_client = None
        self._callbacks = None
        self._user_input_processing_cancel_requested = False
        self._ai_client_type = None
        self._name = None

    def _delete_assistant(
            self, 
            assistant_config : AssistantConfig
    ):
        try:
            assistant_id = assistant_config.assistant_id
            self._ai_client.beta.assistants.delete(
                assistant_id=assistant_id
            )
            # delete threads associated with the assistant
            logger.info(f"Deleted assistant with ID: {assistant_id}")
        except Exception as e:
            logger.error(f"Failed to delete assistant with ID: {assistant_id}: {e}")
            raise EngineError(f"Failed to delete assistant with ID: {assistant_id}: {e}")

    def _update_files(
            self,
            assistant_config: AssistantConfig,
    ) -> None:

        try:
            logger.info(f"Updating files for assistant: {assistant_config.name}")
            assistant = self._retrieve_assistant(assistant_config.assistant_id)
            existing_file_ids = set(assistant.file_ids)
            self._delete_old_files(assistant_config, existing_file_ids)
            self._upload_new_files(assistant_config)

        except Exception as e:
            logger.error(f"Failed to update files for assistant: {assistant_config.name}: {e}")
            raise EngineError(f"Failed to update files for assistant: {assistant_config.name}: {e}")

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
        :param timeout: The timeout in seconds to wait for the processing to complete.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        assistant_config_manager = AssistantConfigManager.get_instance()
        assistant_config = assistant_config_manager.get_config(self._name)
        assistant_id = assistant_config.assistant_id
        # TODO retrieve thread_id from ConversationThreadClient which then retrieve from cloud service
        threads_config : ConversationThreadConfig = ConversationThreadClient.get_instance(self._ai_client_type).get_config()
        thread_id = threads_config.get_thread_id_by_name(thread_name)

        try:

            logger.info(f"Creating a run for assistant: {assistant_id} and thread: {thread_id}")
            # Azure OpenAI does not currently support additional_instructions
            if additional_instructions is None:
                run = self._ai_client.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=assistant_id,
                    timeout=timeout
                )
            else:
                run = self._ai_client.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=assistant_id,
                    additional_instructions=additional_instructions,
                    timeout=timeout
                )

            # call the start_run callback
            run_start_time = str(datetime.now())
            self._callbacks.on_run_start(self._name, run.id, run_start_time, "Processing user input")

            while True:
                time.sleep(0.5)

                logger.info(f"Retrieving run: {run.id} with status: {run.status}")
                run = self._ai_client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id,
                    timeout=timeout
                )

                if run is None:
                    logger.error("Retrieved run is None, exiting the loop.")
                    return None

                logger.info(f"Processing run: {run.id} with status: {run.status}")

                if self._user_input_processing_cancel_requested:
                    self._ai_client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id, timeout=timeout)
                    self._user_input_processing_cancel_requested = False
                    logger.info("Processing run cancelled by user, exiting the loop.")
                    return None

                self._callbacks.on_run_update(self._name, run.id, run.status, thread_name)

                if run.status == "completed":
                    logger.info("Processing run status: completed")
                    run_end_time = str(datetime.now())
                    self._callbacks.on_run_end(self._name, run.id, run_end_time, thread_name)
                    return None
                elif run.status == "failed":
                    logger.warning(f"Processing run status: failed, error code: {run.last_error.code}, error message: {run.last_error.message}")
                    run_end_time = str(datetime.now())
                    self._callbacks.on_run_failed(self._name, run.id, run_end_time, run.last_error.code, run.last_error.message, thread_name)
                    return None
                elif run.status == "cancelled" or run.status == "expired":
                    logger.info("Processing run status: cancelled")
                    run_end_time = str(datetime.now())
                    self._callbacks.on_run_cancelled(self._name, run.id, run_end_time, thread_name)
                    return None
                if run.status == "requires_action":
                    tool_calls = run.required_action.submit_tool_outputs.tool_calls
                    if not self._handle_required_action(self._name, thread_id, run.id, tool_calls):
                        return None

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
            self._ai_client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
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

    def _retrieve_assistant(
            self, 
            assistant_id : str
    ):
        try:
            logger.info(f"Retrieving assistant with ID: {assistant_id}")
            assistant = self._ai_client.beta.assistants.retrieve(
                assistant_id=assistant_id
            )
            return assistant
        except Exception as e:
            logger.error(f"Failed to retrieve assistant with ID: {assistant_id}: {e}")
            raise EngineError(f"Failed to retrieve assistant with ID: {assistant_id}: {e}")

    def _delete_old_files(
            self,
            assistant_config : AssistantConfig,
            existing_file_ids
    ):
        updated_file_ids = set(assistant_config.knowledge_files.values())
        file_ids_to_delete = existing_file_ids - updated_file_ids
        logger.info(f"Deleting files: {file_ids_to_delete} for assistant: {assistant_config.name}")
        for file_id in file_ids_to_delete:
            file_deletion_status = self._ai_client.beta.assistants.files.delete(
                assistant_id=assistant_config.assistant_id,
                file_id=file_id
            )

    def _upload_new_files(
            self, 
            assistant_config: AssistantConfig
    ):
        logger.info(f"Uploading new files for assistant: {assistant_config.name}")
        for file_path, file_id in assistant_config.knowledge_files.items():
            if file_id is None:
                logger.info(f"Uploading file: {file_path} for assistant: {assistant_config.name}")
                file = self._ai_client.files.create(
                    file=open(file_path, "rb"),
                    purpose='assistants'
                )
                assistant_config.knowledge_files[file_path] = file.id

    def _update_assistant(
            self, 
            assistant_config: AssistantConfig
    ):
        try:
            logger.info(f"Updating assistant with ID: {assistant_config.assistant_id}")
            self._update_files(assistant_config)
            file_ids = list(assistant_config.knowledge_files.values())
            tools = self._update_tools(assistant_config)

            # TODO update the assistant with the new configuration only if there are changes
            self._ai_client.beta.assistants.update(
                assistant_id=assistant_config.assistant_id,
                name=assistant_config.name,
                instructions=assistant_config.instructions,
                tools=tools,
                model=assistant_config.model,
                file_ids=file_ids
            )
        except Exception as e:
            logger.error(f"Failed to update assistant with ID: {assistant_config.assistant_id}: {e}")
            raise EngineError(f"Failed to update assistant with ID: {assistant_config.assistant_id}: {e}")

    def _update_tools(
            self, 
            assistant_config: AssistantConfig
    ):
        tools = []
        logger.info(f"Updating tools for assistant: {assistant_config.name}")
        # Add the retrieval tool to the tools list if there are knowledge files
        if assistant_config.knowledge_retrieval:
            tools.append({"type": "retrieval"})
        # Add the functions to the tools list if there are functions
        if assistant_config.selected_functions:
            tools.extend(assistant_config.selected_functions)
        # Add the code interpreter to the tools list if there is a code interpreter
        if assistant_config.code_interpreter:
            tools.append({"type": "code_interpreter"})
        return tools

    @classmethod
    def get_assistant_list(
        cls,
        ai_client_type : AIClientType
    ) -> list:
        """
        Gets a list of all registered assistants.

        :param ai_client_type: The type of AI client to use to get the list of assistants.
        :type ai_client_type: AIClientType

        :return: A list of all registered assistants.
        :rtype: list
        """
        try:
            logger.info(f"Getting assistants list for AI client type: {ai_client_type}")
            ai_client = AIClientFactory.get_instance().get_client(ai_client_type)
            assistant_list = ai_client.beta.assistants.list()
            return assistant_list.data
        except Exception as e:
            logger.error(f"Failed to get assistants list: {e}")
            raise EngineError(f"Failed to get assistants list: {e}")

    @property
    def name(self) -> str:
        """
        The name of the assistant.

        :return: The name of the assistant.
        :rtype: str
        """
        return self._name

    @property
    def assistant_config(self) -> AssistantConfig:
        """
        The assistant configuration.

        AssistantClient update() method will update the assistant configuration in the cloud service
        and apply the changes locally.

        :return: The assistant configuration.
        :rtype: AssistantConfig
        """
        return self._assistant_config