# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.ai_client_factory import AIClientType
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.assistant_config import VectorStoreConfig
from azure.ai.assistant.management.assistant_config import ToolResourcesConfig
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.base_assistant_client import BaseAssistantClient
from azure.ai.assistant.management.conversation_thread_config import ConversationThreadConfig
from azure.ai.assistant.management.exceptions import EngineError, InvalidJSONError
from azure.ai.assistant.management.logger_module import logger

from typing import Optional
from datetime import datetime
import json, time, yaml, contextlib


class AssistantClient(BaseAssistantClient):
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
    :param timeout: The HTTP request timeout in seconds.
    :type timeout: Optional[float]
    :param client_args: Additional keyword arguments for configuring the AI client.
    :type client_args: Dict
    """
    def __init__(
            self, 
            config_json: str,
            callbacks: Optional[AssistantClientCallbacks] = None,
            is_create: bool = True,
            timeout: Optional[float] = None,
            **client_args
    ) -> None:
        super().__init__(config_json, callbacks, **client_args)
        self._init_assistant_client(self._config_data, is_create, timeout=timeout)

    @classmethod
    def from_json(
        cls,
        config_json: str,
        callbacks: Optional[AssistantClientCallbacks] = None,
        timeout: Optional[float] = None,
        **client_args
    ) -> "AssistantClient":
        """
        Creates an AssistantClient instance from JSON configuration data.

        :param config_json: JSON string containing the configuration for the assistant.
        :type config_json: str
        :param callbacks: Optional callbacks for the assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :param client_args: Additional keyword arguments for configuring the AI client.
        :type client_args: Dict

        :return: An instance of AssistantClient.
        :rtype: AssistantClient
        """
        try:
            config_data = json.loads(config_json)
            is_create = not ("assistant_id" in config_data and config_data["assistant_id"])
            return cls(config_json=config_json, callbacks=callbacks, is_create=is_create, timeout=timeout, **client_args)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            raise InvalidJSONError(f"Invalid JSON format: {e}")

    @classmethod
    def from_yaml(
        cls,
        config_yaml: str,
        callbacks: Optional[AssistantClientCallbacks] = None,
        timeout: Optional[float] = None,
        **client_args
    ) -> "AssistantClient":
        """
        Creates an AssistantClient instance from YAML configuration data.

        :param config_yaml: YAML string containing the configuration for the assistant.
        :type config_yaml: str
        :param callbacks: Optional callbacks for the assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :param client_args: Additional keyword arguments for configuring the AI client.
        :type client_args: Dict

        :return: An instance of AssistantClient.
        :rtype: AssistantClient
        """
        try:
            config_data = yaml.safe_load(config_yaml)
            config_json = json.dumps(config_data)
            return cls.from_json(config_json, callbacks, timeout, **client_args)
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML format: {e}")
            raise EngineError(f"Invalid YAML format: {e}")

    @classmethod
    def from_config(
        cls,
        config: AssistantConfig,
        callbacks: Optional[AssistantClientCallbacks] = None,
        timeout: Optional[float] = None,
        **client_args
    ) -> "AssistantClient":
        """
        Creates an AssistantClient instance from an AssistantConfig object.

        :param config: AssistantConfig object containing the configuration for the assistant.
        :type config: AssistantConfig
        :param callbacks: Optional callbacks for the assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :param client_args: Additional keyword arguments for configuring the AI client.
        :type client_args: Dict

        :return: An instance of AssistantClient.
        :rtype: AssistantClient
        """
        try:
            config_json = config.to_json()
            is_create = not config.assistant_id
            return cls(config_json=config_json, callbacks=callbacks, is_create=is_create, timeout=timeout, **client_args)
        except Exception as e:
            logger.error(f"Failed to create assistant client from config: {e}")
            raise EngineError(f"Failed to create assistant client from config: {e}")

    def sync_from_cloud(
            self,
            timeout: Optional[float] = None
    ) -> "AssistantClient":
        """
        Synchronizes the assistant client with the cloud service configuration.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: The assistant client with the given name.
        :rtype: AssistantClient
        """
        try:
            config_manager = AssistantConfigManager.get_instance()
            assistant_config = config_manager.get_config(self.name)
            if assistant_config is None:
                raise EngineError(f"Assistant with name: {self.name} does not exist.")

            # Retrieve the assistant from the cloud service and update the local configuration
            assistant = self._retrieve_assistant(assistant_config.assistant_id, timeout)
            assistant_config.instructions = assistant.instructions
            # TODO text_completion_config parameters are currently used in runs only, not assistant creation
            #assistant_config.text_completion_config.response_format  = assistant.response_format.type
            #assistant_config.text_completion_config.temperature = assistant.temperature
            #assistant_config.text_completion_config.top_p = assistant.top_p
            assistant_config.model = assistant.model

            # TODO currently files are not synced from cloud to local
            code_interpreter_file_ids_cloud = []
            if assistant.tool_resources and assistant.tool_resources.code_interpreter:
                code_interpreter_file_ids_cloud = assistant.tool_resources.code_interpreter.file_ids

            if assistant_config.tool_resources and assistant_config.tool_resources.code_interpreter_files:
                logger.info(f"Code interpreter files in local: {assistant_config.tool_resources.code_interpreter_files}")
                for file_id in code_interpreter_file_ids_cloud:
                    file_name = self._ai_client.files.retrieve(file_id).filename
                    logger.info(f"Code interpreter file id: {file_id}, name: {file_name} in cloud")

            file_search_vs_ids_cloud = []
            if assistant.tool_resources and assistant.tool_resources.file_search:
                file_search_vs_ids_cloud = assistant.tool_resources.file_search.vector_store_ids
                files_in_vs_cloud = list(self._ai_client.beta.vector_stores.files.list(file_search_vs_ids_cloud[0], timeout=timeout))
                file_search_file_ids_cloud = [file.id for file in files_in_vs_cloud]

            if assistant_config.tool_resources and assistant_config.tool_resources.file_search_vector_stores:
                logger.info(f"File search vector stores in local: {assistant_config.tool_resources.file_search_vector_stores}")
                for file_id in file_search_file_ids_cloud:
                    file_name = self._ai_client.files.retrieve(file_id).filename
                    logger.info(f"File search file id: {file_id}, name: {file_name} in cloud")

            #assistant_config.tool_resources = ToolResourcesConfig(
            #    code_interpreter_files=code_interpreter_files,
            #    file_search_vector_stores=file_search_vector_stores
            #)

            assistant_config.functions = [
                tool.function.model_dump() for tool in assistant.tools if tool.type == "function"
            ]
            assistant_config.code_interpreter = any(tool.type == "code_interpreter" for tool in assistant.tools)
            assistant_config.file_search = any(tool.type == "file_search" for tool in assistant.tools)
            assistant_config.assistant_id = assistant.id
            config_manager.update_config(self.name, assistant_config.to_json())
            return self
        except Exception as e:
            logger.error(f"Error retrieving configuration for {self.name}: {e}")
            raise Exception(f"Error retrieving configuration for {self.name}: {e}")

    def _init_assistant_client(
            self, 
            config_data: dict,
            is_create: bool = True,
            timeout: Optional[float] = None
    ):
        try:
            # Create or update the assistant
            assistant_config = AssistantConfig.from_dict(config_data)
            if is_create:
                start_time = time.time()
                self._create_assistant(assistant_config, timeout=timeout)
                end_time = time.time()
                logger.debug(f"Total time taken for _create_assistant: {end_time - start_time} seconds")
            else:
                start_time = time.time()
                config_manager = AssistantConfigManager.get_instance()
                local_config = config_manager.get_config(self.name)
                # check if the local configuration is different from the given configuration
                if local_config and local_config != assistant_config:
                    logger.debug("Local config is different from the given configuration. Updating the assistant...")
                    self._update_assistant(assistant_config, timeout=timeout)
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
            assistant_config: AssistantConfig,
            timeout: Optional[float] = None
    ):
        try:
            logger.info(f"Creating new assistant with name: {assistant_config.name}")
            tools = self._update_tools(assistant_config)
            instructions = self._replace_file_references_with_content(assistant_config)
            tools_resources = self._create_tool_resources(assistant_config)

            assistant = self._ai_client.beta.assistants.create(
                name=assistant_config.name,
                instructions=instructions,
                tool_resources=tools_resources,
                tools=tools,
                model=assistant_config.model,
                timeout=timeout
            )
            # Update the assistant_id in the assistant_config
            assistant_config.assistant_id = assistant.id
            logger.info(f"Created new assistant with ID: {assistant.id}")
        except Exception as e:
            logger.error(f"Failed to create new assistant with name: {assistant_config.name}: {e}")
            raise EngineError(f"Failed to create new assistant with name: {assistant_config.name}: {e}")

    def _create_tool_resources(
            self,
            assistant_config: AssistantConfig,
            timeout : Optional[float] = None
    ) -> dict:

        logger.info(f"Creating tool resources for assistant: {assistant_config.name}")

        if not assistant_config.tool_resources:
            logger.info("No tool resources provided for assistant.")
            return None

        # Upload the code interpreter files
        code_interpreter_file_ids = []
        if assistant_config.tool_resources.code_interpreter_files:
            self._upload_files(assistant_config, assistant_config.tool_resources.code_interpreter_files, timeout=timeout)
            code_interpreter_file_ids = list(assistant_config.tool_resources.code_interpreter_files.values())

        # create the vector store for file search
        assistant_config_vs = None
        if assistant_config.tool_resources.file_search_vector_stores:
            assistant_config_vs = assistant_config.tool_resources.file_search_vector_stores[0]
            self._upload_files(assistant_config, assistant_config_vs.files, timeout=timeout)
            assistant_config_vs.id = self._create_vector_store_with_files(assistant_config, assistant_config_vs, timeout=timeout)

        # Create the tool resources dictionary
        tool_resources = {
            "code_interpreter": {
                "file_ids": code_interpreter_file_ids
            },
            "file_search": {
                "vector_store_ids": [assistant_config_vs.id] if assistant_config_vs else []
            }
        }
        logger.info(f"Created tool resources: {tool_resources}")
        return tool_resources

    def _create_vector_store_with_files(
            self,
            assistant_config: AssistantConfig,
            vector_store: VectorStoreConfig,
            timeout: Optional[float] = None
    ) -> str:
        try:
            client_vs = self._ai_client.beta.vector_stores.create(
                name=vector_store.name,
                file_ids = list(vector_store.files.values()),
                metadata=vector_store.metadata,
                expires_after=vector_store.expires_after,
                timeout=timeout
            )
            return client_vs.id
        except Exception as e:
            logger.error(f"Failed to create vector store for assistant: {assistant_config.name}: {e}")
            raise EngineError(f"Failed to create vector store for assistant: {assistant_config.name}: {e}")

    def _update_tool_resources(
            self,
            assistant_config: AssistantConfig,
            timeout: Optional[float] = None
    ) -> dict:

        try:
            logger.info(f"Updating tool resources for assistant: {assistant_config.name}")

            if not assistant_config.tool_resources:
                logger.info("No tool resources provided for assistant.")
                return None

            assistant = self._retrieve_assistant(assistant_config.assistant_id, timeout=timeout)
            # code interpreter files
            existing_file_ids = set()
            if assistant.tool_resources.code_interpreter:
                existing_file_ids = set(assistant.tool_resources.code_interpreter.file_ids)
            if assistant_config.tool_resources.code_interpreter_files:
                self._delete_files(assistant_config, existing_file_ids, assistant_config.tool_resources.code_interpreter_files, timeout=timeout)
                self._upload_files(assistant_config, assistant_config.tool_resources.code_interpreter_files, timeout=timeout)

            # file search files in cloud
            existing_vs_ids = []
            existing_file_ids = set()
            if assistant.tool_resources.file_search:
                existing_vs_ids = assistant.tool_resources.file_search.vector_store_ids
                if existing_vs_ids:
                    all_files_in_vs = list(self._ai_client.beta.vector_stores.files.list(existing_vs_ids[0], timeout=timeout))
                    existing_file_ids = set([file.id for file in all_files_in_vs])

            # if there are new files to upload or delete, recreate the vector store
            assistant_config_vs = None
            if assistant_config.tool_resources.file_search_vector_stores:
                assistant_config_vs = assistant_config.tool_resources.file_search_vector_stores[0]
                if not existing_vs_ids and assistant_config_vs.id is None:
                    self._upload_files(assistant_config, assistant_config_vs.files, timeout=timeout)
                    assistant_config_vs.id = self._create_vector_store_with_files(assistant_config, assistant_config_vs, timeout=timeout)
                elif set(assistant_config_vs.files.values()) != existing_file_ids:
                    if existing_vs_ids:
                        self._delete_files_from_vector_store(assistant_config, existing_vs_ids[0], existing_file_ids, assistant_config_vs.files, timeout=timeout)
                        self._upload_files_to_vector_store(assistant_config, existing_vs_ids[0], assistant_config_vs.files, timeout=timeout)

            # Create the tool resources dictionary
            tool_resources = {
                "code_interpreter": {
                    "file_ids": list(assistant_config.tool_resources.code_interpreter_files.values()) if assistant_config.tool_resources.code_interpreter_files else []
                },
                "file_search": {
                    "vector_store_ids": [assistant_config_vs.id] if assistant_config_vs and assistant_config_vs.id is not None else []
                }
            }
            logger.info(f"Updated tool resources: {tool_resources}")
            return tool_resources

        except Exception as e:
            logger.error(f"Failed to update tool resources for assistant: {assistant_config.name}: {e}")
            raise EngineError(f"Failed to update tool resources for assistant: {assistant_config.name}: {e}")

    def purge(
            self,
            timeout: Optional[float] = None
    )-> None:
        """
        Purges the assistant from the cloud service and the local configuration.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        try:
            logger.info(f"Purging assistant with name: {self.name}")
            # retrieve the assistant configuration
            config_manager = AssistantConfigManager.get_instance()
            assistant_config = config_manager.get_config(self.name)

            # remove from the cloud service
            self._delete_assistant(assistant_config, timeout=timeout)

            # remove from the local config
            config_manager.delete_config(assistant_config.name)

            self._clear_variables()

        except Exception as e:
            logger.error(f"Failed to purge assistant with name: {self.name}: {e}")
            raise EngineError(f"Failed to purge assistant with name: {self.name}: {e}")

    def _delete_assistant(
            self, 
            assistant_config : AssistantConfig,
            timeout : Optional[float] = None
    ):
        try:
            assistant_id = assistant_config.assistant_id
            self._ai_client.beta.assistants.delete(
                assistant_id=assistant_id,
                timeout=timeout
            )
            # delete threads associated with the assistant
            logger.info(f"Deleted assistant with ID: {assistant_id}")
        except Exception as e:
            logger.error(f"Failed to delete assistant with ID: {assistant_id}: {e}")
            raise EngineError(f"Failed to delete assistant with ID: {assistant_id}: {e}")

    def process_messages(
            self, 
            thread_name: str,
            additional_instructions: Optional[str] = None,
            timeout: Optional[float] = None,
            stream: Optional[bool] = False
    ) -> None:
        """
        Process the messages in given thread, either in streaming or non-streaming mode.

        :param thread_name: The name of the thread to process.
        :param additional_instructions: Additional instructions to provide to the assistant.
        :param timeout: The HTTP request timeout in seconds.
        :param stream: Flag to indicate if the messages should be processed in streaming mode.
        """
        threads_config : ConversationThreadConfig = self._conversation_thread_client.get_config()
        thread_id = threads_config.get_thread_id_by_name(thread_name)

        try:
            if stream:
                self._process_messages_streaming(thread_name, thread_id, additional_instructions, timeout)
            else:
                self._process_messages_non_streaming(thread_name, thread_id, additional_instructions, timeout)
        except Exception as e:
            logger.error(f"Error occurred during processing messages: {e}")
            raise EngineError(f"Error occurred during processing messages: {e}")

    def _process_messages_non_streaming(
            self,
            thread_name: str,
            thread_id: str,
            additional_instructions: Optional[str] = None,
            timeout: Optional[float] = None
    ) -> None:
        """
        Process the messages in a given thread without streaming.

        :param thread_name: The name of the thread to process.
        :param thread_id: The ID of the thread to process.
        :param additional_instructions: Additional instructions to provide to the assistant.
        :param timeout: The HTTP request timeout in seconds.
        """
        try:
            text_completion_config = self._assistant_config.text_completion_config

            logger.info(f"Creating a run for assistant: {self.assistant_config.assistant_id} and thread: {thread_id}")
            # Azure OpenAI does not support all completion parameters currently
            if text_completion_config == None:
                run = self._ai_client.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=self.assistant_config.assistant_id,
                    additional_instructions=additional_instructions,
                    timeout=timeout
                )
            else:
                run = self._ai_client.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=self.assistant_config.assistant_id,
                    additional_instructions=additional_instructions,
                    temperature=None if text_completion_config is None else text_completion_config.temperature,
                    max_completion_tokens=None if text_completion_config is None else text_completion_config.max_completion_tokens,
                    max_prompt_tokens=None if text_completion_config is None else text_completion_config.max_prompt_tokens,
                    top_p=None if text_completion_config is None else text_completion_config.top_p,
                    response_format=None if text_completion_config is None else {'type': text_completion_config.response_format},
                    truncation_strategy=None if text_completion_config is None else text_completion_config.truncation_strategy,
                    timeout=timeout
                )

            # call the start_run callback
            run_start_time = str(datetime.now())
            user_request = self._conversation_thread_client.retrieve_conversation(thread_name).get_last_text_message("user").content
            self._callbacks.on_run_start(self._name, run.id, run_start_time, user_request)
            if self._cancel_run_requested.is_set():
                self._cancel_run_requested.clear()
            is_first_message = True

            while True:
                time.sleep(0.5)

                logger.debug(f"Retrieving run: {run.id} with status: {run.status}")
                run = self._ai_client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id,
                    timeout=timeout
                )

                if run is None:
                    logger.error("Retrieved run is None, exiting the loop.")
                    return None

                logger.info(f"Processing run: {run.id} with status: {run.status}")

                if self._cancel_run_requested.is_set():
                    self._ai_client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id, timeout=timeout)
                    self._cancel_run_requested.clear()
                    logger.info("Processing run cancelled by user, exiting the loop.")
                    return None

                self._callbacks.on_run_update(self._name, run.id, run.status, thread_name, is_first_message)
                is_first_message = False

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
            logger.error(f"Error occurred during non-streaming processing run: {e}")
            raise EngineError(f"Error occurred during non-streaming processing run: {e}")

    def _process_messages_streaming(
            self, 
            thread_name: str,
            thread_id: str,
            additional_instructions: Optional[str] = None,
            timeout: Optional[float] = None
    ) -> None:
        """
        Process the messages in a given thread with streaming.

        :param thread_name: The name of the thread to process.
        :param thread_id: The ID of the thread to process.
        :param additional_instructions: Additional instructions to provide to the assistant.
        :param timeout: The HTTP request timeout in seconds.
        """
        from azure.ai.assistant.management.stream_event_handler import StreamEventHandler
        try:
            logger.info(f"Creating and streaming a run for assistant: {self._assistant_config.assistant_id} and thread: {thread_id}")

            text_completion_config = self._assistant_config.text_completion_config

            if text_completion_config is None:
                with self._ai_client.beta.threads.runs.stream(
                    thread_id=thread_id,
                    assistant_id=self._assistant_config.assistant_id,
                    additional_instructions=additional_instructions,
                    timeout=timeout,
                    event_handler=StreamEventHandler(self, thread_id, timeout=timeout)
                ) as stream:
                    stream.until_done()
            else:
                with self._ai_client.beta.threads.runs.stream(
                    thread_id=thread_id,
                    assistant_id=self._assistant_config.assistant_id,
                    additional_instructions=additional_instructions,
                    temperature=None if text_completion_config is None else text_completion_config.temperature,
                    max_completion_tokens=None if text_completion_config is None else text_completion_config.max_completion_tokens,
                    max_prompt_tokens=None if text_completion_config is None else text_completion_config.max_prompt_tokens,
                    top_p=None if text_completion_config is None else text_completion_config.top_p,
                    response_format=None if text_completion_config is None else {'type': text_completion_config.response_format},
                    truncation_strategy=None if text_completion_config is None else text_completion_config.truncation_strategy,
                    event_handler=StreamEventHandler(self, thread_id, timeout=timeout),
                    timeout=timeout
                ) as stream:
                    stream.until_done()

        except Exception as e:
            logger.error(f"Error occurred during streaming processing run: {e}")
            raise EngineError(f"Error occurred during streaming processing run: {e}")

    def _handle_required_action(self, name, thread_id, run_id, tool_calls, timeout : Optional[float] = None, stream : Optional[bool] = None) -> bool:
        from azure.ai.assistant.management.stream_event_handler import StreamEventHandler
        logger.info("Handling required action")
        if tool_calls is None:
            logger.error("Processing run requires tool call action but no tool calls provided.")
            self._ai_client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id, timeout=timeout)
            return False

        tool_outputs = self._process_tool_calls(name, run_id, tool_calls)
        if not tool_outputs:
            return False

        if stream:
            logger.info("Submitting tool outputs with stream")
            with self._ai_client.beta.threads.runs.submit_tool_outputs_stream(
                thread_id=thread_id,
                run_id=run_id,
                tool_outputs=tool_outputs,
                timeout=timeout,
                event_handler=StreamEventHandler(self, thread_id, is_submit_tool_call=True)
            ) as stream:
                stream.until_done()
        else:
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
            function_response = str(self._handle_function_call(tool_call.function.name, tool_call.function.arguments))
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

    def _retrieve_assistant(
            self, 
            assistant_id : str,
            timeout : Optional[float] = None
    ):
        try:
            logger.info(f"Retrieving assistant with ID: {assistant_id}")
            assistant = self._ai_client.beta.assistants.retrieve(
                assistant_id=assistant_id,
                timeout=timeout
            )
            return assistant
        except Exception as e:
            logger.error(f"Failed to retrieve assistant with ID: {assistant_id}: {e}")
            raise EngineError(f"Failed to retrieve assistant with ID: {assistant_id}: {e}")

    def _delete_files_from_vector_store(
            self,
            assistant_config : AssistantConfig,
            vector_store_id: str,
            existing_file_ids: set,
            updated_files: Optional[dict] = None,
            delete_from_service: Optional[bool] = True,
            timeout : Optional[float] = None
    ):
        updated_file_ids = set(updated_files.values())
        file_ids_to_delete = existing_file_ids - updated_file_ids
        logger.info(f"Deleting files: {file_ids_to_delete} from assistant: {assistant_config.name} vector store: {vector_store_id}")
        for file_id in file_ids_to_delete:
            file_deletion_status = self._ai_client.beta.vector_stores.files.delete(
                vector_store_id=vector_store_id,
                file_id=file_id,
                timeout=timeout
            )
            if delete_from_service:
                file_deletion_status = self._ai_client.files.delete(
                    file_id=file_id,
                    timeout=timeout
                )

    def _upload_files_to_vector_store(
            self,
            assistant_config: AssistantConfig,
            vector_store_id: str,
            updated_files: Optional[dict] = None,
            timeout : Optional[float] = None
    ):
        logger.info(f"Uploading files to assistant {assistant_config.name} vector store: {vector_store_id}")
        for file_path, file_id in updated_files.items():
            if file_id is None:
                logger.info(f"Uploading file: {file_path} for assistant: {assistant_config.name}")
                file = self._ai_client.beta.vector_stores.files.upload_and_poll(
                    vector_store_id=vector_store_id,
                    file=open(file_path, "rb")
                )
                updated_files[file_path] = file.id

    def _delete_files(
            self,
            assistant_config : AssistantConfig,
            existing_file_ids : set,
            updated_files: Optional[dict] = None,
            timeout : Optional[float] = None
    ):
        updated_file_ids = set(updated_files.values())
        file_ids_to_delete = existing_file_ids - updated_file_ids
        logger.info(f"Deleting files: {file_ids_to_delete} for assistant: {assistant_config.name}")
        for file_id in file_ids_to_delete:
            file_deletion_status = self._ai_client.files.delete(
                file_id=file_id,
                timeout=timeout
            )
    
    def _upload_files(
            self, 
            assistant_config: AssistantConfig,
            updated_files: Optional[dict] = None,
            timeout : Optional[float] = None
    ):
        logger.info(f"Uploading files for assistant: {assistant_config.name}")
        for file_path, file_id in updated_files.items():
            if file_id is None:
                logger.info(f"Uploading file: {file_path} for assistant: {assistant_config.name}")
                file = self._ai_client.files.create(
                    file=open(file_path, "rb"),
                    purpose='assistants',
                    timeout=timeout
                )
                updated_files[file_path] = file.id

    def _update_assistant(
            self, 
            assistant_config: AssistantConfig,
            timeout : Optional[float] = None
    ):
        try:
            logger.info(f"Updating assistant with ID: {assistant_config.assistant_id}")
            tools = self._update_tools(assistant_config)
            instructions = self._replace_file_references_with_content(assistant_config)
            tools_resources = self._update_tool_resources(assistant_config)

            # TODO update the assistant with the new configuration only if there are changes
            self._ai_client.beta.assistants.update(
                assistant_id=assistant_config.assistant_id,
                name=assistant_config.name,
                instructions=instructions,
                tool_resources=tools_resources,
                tools=tools,
                model=assistant_config.model,
                timeout=timeout
            )
        except Exception as e:
            logger.error(f"Failed to update assistant with ID: {assistant_config.assistant_id}: {e}")
            raise EngineError(f"Failed to update assistant with ID: {assistant_config.assistant_id}: {e}")