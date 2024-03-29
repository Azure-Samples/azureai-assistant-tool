# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.base_assistant_client import BaseAssistantClient
from azure.ai.assistant.management.async_conversation_thread_client import AsyncConversationThreadClient
from azure.ai.assistant.management.conversation_thread_config import ConversationThreadConfig
from azure.ai.assistant.management.exceptions import EngineError, InvalidJSONError
from azure.ai.assistant.management.logger_module import logger

from openai import AsyncAzureOpenAI, AsyncOpenAI

from typing import Optional, Union
from datetime import datetime
import json, time
import copy
import asyncio


class AsyncAssistantClient(BaseAssistantClient):
    """
    A class that manages an assistant client.

    The assistant client is used to create, retrieve, update, and delete assistants in the cloud service 
    using the given AI client type and json configuration data.

    Use the `from_json` or `from_config` factory methods to create an instance of this class.

    :param config_json: The configuration data to use to create the assistant client.
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
        await self._init_assistant_client(self._config_data, is_create, timeout)

    @classmethod
    async def from_json(
        cls,
        config_json: str,
        callbacks: Optional[AssistantClientCallbacks] = None,
        timeout: Optional[float] = None
    ) -> "AsyncAssistantClient":
        """
        Creates an AsyncAssistantClient instance from JSON configuration data.

        :param config_json: JSON string containing the configuration for the assistant.
        :type config_json: str
        :param callbacks: Optional callbacks for the assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :return: An instance of AsyncAssistantClient.
        :rtype: AsyncAssistantClient
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
    ) -> "AsyncAssistantClient":
        """
        Creates an AsyncAssistantClient instance from an AssistantConfig object.

        :param config: AssistantConfig object containing the configuration for the assistant.
        :type config: AssistantConfig
        :param callbacks: Optional callbacks for the assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :return: An instance of AsyncAssistantClient.
        :rtype: AsyncAssistantClient
        """
        try:
            instance = cls(config.to_json(), callbacks)  # Instance creation without async init
            is_create = not config.assistant_id
            await instance._async_init(is_create, timeout)  # Perform async initialization
            return instance
        except Exception as e:
            logger.error(f"Failed to create assistant client from config: {e}")
            raise EngineError(f"Failed to create assistant client from config: {e}")

    async def sync_from_cloud(
            self,
            timeout: Optional[float] = None
    ) -> "AsyncAssistantClient":
        """
        Synchronizes the assistant client with the cloud service configuration.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: The assistant client with the given name.
        :rtype: AsyncAssistantClient
        """
        try:
            # If not registered, retrieve data from cloud and register it to AssistantConfig using AssistantConfigManager
            #TODO fill the config data from the cloud service by default
            config_manager = AssistantConfigManager.get_instance()
            assistant_config = config_manager.get_config(self.name)
            if assistant_config is None:
                raise EngineError(f"Assistant with name: {self.name} does not exist.")

            # Retrieve the assistant from the cloud service and update the local configuration
            assistant = await self._retrieve_assistant(assistant_config.assistant_id, timeout)
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

    async def _init_assistant_client(
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
                await self._create_assistant(assistant_config, timeout=timeout)
                end_time = time.time()
                logger.debug(f"Total time taken for _create_assistant: {end_time - start_time} seconds")
            else:
                start_time = time.time()
                config_manager = AssistantConfigManager.get_instance()
                local_config = config_manager.get_config(self.name)
                # check if the local configuration is different from the given configuration
                if local_config and local_config != assistant_config:
                    logger.debug("Local config is different from the given configuration. Updating the assistant...")
                    await self._update_assistant(assistant_config, timeout=timeout)
                else:
                    logger.debug("Local config is the same as the given configuration. No need to update the assistant.")
                end_time = time.time()
                logger.debug(f"Total time taken for _update_assistant: {end_time - start_time} seconds")

            start_time = time.time()
            await asyncio.to_thread(self._load_selected_functions, assistant_config)
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

    async def _create_assistant(
            self, 
            assistant_config: AssistantConfig,
            timeout: Optional[float] = None
    ):
        try:
            logger.info(f"Creating new assistant with name: {assistant_config.name}")
            # Upload the files for new assistant
            await self._upload_new_files(assistant_config, timeout=timeout)
            file_ids = list(assistant_config.knowledge_files.values())
            tools = self._update_tools(assistant_config)
            instructions = self._replace_file_references_with_content(assistant_config)

            assistant = await self._async_client.beta.assistants.create(
                name=assistant_config.name,
                instructions=instructions,
                tools=tools,
                model=assistant_config.model,
                file_ids=file_ids,
                timeout=timeout
            )
            # Update the assistant_id in the assistant_config
            assistant_config.assistant_id = assistant.id
            logger.info(f"Created new assistant with ID: {assistant.id}")
        except Exception as e:
            logger.error(f"Failed to create new assistant with name: {assistant_config.name}: {e}")
            raise EngineError(f"Failed to create new assistant with name: {assistant_config.name}: {e}")

    async def purge(
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
            await self._delete_assistant(assistant_config, timeout=timeout)

            # remove from the local config
            config_manager.delete_config(assistant_config.name)

            self._clear_variables()

        except Exception as e:
            logger.error(f"Failed to purge assistant with name: {self.name}: {e}")
            raise EngineError(f"Failed to purge assistant with name: {self.name}: {e}")

    async def _delete_assistant(
            self, 
            assistant_config : AssistantConfig,
            timeout : Optional[float] = None
    ):
        try:
            assistant_id = assistant_config.assistant_id
            await self._async_client.beta.assistants.delete(
                assistant_id=assistant_id,
                timeout=timeout
            )
            # delete threads associated with the assistant
            logger.info(f"Deleted assistant with ID: {assistant_id}")
        except Exception as e:
            logger.error(f"Failed to delete assistant with ID: {assistant_id}: {e}")
            raise EngineError(f"Failed to delete assistant with ID: {assistant_id}: {e}")

    async def _update_files(
            self,
            assistant_config: AssistantConfig,
            timeout: Optional[float] = None
    ) -> None:

        try:
            logger.info(f"Updating files for assistant: {assistant_config.name}")
            assistant = await self._retrieve_assistant(assistant_config.assistant_id, timeout=timeout)
            existing_file_ids = set(assistant.file_ids)
            await self._delete_old_files(assistant_config, existing_file_ids, timeout=timeout)
            await self._upload_new_files(assistant_config, timeout=timeout)

        except Exception as e:
            logger.error(f"Failed to update files for assistant: {assistant_config.name}: {e}")
            raise EngineError(f"Failed to update files for assistant: {assistant_config.name}: {e}")

    async def process_messages(
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
        threads_config : ConversationThreadConfig = AsyncConversationThreadClient.get_instance(self._ai_client_type).get_config()
        thread_id = threads_config.get_thread_id_by_name(thread_name)

        try:
            if stream:
                await self._process_messages_streaming(thread_name, thread_id, additional_instructions, timeout)
            else:
                await self._process_messages_non_streaming(thread_name, thread_id, additional_instructions, timeout)
        except Exception as e:
            logger.error(f"Error occurred during processing messages: {e}")
            raise EngineError(f"Error occurred during processing messages: {e}")

    async def _process_messages_non_streaming(
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
            logger.info(f"Creating a run for assistant: {self.assistant_config.assistant_id} and thread: {thread_id}")
            if additional_instructions is None:
                run = await self._async_client.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=self.assistant_config.assistant_id,
                    timeout=timeout
                )
            else:
                run = await self._async_client.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=self.assistant_config.assistant_id,
                    additional_instructions=additional_instructions,
                    timeout=timeout
                )

            # call the start_run callback
            run_start_time = str(datetime.now())
            self._callbacks.on_run_start(self._name, run.id, run_start_time, "Processing user input")
            self._user_input_processing_cancel_requested = False

            while True:
                time.sleep(0.5)

                logger.debug(f"Retrieving run: {run.id} with status: {run.status}")
                run = await self._async_client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id,
                    timeout=timeout
                )

                if run is None:
                    logger.error("Retrieved run is None, exiting the loop.")
                    return None

                logger.info(f"Processing run: {run.id} with status: {run.status}")

                if self._user_input_processing_cancel_requested:
                    await self._async_client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run.id, timeout=timeout)
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
                    if not await self._handle_required_action(self._name, thread_id, run.id, tool_calls):
                        return None

        except Exception as e:
            logger.error(f"Error occurred during non-streaming processing run: {e}")
            raise EngineError(f"Error occurred during non-streaming processing run: {e}")

    async def _process_messages_streaming(
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
        from azure.ai.assistant.management.async_stream_event_handler import AsyncStreamEventHandler
        try:
            logger.info(f"Creating and streaming a run for assistant: {self._assistant_config.assistant_id} and thread: {thread_id}")

            # Start the streaming process
            async with self._async_client.beta.threads.runs.create_and_stream(
                thread_id=thread_id,
                assistant_id=self._assistant_config.assistant_id,
                instructions=self._assistant_config.instructions,
                event_handler=AsyncStreamEventHandler(self, thread_id, timeout=timeout),
                timeout=timeout
            ) as stream:
                await stream.until_done()

        except Exception as e:
            logger.error(f"Error occurred during streaming processing run: {e}")
            raise EngineError(f"Error occurred during streaming processing run: {e}")

    async def _handle_required_action(self, name, thread_id, run_id, tool_calls, timeout : Optional[float] = None, stream : Optional[bool] = None) -> bool:
        from azure.ai.assistant.management.async_stream_event_handler import AsyncStreamEventHandler
        logger.info("Handling required action")
        if tool_calls is None:
            logger.error("Processing run requires tool call action but no tool calls provided.")
            await self._async_client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id, timeout=timeout)
            return False

        tool_outputs = await self._process_tool_calls(name, run_id, tool_calls)
        if not tool_outputs:
            return False

        if stream:
            logger.info("Submitting tool outputs with stream")
            async with self._async_client.beta.threads.runs.submit_tool_outputs_stream(
                thread_id=thread_id,
                run_id=run_id,
                tool_outputs=tool_outputs,
                timeout=timeout,
                event_handler=AsyncStreamEventHandler(self, thread_id, is_submit_tool_call=True)
            ) as stream:
                await stream.until_done()
        else:
            await self._async_client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run_id,
                tool_outputs=tool_outputs,
                timeout=timeout
            )
        return True

    async def _process_tool_calls(self, name, run_id, tool_calls):
        tool_outputs = []
        for tool_call in tool_calls:
            start_time = time.time()
            
            function_response = await asyncio.to_thread(self._handle_function_call, tool_call.function.name, tool_call.function.arguments)
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

    async def _retrieve_assistant(
            self, 
            assistant_id : str,
            timeout : Optional[float] = None
    ):
        try:
            logger.info(f"Retrieving assistant with ID: {assistant_id}")
            assistant = await self._async_client.beta.assistants.retrieve(
                assistant_id=assistant_id,
                timeout=timeout
            )
            return assistant
        except Exception as e:
            logger.error(f"Failed to retrieve assistant with ID: {assistant_id}: {e}")
            raise EngineError(f"Failed to retrieve assistant with ID: {assistant_id}: {e}")

    async def _delete_old_files(
            self,
            assistant_config : AssistantConfig,
            existing_file_ids,
            timeout : Optional[float] = None
    ):
        updated_file_ids = set(assistant_config.knowledge_files.values())
        file_ids_to_delete = existing_file_ids - updated_file_ids
        logger.info(f"Deleting files: {file_ids_to_delete} for assistant: {assistant_config.name}")
        for file_id in file_ids_to_delete:
            file_deletion_status = await self._async_client.beta.assistants.files.delete(
                assistant_id=assistant_config.assistant_id,
                file_id=file_id,
                timeout=timeout
            )

    async def _upload_new_files(
            self, 
            assistant_config: AssistantConfig,
            timeout : Optional[float] = None
    ):
        logger.info(f"Uploading new files for assistant: {assistant_config.name}")
        for file_path, file_id in assistant_config.knowledge_files.items():
            if file_id is None:
                logger.info(f"Uploading file: {file_path} for assistant: {assistant_config.name}")
                file = await self._async_client.files.create(
                    file=open(file_path, "rb"),
                    purpose='assistants',
                    timeout=timeout
                )
                assistant_config.knowledge_files[file_path] = file.id

    async def _update_assistant(
            self, 
            assistant_config: AssistantConfig,
            timeout : Optional[float] = None
    ):
        try:
            logger.info(f"Updating assistant with ID: {assistant_config.assistant_id}")
            self._update_files(assistant_config)
            file_ids = list(assistant_config.knowledge_files.values())
            tools = self._update_tools(assistant_config)
            instructions = self._replace_file_references_with_content(assistant_config)

            # TODO update the assistant with the new configuration only if there are changes
            await self._async_client.beta.assistants.update(
                assistant_id=assistant_config.assistant_id,
                name=assistant_config.name,
                instructions=instructions,
                tools=tools,
                model=assistant_config.model,
                file_ids=file_ids,
                timeout=timeout
            )
        except Exception as e:
            logger.error(f"Failed to update assistant with ID: {assistant_config.assistant_id}: {e}")
            raise EngineError(f"Failed to update assistant with ID: {assistant_config.assistant_id}: {e}")

    def _update_tools(self, assistant_config: AssistantConfig):
        tools = []
        logger.info(f"Updating tools for assistant: {assistant_config.name}")
        # Add the retrieval tool to the tools list if there are knowledge files
        if assistant_config.knowledge_retrieval:
            tools.append({"type": "retrieval"})
        # Process and add the functions to the tools list if there are functions
        if assistant_config.selected_functions:
            modified_functions = []
            for function in assistant_config.selected_functions:
                # Create a copy of the function spec to avoid modifying the original
                modified_function = copy.deepcopy(function)
                # Remove the module field from the function spec
                if "function" in modified_function and "module" in modified_function["function"]:
                    del modified_function["function"]["module"]
                modified_functions.append(modified_function)
            tools.extend(modified_functions)
        # Add the code interpreter to the tools list if there is a code interpreter
        if assistant_config.code_interpreter:
            tools.append({"type": "code_interpreter"})
        return tools