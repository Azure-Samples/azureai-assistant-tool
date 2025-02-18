# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import json
import time
import yaml
import copy
from typing import Optional, List, Tuple
from datetime import datetime

from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.assistant_config import VectorStoreConfig
from azure.ai.assistant.management.assistant_config import ToolResourcesConfig
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.base_assistant_client import BaseAssistantClient
from azure.ai.assistant.management.conversation_thread_config import ConversationThreadConfig
from azure.ai.assistant.management.exceptions import EngineError, InvalidJSONError
from azure.ai.assistant.management.logger_module import logger
from azure.ai.projects.models import RequiredFunctionToolCall, SubmitToolOutputsAction, ThreadRun
from azure.ai.projects.models import CodeInterpreterTool, FileSearchTool, ToolSet, ToolResources, OpenApiTool, OpenApiAnonymousAuthDetails, AzureAISearchTool, BingGroundingTool, ConnectionType


class AgentClient(BaseAssistantClient):
    """
    A class that manages an agent client.

    The agent client is used to create, retrieve, update, and delete agents in the cloud service 
    using the given AI client type and JSON configuration data.

    :param config_json: The configuration data to use to create the agent client.
    :type config_json: str
    :param callbacks: The callbacks to use for the agent client.
    :type callbacks: Optional[AssistantClientCallbacks]
    :param is_create: A flag to indicate if the agent client is being created.
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
        self._init_agent_client(self._config_data, is_create, timeout=timeout)

    @classmethod
    def from_json(
        cls,
        config_json: str,
        callbacks: Optional[AssistantClientCallbacks] = None,
        timeout: Optional[float] = None,
        **client_args
    ) -> "AgentClient":
        """
        Creates an AgentClient instance from JSON configuration data.

        :param config_json: JSON string containing the configuration for the agent.
        :type config_json: str
        :param callbacks: Optional callbacks for the agent client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :param client_args: Additional keyword arguments for configuring the AI client.
        :type client_args: Dict

        :return: An instance of AgentClient.
        :rtype: AgentClient
        """
        try:
            config_data = json.loads(config_json)
            is_create = not ("assistant_id" in config_data and config_data["assistant_id"])
            return cls(
                config_json=config_json,
                callbacks=callbacks,
                is_create=is_create,
                timeout=timeout,
                **client_args
            )
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
    ) -> "AgentClient":
        """
        Creates an AgentClient instance from YAML configuration data.

        :param config_yaml: YAML string containing the configuration for the agent.
        :type config_yaml: str
        :param callbacks: Optional callbacks for the agent client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :param client_args: Additional keyword arguments for configuring the AI client.
        :type client_args: Dict

        :return: An instance of AgentClient.
        :rtype: AgentClient
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
    ) -> "AgentClient":
        """
        Creates an AgentClient instance from an AssistantConfig object.

        :param config: AssistantConfig object containing the configuration for the agent.
        :type config: AssistantConfig
        :param callbacks: Optional callbacks for the agent client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :param client_args: Additional keyword arguments for configuring the AI client.
        :type client_args: Dict

        :return: An instance of AgentClient.
        :rtype: AgentClient
        """
        try:
            config_json = config.to_json()
            is_create = not config.assistant_id
            return cls(
                config_json=config_json,
                callbacks=callbacks,
                is_create=is_create,
                timeout=timeout,
                **client_args
            )
        except Exception as e:
            logger.error(f"Failed to create agent client from config: {e}")
            raise EngineError(f"Failed to create agent client from config: {e}")

    def sync_from_cloud(
            self,
            timeout: Optional[float] = None
    ) -> "AgentClient":
        """
        Synchronizes the agent client with the cloud service configuration.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: The agent client with the given name.
        :rtype: AgentClient
        """
        try:
            config_manager = AssistantConfigManager.get_instance()
            assistant_config = config_manager.get_config(self.name)
            if assistant_config is None:
                raise EngineError(f"Agent with name: {self.name} does not exist.")

            # Retrieve the agent from the cloud service and update the local configuration
            assistant = self._retrieve_agent(assistant_config.assistant_id, timeout)
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
                    file_name = self._ai_client.agents.get_file(file_id).filename
                    logger.info(f"Code interpreter file id: {file_id}, name: {file_name} in cloud")

            file_search_vs_ids_cloud = []
            if assistant.tool_resources and assistant.tool_resources.file_search:
                file_search_vs_ids_cloud = assistant.tool_resources.file_search.vector_store_ids
                files_in_vs_cloud = list(self._ai_client.agents.list_vector_store_files(file_search_vs_ids_cloud[0]))
                file_search_file_ids_cloud = [file.id for file in files_in_vs_cloud]

            if assistant_config.tool_resources and assistant_config.tool_resources.file_search_vector_stores:
                logger.info(f"File search vector stores in local: {assistant_config.tool_resources.file_search_vector_stores}")
                for file_id in file_search_file_ids_cloud:
                    file_name = self._ai_client.agents.get_file(file_id).filename
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

    def _init_agent_client(
            self, 
            config_data: dict,
            is_create: bool = True,
            timeout: Optional[float] = None
    ):
        try:
            assistant_config = AssistantConfig.from_dict(config_data)

            if is_create:
                start_time = time.time()
                self._create_agent(assistant_config, timeout=timeout)
                end_time = time.time()
                logger.debug(f"Total time taken for _create_agent: {end_time - start_time} seconds")
            else:
                start_time = time.time()
                config_manager = AssistantConfigManager.get_instance()
                local_config = config_manager.get_config(self.name)
                if local_config and local_config != assistant_config:
                    logger.debug("Local config is different from the given configuration. Updating the agent...")
                    self._update_agent(assistant_config, timeout=timeout)
                else:
                    logger.debug("Local config is the same as the given configuration. No need to update the agent.")
                end_time = time.time()
                logger.debug(f"Total time taken for _update_agent: {end_time - start_time} seconds")

            # Load functions
            start_time = time.time()
            self._load_selected_functions(assistant_config)
            end_time = time.time()
            logger.debug(f"Total time taken for _load_selected_functions: {end_time - start_time} seconds")
            self._assistant_config = assistant_config

            # Update assistant config manager
            config_manager = AssistantConfigManager.get_instance()
            config_manager.update_config(self._name, assistant_config.to_json())

        except Exception as e:
            logger.error(f"Failed to initialize agent instance: {e}")
            raise EngineError(f"Failed to initialize agent instance: {e}")

    def _create_agent(
        self, 
        assistant_config: AssistantConfig,
        timeout: Optional[float] = None
    ):
        try:
            logger.info(f"Creating new agent with name: {assistant_config.name}")
            instructions = self._replace_file_references_with_content(assistant_config)
            tool_resources = self._create_tool_resources(assistant_config, timeout=timeout)
            tools, resources = self._build_tools_and_resources(assistant_config, tool_resources)

            assistant = self._ai_client.agents.create_agent(
                name=assistant_config.name,
                instructions=instructions,
                tools=tools,
                tool_resources=resources,
                model=assistant_config.model,
            )

            # Update the assistant_id in the assistant_config
            assistant_config.assistant_id = assistant.id
            logger.info(f"Created new assistant with ID: {assistant.id}")

        except Exception as e:
            logger.error(f"Failed to create new agent with name: {assistant_config.name}: {e}")
            raise EngineError(f"Failed to create new agent with name: {assistant_config.name}: {e}")

    def _create_tool_resources(
        self,
        assistant_config: AssistantConfig,
        timeout: Optional[float] = None
    ) -> Optional[dict]:
        logger.info(f"Creating tool resources for agent: {assistant_config.name}")

        # If no tool_resources in config, return None early
        if not assistant_config.tool_resources:
            logger.info("No tool resources provided for agent.")
            return None

        tool_resources = {}

        # If code_interpreter is enabled, set up its resource
        if assistant_config.code_interpreter:
            code_interpreter_file_ids = []
            local_files = assistant_config.tool_resources.code_interpreter_files
            if local_files:
                self._upload_files(assistant_config, local_files, timeout=timeout)
                code_interpreter_file_ids = list(local_files.values())
            tool_resources["code_interpreter"] = {
                "file_ids": code_interpreter_file_ids
            }

        # If file_search is enabled, set up its resource
        if assistant_config.file_search:
            file_search_vs = None
            if assistant_config.tool_resources.file_search_vector_stores:
                file_search_vs = assistant_config.tool_resources.file_search_vector_stores[0]
                self._upload_files(assistant_config, file_search_vs.files, timeout=timeout)
                file_search_vs.id = self._create_vector_store_with_files(assistant_config, file_search_vs, timeout=timeout)

            tool_resources["file_search"] = {
                "vector_store_ids": [file_search_vs.id] if file_search_vs else []
            }

        # If empty (meaning code_interpreter and file_search were both false), return None
        logger.info(f"Created tool resources: {tool_resources if tool_resources else None}")
        return tool_resources if tool_resources else None

    def _create_vector_store_with_files(
            self,
            assistant_config: AssistantConfig,
            vector_store: VectorStoreConfig,
            timeout: Optional[float] = None
    ) -> str:
        try:
            client_vs = self._ai_client.agents.create_vector_store(
                name=vector_store.name,
                file_ids=list(vector_store.files.values()),
                metadata=vector_store.metadata,
                expires_after=vector_store.expires_after,
            )
            return client_vs.id
        except Exception as e:
            logger.error(f"Failed to create vector store for agent: {assistant_config.name}: {e}")
            raise EngineError(f"Failed to create vector store for agent: {assistant_config.name}: {e}")

    def _update_tool_resources(
        self,
        assistant_config: AssistantConfig,
        timeout: Optional[float] = None
    ) -> Optional[dict]:
        try:
            logger.info(f"Updating tool resources for agent: {assistant_config.name}")

            # If there's no tool_resources object in the config, we cannot update anything
            if not assistant_config.tool_resources:
                logger.info("No tool resources provided for agent.")
                return None

            cloud_agent = self._retrieve_agent(assistant_config.assistant_id, timeout=timeout)
            
            tool_resources = {}
            if assistant_config.code_interpreter:
                # Identify which files are already present
                cloud_file_ids = set()
                if cloud_agent.tool_resources.code_interpreter:
                    cloud_file_ids = set(cloud_agent.tool_resources.code_interpreter.file_ids)

                # Files user wants attached for this interpreter
                local_files = assistant_config.tool_resources.code_interpreter_files
                self._delete_files(assistant_config, cloud_file_ids, local_files, timeout=timeout)
                self._upload_files(assistant_config, local_files, timeout=timeout)

                # Add code interpreter resources to dictionary
                tool_resources["code_interpreter"] = {
                    "file_ids": list(local_files.values()) if local_files else []
                }

            if assistant_config.file_search:
                existing_vs_ids = []
                existing_fs_file_ids = set()
                if cloud_agent.tool_resources.file_search:
                    existing_vs_ids = cloud_agent.tool_resources.file_search.vector_store_ids or []
                    if existing_vs_ids:
                        vs_files = self._ai_client.agents.list_vector_store_files(existing_vs_ids[0])
                        all_files_in_vs = vs_files.data
                        existing_fs_file_ids = {file.id for file in all_files_in_vs}

                file_search_vs = None
                vector_stores = assistant_config.tool_resources.file_search_vector_stores
                if vector_stores:
                    file_search_vs = vector_stores[0]
                    # If there's no existing VS ID and we haven't created one yet, make it
                    if not existing_vs_ids and file_search_vs.id is None:
                        self._upload_files(assistant_config, file_search_vs.files, timeout=timeout)
                        file_search_vs.id = self._create_vector_store_with_files(
                            assistant_config, file_search_vs, timeout=timeout
                        )
                    # Otherwise, if files differ, update or remove the old ones
                    elif file_search_vs.id in existing_vs_ids and (
                        set(file_search_vs.files.values()) != existing_fs_file_ids
                    ):
                        self._delete_files_from_vector_store(
                            assistant_config,
                            existing_vs_ids[0],
                            existing_fs_file_ids,
                            file_search_vs.files,
                            timeout=timeout
                        )
                        self._upload_files_to_vector_store(
                            assistant_config,
                            existing_vs_ids[0],
                            file_search_vs.files,
                            timeout=timeout
                        )

                # Add file search resources to dictionary
                tool_resources["file_search"] = {
                    "vector_store_ids": [file_search_vs.id] if file_search_vs and file_search_vs.id else []
                }

            # If we ended up with no tool resources to update, return None
            logger.info(f"Updated tool resources: {tool_resources if tool_resources else None}")
            return tool_resources if tool_resources else None

        except Exception as e:
            logger.error(f"Failed to update tool resources for agent: {assistant_config.name}: {e}")
            raise EngineError(f"Failed to update tool resources for agent: {assistant_config.name}: {e}")

    def purge(
            self,
            timeout: Optional[float] = None
    ) -> None:
        """
        Purges the agent from the cloud service and the local configuration.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        try:
            logger.info(f"Purging agent with name: {self.name}")
            config_manager = AssistantConfigManager.get_instance()
            assistant_config = config_manager.get_config(self.name)

            self._delete_agent(assistant_config, timeout=timeout)
            config_manager.delete_config(assistant_config.name)
            self._clear_variables()
        except Exception as e:
            logger.error(f"Failed to purge agent with name: {self.name}: {e}")
            raise EngineError(f"Failed to purge agent with name: {self.name}: {e}")

    def get_azure_search_connections(self) -> list:
        """
        Returns a list of connection IDs for connections 
        whose type is Azure AI Search.
        """
        conn_list = self._ai_client.connections.list()
        azure_search_ids = []
        for conn in conn_list:
            # Check your actual condition for Azure AI Search
            if conn.connection_type == ConnectionType.AZURE_AI_SEARCH:
                azure_search_ids.append(conn.id)
        return azure_search_ids

    def get_bing_search_connections(self) -> list:
        """
        Returns a list of connection IDs for connections 
        pointing to Bing Search endpoint.
        """
        conn_list = self._ai_client.connections.list()
        bing_ids = []
        for conn in conn_list:
            # Check your actual condition for Bing 
            if conn.endpoint_url and conn.endpoint_url.lower().startswith("https://api.bing.microsoft.com"):
                bing_ids.append(conn.id)
        return bing_ids

    def _delete_agent(
            self, 
            assistant_config: AssistantConfig,
            timeout: Optional[float] = None
    ):
        try:
            assistant_id = assistant_config.assistant_id
            self._ai_client.agents.delete_agent(
                assistant_id=assistant_id
            )
            logger.info(f"Deleted agent with ID: {assistant_id}")
        except Exception as e:
            logger.error(f"Failed to delete agent with ID: {assistant_id}: {e}")
            raise EngineError(f"Failed to delete agent with ID: {assistant_id}: {e}")

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
        :param additional_instructions: Additional instructions to provide to the agent.
        :param timeout: The HTTP request timeout in seconds.
        :param stream: Flag to indicate if the messages should be processed in streaming mode.
        """
        threads_config: ConversationThreadConfig = self._conversation_thread_client.get_config()
        thread_id = threads_config.get_thread_id_by_name(thread_name)

        try:
            if stream:
                self._process_messages_streaming(thread_name, thread_id, additional_instructions, timeout)
            else:
                self._process_messages_non_streaming(thread_name, thread_id, additional_instructions, timeout)
        except Exception as e:
            logger.error(f"Error occurred during processing messages: {e}")
            raise EngineError(f"Error occurred during processing messages: {e}")

    def get_run_steps(self, thread_name: str, run_id: str, timeout: Optional[float] = None) -> List[dict]:
        """
        Retrieves the steps of a run in a thread.

        :param thread_name: The name of the thread to get the run steps from.
        :param run_id: The ID of the run to get the steps from.
        :param timeout: The HTTP request timeout in seconds.

        :return: The steps of the run.
        :rtype: List[dict]
        """
        threads_config: ConversationThreadConfig = self._conversation_thread_client.get_config()
        thread_id = threads_config.get_thread_id_by_name(thread_name)

        try:
            run_steps = self._ai_client.agents.list_run_steps(thread_id=thread_id, run_id=run_id)
            return run_steps.data
        except Exception as e:
            logger.error(f"Failed to retrieve run steps for run {run_id}: {e}")
            raise EngineError(f"Failed to retrieve run steps for run {run_id}: {e}")

    def _process_messages_non_streaming(
            self,
            thread_name: str,
            thread_id: str,
            additional_instructions: Optional[str] = None,
            timeout: Optional[float] = None
    ) -> None:
        try:
            text_completion_config = self._assistant_config.text_completion_config
            logger.info(f"Creating a run for agent: {self.assistant_config.assistant_id} and thread: {thread_id}")

            run = self._ai_client.agents.create_run(
                thread_id=thread_id,
                assistant_id=self.assistant_config.assistant_id,
                additional_instructions=additional_instructions,
                temperature=None if text_completion_config is None else text_completion_config.temperature,
                max_completion_tokens=None if text_completion_config is None else text_completion_config.max_completion_tokens,
                max_prompt_tokens=None if text_completion_config is None else text_completion_config.max_prompt_tokens,
                top_p=None if text_completion_config is None else text_completion_config.top_p,
                response_format=None if text_completion_config is None else {'type': text_completion_config.response_format},
                truncation_strategy=None if text_completion_config is None else text_completion_config.truncation_strategy
            )

            run_start_time = str(datetime.now())
            conversation = self._conversation_thread_client.retrieve_conversation(
                thread_name
            )
            user_request = conversation.get_last_text_message("user").content
            self._callbacks.on_run_start(self._name, run.id, run_start_time, user_request)

            if self._cancel_run_requested.is_set():
                self._cancel_run_requested.clear()

            is_first_message = True
            while True:
                time.sleep(0.5)
                run = self._ai_client.agents.get_run(thread_id=thread_id, run_id=run.id)
                if run is None:
                    logger.error("Retrieved run is None, exiting the loop.")
                    return

                if self._cancel_run_requested.is_set():
                    self._ai_client.agents.cancel_run(thread_id=thread_id, run_id=run.id)
                    self._cancel_run_requested.clear()
                    logger.info("Processing run cancelled by user, exiting the loop.")
                    return

                logger.debug(f"Run {run.id} status: {run.status}")
                self._callbacks.on_run_update(self._name, run.id, run.status, thread_name, is_first_message)
                is_first_message = False

                if run.status in ["completed", "failed", "cancelled", "expired"]:
                    self._handle_terminal_run_status(run, thread_name)
                    return

                if run.status == "requires_action" and isinstance(run.required_action, SubmitToolOutputsAction):
                    tool_calls = run.required_action.submit_tool_outputs.tool_calls
                    if not self._handle_required_action(self._name, thread_id, run.id, tool_calls):
                        return

        except Exception as e:
            logger.error(f"Error occurred during non-streaming processing run: {e}")
            raise EngineError(f"Error occurred during non-streaming processing run: {e}")

    def _handle_terminal_run_status(self, run : ThreadRun, thread_name):
        run_end_time = str(datetime.now())

        if run.status == "completed":
            logger.info("Processing run status: completed")
            self._callbacks.on_run_end(self._name, run.id, run_end_time, thread_name)
        elif run.status == "failed":
            logger.warning(f"Processing run status: failed, error: {run.last_error}")
            self._callbacks.on_run_failed(
                self._name,
                run.id,
                run_end_time,
                run.last_error.code if run.last_error else "",
                run.last_error.message if run.last_error else "",
                thread_name
            )
        else:  # "cancelled" or "expired"
            logger.info(f"Processing run status: {run.status}")
            self._callbacks.on_run_cancelled(self._name, run.id, run_end_time, thread_name)

    def _process_messages_streaming(
            self, 
            thread_name: str,
            thread_id: str,
            additional_instructions: Optional[str] = None,
            timeout: Optional[float] = None
    ) -> None:
        try:
            from azure.ai.assistant.management.agent_stream_event_handler import AgentStreamEventHandler

            logger.info(f"Creating and streaming a run for agent: {self._assistant_config.assistant_id} and thread: {thread_id}")
            text_completion_config = self._assistant_config.text_completion_config

            with self._ai_client.agents.create_stream(
                thread_id=thread_id,
                assistant_id=self._assistant_config.assistant_id,
                additional_instructions=additional_instructions,
                temperature=None if text_completion_config is None else text_completion_config.temperature,
                max_completion_tokens=None if text_completion_config is None else text_completion_config.max_completion_tokens,
                max_prompt_tokens=None if text_completion_config is None else text_completion_config.max_prompt_tokens,
                top_p=None if text_completion_config is None else text_completion_config.top_p,
                response_format=None if text_completion_config is None else {'type': text_completion_config.response_format},
                truncation_strategy=None if text_completion_config is None else text_completion_config.truncation_strategy,
                event_handler=AgentStreamEventHandler(self, thread_id),
            ) as stream:
                stream.until_done()

        except Exception as e:
            logger.error(f"Error occurred during streaming processing run: {e}")
            raise EngineError(f"Error occurred during streaming processing run: {e}")

    def _handle_required_action(self, name, thread_id, run_id, tool_calls, timeout: Optional[float] = None) -> bool:
        if tool_calls is None:
            logger.error("Processing run requires tool call action but no tool calls provided.")
            self._ai_client.agents.cancel_run(thread_id=thread_id, run_id=run_id)
            return False

        tool_outputs = self._process_tool_calls(name, run_id, tool_calls)
        if not tool_outputs:
            return False

        self._ai_client.agents.submit_tool_outputs_to_run(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=tool_outputs,
        )
        return True

    def _process_tool_calls(self, name, run_id, tool_calls: list[RequiredFunctionToolCall]) -> list[dict]:
        tool_outputs = []
        for tool_call in tool_calls:
            start_time = time.time()
            function_response = str(self._handle_function_call(tool_call.function.name, tool_call.function.arguments))
            end_time = time.time()
            logger.debug(f"Total time taken for function {tool_call.function.name}: {end_time - start_time} seconds")
            logger.info(f"Function response: {function_response}")

            self._callbacks.on_function_call_processed(
                name, run_id, tool_call.function.name, tool_call.function.arguments, function_response
            )
            tool_outputs.append({
                "tool_call_id": tool_call.id,
                "output": function_response,
            })
        return tool_outputs

    def _retrieve_agent(
            self, 
            assistant_id: str,
            timeout: Optional[float] = None
    ):
        try:
            logger.info(f"Retrieving agent with ID: {assistant_id}")
            return self._ai_client.agents.get_agent(assistant_id=assistant_id)
        except Exception as e:
            logger.error(f"Failed to retrieve agent with ID: {assistant_id}: {e}")
            raise EngineError(f"Failed to retrieve agent with ID: {assistant_id}: {e}")

    def _delete_files_from_vector_store(
            self,
            assistant_config: AssistantConfig,
            vector_store_id: str,
            existing_file_ids: set,
            updated_files: Optional[dict] = None,
            delete_from_service: Optional[bool] = True,
            timeout: Optional[float] = None
    ):
        updated_file_ids = set(updated_files.values())
        file_ids_to_delete = existing_file_ids - updated_file_ids
        logger.info(f"Deleting files: {file_ids_to_delete} from agent: {assistant_config.name} vector store: {vector_store_id}")
        for file_id in file_ids_to_delete:
            self._ai_client.agents.delete_vector_store_file(
                vector_store_id=vector_store_id,
                file_id=file_id,
            )
            if delete_from_service:
                self._ai_client.agents.delete_file(file_id=file_id)

    def _upload_files_to_vector_store(
            self,
            assistant_config: AssistantConfig,
            vector_store_id: str,
            updated_files: Optional[dict] = None,
            timeout: Optional[float] = None
    ):
        logger.info(f"Uploading files to agent {assistant_config.name} vector store: {vector_store_id}")
        for file_path, file_id in updated_files.items():
            if file_id is None:
                logger.info(f"Uploading file: {file_path} for agent: {assistant_config.name}")

                with open(file_path, "rb") as f:
                    uploaded_file = self._ai_client.agents.upload_file_and_poll(
                        file=f,
                        purpose='assistants',
                    )
                    file = self._ai_client.agents.create_vector_store_file_and_poll(
                        vector_store_id=vector_store_id,
                        file_id=uploaded_file.id,
                    )
                    updated_files[file_path] = file.id

    def _delete_files(
            self,
            assistant_config: AssistantConfig,
            cloud_file_ids: set,
            local_files: Optional[dict] = None,
            timeout: Optional[float] = None
    ):
        try:
            local_file_ids = set(local_files.values())
            file_ids_to_delete = cloud_file_ids - local_file_ids
            logger.info(f"Deleting files: {file_ids_to_delete} for agent: {assistant_config.name}")
            for file_id in file_ids_to_delete:
                self._ai_client.agents.delete_file(file_id=file_id)
        except Exception as e:
            logger.warning(f"Failed to delete files for agent: {assistant_config.name}: {e}")
            # ignore the error and continue

    def _upload_files(
            self, 
            assistant_config: AssistantConfig,
            local_files: Optional[dict] = None,
            timeout: Optional[float] = None
    ):
        logger.info(f"Uploading files for agent: {assistant_config.name}")
        for file_path, file_id in local_files.items():
            if file_id is None:
                logger.info(f"Uploading file: {file_path} for agent: {assistant_config.name}")
                with open(file_path, "rb") as f:
                    uploaded_file = self._ai_client.agents.upload_file(
                        file=f,
                        purpose='assistants',
                    )
                local_files[file_path] = uploaded_file.id

    def _update_agent(
            self, 
            assistant_config: AssistantConfig,
            timeout: Optional[float] = None
    ):
        try:
            logger.info(f"Updating agent with ID: {assistant_config.assistant_id}")
            instructions = self._replace_file_references_with_content(assistant_config)
            tool_resources = self._update_tool_resources(assistant_config)
            tools, resources = self._build_tools_and_resources(assistant_config, tool_resources)

            self._ai_client.agents.update_agent(
                assistant_id=assistant_config.assistant_id,
                name=assistant_config.name,
                instructions=instructions,
                tools=tools,
                tool_resources=resources,
                model=assistant_config.model,
            )

        except Exception as e:
            logger.error(f"Failed to update agent with ID: {assistant_config.assistant_id}: {e}")
            raise EngineError(f"Failed to update agent with ID: {assistant_config.assistant_id}: {e}")

    def _build_tools_and_resources(
        self,
        assistant_config: AssistantConfig,
        tool_resources: Optional[dict]
    ) -> Tuple[List[dict], Optional["ToolResources"]]:

        tools = []
        resources = {}
        standard_functions = []
        openapi_functions = []

        for f_spec in assistant_config.functions:
            f_type = f_spec.get("type")
            if f_type == "openapi":
                openapi_functions.append(f_spec)
            else:
                standard_functions.append(f_spec)

        # Build an OpenApiTool and add its definitions
        openapi_tool = None
        for idx, f_spec in enumerate(openapi_functions):
            openapi_data = f_spec.get("openapi", {})
            function_name = openapi_data.get("name", "openapi_function")
            description = openapi_data.get("description", f"OpenAPI function {function_name}")

            # Parse auth config, TODO: add more auth types
            auth_config = f_spec.get("auth", {})
            auth = OpenApiAnonymousAuthDetails()

            if idx == 0:
                # For the first OpenAPI function, create the primary OpenApiTool
                openapi_tool = OpenApiTool(
                    name=function_name,
                    spec=openapi_data.get("spec", {}),
                    description=description,
                    auth=auth
                )
            else:
                # For subsequent OpenAPI functions, add them as definitions to the same tool
                openapi_tool.add_definition(
                    name=function_name,
                    spec=openapi_data.get("spec", {}),
                    description=description,
                    auth=auth
                )

        # If we found any OpenAPI functions, merge that one tool’s definitions
        if openapi_tool is not None:
            tools.extend(openapi_tool.definitions)

        # Handle the standard “tool_resources” (Code Interpreter, etc.)
        if tool_resources is not None:
            # Code Interpreter Tool
            if "code_interpreter" in tool_resources:
                ci_data = tool_resources["code_interpreter"]
                file_ids = ci_data.get("file_ids", [])
                code_interpreter_tool = CodeInterpreterTool(file_ids=file_ids)
                tools.extend(code_interpreter_tool.definitions)
                resources = code_interpreter_tool.resources

            # File Search Tool
            if "file_search" in tool_resources:
                fs_data = tool_resources["file_search"]
                vector_store_ids = fs_data.get("vector_store_ids", [])
                file_search_tool = FileSearchTool(vector_store_ids=vector_store_ids)
                tools.extend(file_search_tool.definitions)
                resources.update(file_search_tool.resources)
        else:
            # If code interpreter is enabled without tool_resources
            if assistant_config.code_interpreter:
                code_interpreter_tool = CodeInterpreterTool()
                tools.extend(code_interpreter_tool.definitions)
                resources = code_interpreter_tool.resources

        # Add the Azure AI Search if enabled
        if assistant_config.azure_ai_search.get("enabled", False):
            conn_id = assistant_config.azure_ai_search.get("connection_id", "")
            index_name = assistant_config.azure_ai_search.get("index_name", "")
            if conn_id and index_name:
                azure_ai_search_tool = AzureAISearchTool(index_connection_id=conn_id, index_name=index_name)
                tools.extend(azure_ai_search_tool.definitions)
                if azure_ai_search_tool.resources:
                    resources.update(azure_ai_search_tool.resources)

        # Add the Bing Search if enabled
        if assistant_config.bing_search.get("enabled", False):
            conn_id = assistant_config.bing_search.get("connection_id", "")
            if conn_id:
                bing_search_tool = BingGroundingTool(connection_id=conn_id)
                tools.extend(bing_search_tool.definitions)
                if bing_search_tool.resources:
                    resources.update(bing_search_tool.resources)

        # Add the standard functions to the tools list
        if standard_functions:
            modified_functions = []
            for func in standard_functions:
                # Create a copy so we can remove the module field safely
                func_copy = copy.deepcopy(func)
                if "function" in func_copy and "module" in func_copy["function"]:
                    del func_copy["function"]["module"]
                modified_functions.append(func_copy)
            tools.extend(modified_functions)

        # Convert resources dict to a ToolResources object if needed
        if not resources:
            resources = None
        else:
            toolset = ToolSet()
            resources = toolset._create_tool_resources_from_dict(resources)

        return tools, resources