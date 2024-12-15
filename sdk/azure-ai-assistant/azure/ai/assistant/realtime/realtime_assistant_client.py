# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.ai_client_factory import AIClientFactory, AIClientType
from azure.ai.assistant.management.assistant_config import AssistantConfig, AssistantType
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.base_assistant_client import BaseAssistantClient
from azure.ai.assistant.management.message import ConversationMessage
from azure.ai.assistant.management.text_message import TextMessage
from azure.ai.assistant.management.exceptions import EngineError, InvalidJSONError
from azure.ai.assistant.management.logger_module import logger
from realtime_ai.realtime_ai_client import RealtimeAIClient, RealtimeAIOptions, RealtimeAIEventHandler, AudioStreamOptions
from realtime_ai.models.realtime_ai_events import *

from typing import Optional
import json, uuid, yaml
from datetime import datetime
import threading, base64
import copy


class RealtimeAssistantEventHandler(RealtimeAIEventHandler):

    def __init__(self, ai_client: "RealtimeAssistantClient"):
        super().__init__()
        self._call_id_to_function_name = {}
        self._lock = threading.Lock()
        self._realtime_client = None
        self._function_processing = False
        self._ai_client = ai_client
        self._is_first_message = True
        self._is_transcription_for_audio_created = False
        self._thread_name = None
        self._keyword_run_identifier = None
        self._text_run_identifier = None
  
    def is_function_processing(self):
        return self._function_processing

    def set_realtime_client(self, client: RealtimeAIClient):
        self._realtime_client = client

    def set_thread_name(self, thread_name: str):
        self._thread_name = thread_name

    def on_error(self, event: ErrorEvent):
        logger.error(f"Error occurred: {event.error.message}")

    def is_run_active(self) -> bool:
        return self._keyword_run_identifier or self._text_run_identifier

    def on_keyword_armed(self, armed: bool):
        logger.info(f"Keyword detection armed: {armed}")
        if armed is False:
            self._keyword_run_identifier = self._create_identifier("keyword")
            self._realtime_client.send_text("Hello")
            self._ai_client.callbacks.on_run_start(assistant_name=self._ai_client.name, run_identifier=self._keyword_run_identifier, run_start_time=str(datetime.now()), user_input="keyword input")
        else:
            if self._keyword_run_identifier:
                self._ai_client.callbacks.on_run_end(assistant_name=self._ai_client.name, run_identifier=self._keyword_run_identifier, run_end_time=str(datetime.now()), thread_name=self._thread_name)
            self._keyword_run_identifier = None

    def on_input_audio_buffer_speech_stopped(self, event: InputAudioBufferSpeechStopped):
        logger.info(f"Server VAD: Speech stopped at {event.audio_end_ms}ms, Item ID: {event.item_id}")
        # If server VAD is enabled, notify the end of speech via callback
        #self._ai_client.callbacks._on_speech_end_detected()

    def on_input_audio_buffer_committed(self, event: InputAudioBufferCommitted):
        logger.debug(f"Audio Buffer Committed: {event.item_id}")

    def on_conversation_item_created(self, event: ConversationItemCreated):
        logger.info(f"New Conversation Item: {event.item}")
        with self._lock:
            if event.item.get("role") == "user":
                return
            if not self._keyword_run_identifier and self._text_run_identifier is None:
                self._text_run_identifier = self._create_identifier("text")
                self._ai_client.callbacks.on_run_start(assistant_name=self._ai_client.name, run_identifier=self._text_run_identifier, run_start_time=str(datetime.now()), user_input="text input")

    def on_response_created(self, event: ResponseCreated):
        logger.info(f"Response Created: {event.response}")

    def on_response_content_part_added(self, event: ResponseContentPartAdded):
        logger.debug(f"New Part Added: {event.part}")

    def on_response_audio_delta(self, event: ResponseAudioDelta):
        logger.debug(f"Received audio delta for Response ID {event.response_id}, Item ID {event.item_id}, Content Index {event.content_index}")
        self.handle_audio_delta(event)

    def on_response_audio_transcript_delta(self, event: ResponseAudioTranscriptDelta):
        logger.info(f"Assistant transcription delta: {event.delta}")
        message : ConversationMessage = ConversationMessage(self._ai_client)
        message.text_message = TextMessage(event.delta)
        self._ai_client.callbacks.on_run_update(
            assistant_name=self._ai_client.name, 
            run_identifier="", 
            run_status="streaming", 
            thread_name=self._thread_name, 
            is_first_message=self._is_first_message, 
            message=message)
        self._is_first_message = False

    def on_rate_limits_updated(self, event: RateLimitsUpdated):
        for rate in event.rate_limits:
            logger.debug(f"Rate Limit: {rate.name}, Remaining: {rate.remaining}")

    def on_conversation_item_input_audio_transcription_completed(self, event: ConversationItemInputAudioTranscriptionCompleted):
        logger.info(f"User transcription complete: {event.transcript}")
        # remove new line characters from the end of the transcript
        transcript = event.transcript.rstrip("\n")
        self._create_thread_message(message=transcript, role="user")

    def on_response_audio_done(self, event: ResponseAudioDone):
        logger.debug(f"Audio done for response ID {event.response_id}, item ID {event.item_id}")

    def on_response_audio_transcript_done(self, event: ResponseAudioTranscriptDone):
        logger.debug(f"Audio transcript done: '{event.transcript}' for response ID {event.response_id}")

    def on_response_content_part_done(self, event: ResponseContentPartDone):
        part_type = event.part.get("type")
        part_text = event.part.get("text", "")
        logger.debug(f"Content part done: '{part_text}' of type '{part_type}' for response ID {event.response_id}")

    def on_response_output_item_done(self, event: ResponseOutputItemDone):
        with self._lock:
            try:
                item_content = event.item.get("content", [])
                for item in item_content:
                    # If audio content is present, process the transcript
                    if item.get("type") != "audio":
                        continue
                    transcript = item.get("transcript")
                    if transcript:
                        logger.info(f"Assistant transcription complete: {transcript}")
                        self._create_thread_message(message=transcript, role="assistant")
                        self._is_first_message = True
                        self._is_transcription_for_audio_created = True
            except Exception as e:
                error_message = f"Failed to process output item: {e}"
                logger.error(error_message)

    def _create_thread_message(self, message: str, role: str):
        if role == "user":
            self._ai_client._conversation_thread_client.create_conversation_thread_message(message=message, thread_name=self._thread_name)
            conversation_message : ConversationMessage = ConversationMessage(self._ai_client)
            conversation_message.text_message = TextMessage(message)
            conversation_message.role = role
            conversation_message.sender = "user"
            self._ai_client.callbacks.on_run_update(
                assistant_name=self._ai_client.name, 
                run_identifier="",
                run_status="in_progress", 
                thread_name=self._thread_name,
                is_first_message=False,
                message=conversation_message)
        elif role == "assistant":
            self._ai_client._conversation_thread_client.create_conversation_thread_message(message=message, thread_name=self._thread_name, metadata={"chat_assistant": self._ai_client._name})
            self._ai_client.callbacks.on_run_update(
                assistant_name=self._ai_client.name, 
                run_identifier="", 
                run_status="in_progress", 
                thread_name=self._thread_name)

    def on_response_done(self, event: ResponseDone):
        logger.info(f"Assistant's response completed with response event content: {event}")

        with self._lock:
            try:
                completed = self._handle_response_done(event)
                if completed:
                    self._text_run_identifier = None
                    self._is_transcription_for_audio_created = False
            except Exception as e:
                error_message = f"Failed to process response: {e}"
                logger.error(error_message)
                self._text_run_identifier = None
                self._is_transcription_for_audio_created = False

    def _handle_response_done(self, event : ResponseDone) -> bool:
        # Check if the response is failed
        if event.response.get('status') == 'failed':
            self._handle_failed_response(event.response)
            return True
        
        # If keyword triggered run is not active, check the text triggered run messages here
        elif not self._keyword_run_identifier:
            is_function_call_present = self._check_function_call(event.response.get('output', []))

            # if function call is present, do not end the run yet
            if not is_function_call_present:
                if self._is_transcription_for_audio_created is False:
                    messages = self._extract_content_messages(event.response.get('output', []))
                    if messages:
                        self._create_thread_message(message=messages, role="assistant")
                self._ai_client.callbacks.on_run_end(assistant_name=self._ai_client.name, run_identifier=self._text_run_identifier, run_end_time=str(datetime.now()), thread_name=self._thread_name)
                return True

        return False

    def _handle_failed_response(self, response):
        status_details = response.get('status_details', {})
        error = status_details.get('error', {})
        
        error_type = error.get('type')
        error_code = error.get('code')
        error_message = error.get('message')
        
        # Handle the failed response in both keyword and text triggered runs
        run_identifier = self._text_run_identifier if not self._keyword_run_identifier else self._keyword_run_identifier

        # If the run is not started at all, call on_run_start with new run_identifier to make sure the contract is followed
        if run_identifier is None:
            run_identifier = self._create_identifier("failed")
            self._ai_client.callbacks.on_run_start(assistant_name=self._ai_client.name, run_identifier=run_identifier, run_start_time=str(datetime.now()), user_input="run failed")

        self._ai_client.callbacks.on_run_failed(assistant_name=self._ai_client.name, run_identifier=run_identifier, run_end_time=str(datetime.now()), error_code="", error_message=error_message, thread_name=self._thread_name)
        logger.error(f"Failed response: Type: {error_type}, Code: {error_code}, Message: {error_message}")

    def _check_function_call(self, output_list):
        return any(item.get('type') == 'function_call' for item in output_list)

    def _extract_content_messages(self, output_list):
        content_messages = []
        for item in output_list:
            if item.get('type') == 'message':
                content_list = item.get('content', [])
                for content in content_list:
                    if content.get('type') == 'text':
                        content_messages.append(content.get('text'))
        
        if not content_messages:
            return None
        
        return "\n".join(content_messages)

    def on_session_created(self, event: SessionCreated):
        logger.info(f"Session created: {event.session}")

    def on_session_updated(self, event: SessionUpdated):
        logger.info(f"Session updated: {event.session}")

    def on_input_audio_buffer_speech_started(self, event: InputAudioBufferSpeechStarted):
        logger.info(f"Server VAD: User speech started at {event.audio_start_ms}ms for item ID {event.item_id}")
        if self._realtime_client.options.turn_detection is not None:
            self._realtime_client.clear_input_audio_buffer()
            self._realtime_client.cancel_response()
            # If server VAD is enabled, interrupt the audio playback via callback via notification
            #self._ai_client.callbacks._on_speech_start_detected()

    def on_response_output_item_added(self, event: ResponseOutputItemAdded):
        logger.debug(f"Output item added for response ID {event.response_id} with item: {event.item}")
        if event.item.get("type") == "function_call":
            call_id = event.item.get("call_id")
            function_name = event.item.get("name")
            if call_id and function_name:
                with self._lock:
                    self._call_id_to_function_name[call_id] = function_name
                logger.debug(f"Registered function call. Call ID: {call_id}, Function Name: {function_name}")
            else:
                logger.warning("Function call item missing 'call_id' or 'name' fields.")

    def on_response_function_call_arguments_delta(self, event: ResponseFunctionCallArgumentsDelta):
        logger.debug(f"Function call arguments delta for call ID {event.call_id}: {event.delta}")

    def on_response_function_call_arguments_done(self, event: ResponseFunctionCallArgumentsDone):
        call_id = event.call_id
        arguments_str = event.arguments

        with self._lock:
            function_name = self._call_id_to_function_name.pop(call_id, None)

        if not function_name:
            logger.error(f"No function name found for call ID: {call_id}")
            return

        try:
            self._function_processing = True
            logger.info(f"Executing function '{function_name}' with arguments: {arguments_str} for call ID {call_id}")
            function_output = str(self._ai_client._handle_function_call(function_name, arguments_str))
            self._ai_client.callbacks.on_function_call_processed(
                assistant_name=self._ai_client.name, 
                run_identifier=self._text_run_identifier if not self._keyword_run_identifier else self._keyword_run_identifier,
                function_name=function_name, 
                arguments=arguments_str, 
                response=str(function_output))
            logger.info(f"Function output for call ID {call_id}: {function_output}")
            self._realtime_client.generate_response_from_function_call(call_id, function_output)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse arguments for call ID {call_id}: {e}")
            return
        finally:
            self._function_processing = False

    def on_unhandled_event(self, event_type: str, event_data: Dict[str, Any]):
        logger.warning(f"Unhandled Event: {event_type} - {event_data}")

    def handle_audio_delta(self, event: ResponseAudioDelta):
        delta_audio = event.delta
        if delta_audio:
            try:
                audio_bytes = base64.b64decode(delta_audio)
                self._ai_client.callbacks.on_run_audio_data(
                    assistant_name=self._ai_client.name, 
                    run_identifier=self._text_run_identifier if not self._keyword_run_identifier else self._keyword_run_identifier, 
                    audio_data=audio_bytes
                )
            except base64.binascii.Error as e:
                logger.error(f"Failed to decode audio delta: {e}")
        else:
            logger.warning("Received 'ResponseAudioDelta' event without 'delta' field.")

    def _create_identifier(self, prefix: str) -> str:
        short_id = uuid.uuid4().hex[:8]
        return f"{prefix}_{short_id}"


class RealtimeAssistantClient(BaseAssistantClient):
    """
    A class that manages a realtine assistant client.

    :param config_json: The configuration data to use to create the realtime client.
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
            callbacks: Optional[AssistantClientCallbacks],
            is_create: bool = True,
            timeout: Optional[float] = None,
            **client_args
    ) -> None:
        super().__init__(config_json, callbacks, **client_args)
        self._init_realtime_assistant_client(self._config_data, is_create, timeout=timeout)

    @classmethod
    def from_json(
        cls,
        config_json: str,
        callbacks: Optional[AssistantClientCallbacks],
        timeout: Optional[float] = None,
        **client_args
    ) -> "RealtimeAssistantClient":
        """
        Creates a RealtimeAssistantClient instance from JSON configuration data.

        :param config_json: JSON string containing the configuration for the realtime assistant.
        :type config_json: str
        :param callbacks: Optional callbacks for the realtime assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :param client_args: Additional keyword arguments for configuring the AI client.
        :type client_args: Dict

        :return: An instance of RealtimeAssistantClient.
        :rtype: RealtimeAssistantClient
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
        callbacks: Optional[AssistantClientCallbacks],
        timeout: Optional[float] = None,
        **client_args
    ) -> "RealtimeAssistantClient":
        """
        Creates an RealtimeAssistantClient instance from YAML configuration data.

        :param config_yaml: YAML string containing the configuration for the realtime assistant.
        :type config_yaml: str
        :param callbacks: Optional callbacks for the realtime assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :param client_args: Additional keyword arguments for configuring the AI client.
        :type client_args: Dict

        :return: An instance of RealtimeAssistantClient.
        :rtype: RealtimeAssistantClient
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
        callbacks: Optional[AssistantClientCallbacks],
        timeout: Optional[float] = None,
        **client_args
    ) -> "RealtimeAssistantClient":
        """
        Creates a RealtimeAssistantClient instance from an AssistantConfig object.

        :param config: AssistantConfig object containing the configuration for the realtime assistant.
        :type config: AssistantConfig
        :param callbacks: Optional callbacks for the realtime assistant client.
        :type callbacks: Optional[AssistantClientCallbacks]
        :param timeout: Optional timeout for HTTP requests.
        :type timeout: Optional[float]
        :param client_args: Additional keyword arguments for configuring the AI client.
        :type client_args: Dict

        :return: An instance of RealtimeAssistantClient.
        :rtype: RealtimeAssistantClient
        """
        try:
            config_json = config.to_json()
            return cls.from_json(config_json, callbacks, timeout, **client_args)
        except Exception as e:
            logger.error(f"Failed to create realtime client from config: {e}")
            raise EngineError(f"Failed to create realtime client from config: {e}")

    def update(
            self,
            config_json: str,
            timeout: Optional[float] = None
    ) -> None:
        """
        Updates the realtime assistant client with new configuration data.

        :param config_json: The configuration data to use to update the realtime client.
        :type config_json: str
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        try:
            config_data = json.loads(config_json)
            self._init_realtime_assistant_client(config_data, is_create=False, timeout=timeout)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            raise InvalidJSONError(f"Invalid JSON format: {e}")

    def _init_realtime_assistant_client(
            self, 
            config_data: dict,
            is_create: bool = True,
            timeout: Optional[float] = None
    ):
        try:
            # Create or update the assistant
            assistant_config = AssistantConfig.from_dict(config_data)

            tools = self._update_tools(assistant_config)
            self._tools = tools if tools else None
            self._load_selected_functions(assistant_config)
            self._assistant_config = assistant_config

            if self.ai_client_type == AIClientType.AZURE_OPEN_AI_REALTIME:
                azure_openai_api_version, azure_openai_endpoint = AIClientFactory.get_instance().get_azure_client_info()
            else:
                azure_openai_api_version, azure_openai_endpoint = None, None

            realtime_options = RealtimeAIOptions(
                api_key=self.ai_client.api_key,
                model=assistant_config.model,
                modalities=assistant_config.realtime_config.modalities,
                instructions=assistant_config.instructions,
                voice=assistant_config.realtime_config.voice,
                input_audio_format=assistant_config.realtime_config.input_audio_format,
                output_audio_format=assistant_config.realtime_config.output_audio_format,
                input_audio_transcription_enabled=True,
                input_audio_transcription_model=assistant_config.realtime_config.input_audio_transcription_model,
                turn_detection=None, #if assistant_config.realtime_config.turn_detection.get("type") == "local_vad" else assistant_config.realtime_config.turn_detection,
                tools=tools,
                tool_choice="auto",
                temperature=0.8 if not assistant_config.text_completion_config else assistant_config.text_completion_config.temperature,
                max_output_tokens="inf" if not assistant_config.text_completion_config else assistant_config.text_completion_config.max_output_tokens,
                azure_openai_api_version=azure_openai_api_version,
                azure_openai_endpoint=azure_openai_endpoint
            )

            # Check if the _realtime_client attribute exists and is set
            client_exists = hasattr(self, '_realtime_client') and self._realtime_client is not None

            if is_create or not client_exists:
                assistant_config.assistant_id = str(uuid.uuid4())
                self._create_realtime_client(realtime_options=realtime_options, timeout=timeout)
            else:
                self._update_realtime_client(realtime_options=realtime_options, timeout=timeout)

            # Update the local configuration using AssistantConfigManager
            # TODO make optional to save the assistant_config in the config manager
            config_manager = AssistantConfigManager.get_instance()
            config_manager.update_config(self._name, assistant_config.to_json())

        except Exception as e:
            logger.error(f"Failed to initialize assistant instance: {e}")
            raise EngineError(f"Failed to initialize assistant instance: {e}")

    def _update_tools(self, assistant_config: AssistantConfig):
        tools = []
        logger.info(f"Updating tools for realtime assistant: {assistant_config.name}")
        
        if assistant_config.functions:
            modified_functions = []
            for function in assistant_config.functions:
                # Create a copy of the function spec to avoid modifying the original
                modified_function = copy.deepcopy(function)
                
                # Check for old structure and modify to new structure
                if "function" in modified_function:
                    function_details = modified_function.pop("function")
                    # Remove the module field if it exists
                    function_details.pop("module", None)
                    
                    # Merge the `function_details` with `modified_function`
                    modified_function.update(function_details)
                
                modified_functions.append(modified_function)
            
            tools.extend(modified_functions)
                
        return tools
    
    def _create_realtime_client(
            self,
            realtime_options: RealtimeAIOptions,
            timeout: Optional[float] = None
    ) -> None:
        """
        Creates a realtime assistant client.

        :param realtime_options: The realtime AI options.
        :type realtime_options: RealtimeAIOptions
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]
        """
        try:
            self._event_handler = RealtimeAssistantEventHandler(ai_client=self)
            audio_stream_options = AudioStreamOptions(
                sample_rate=24000,
                channels=1,
                bytes_per_sample=2
            )
            self._realtime_client = RealtimeAIClient(options=realtime_options, stream_options=audio_stream_options, event_handler=self._event_handler)
            self._event_handler.set_realtime_client(self._realtime_client)

        except Exception as e:
            logger.error(f"Failed to create realtime client: {e}")
            raise EngineError(f"Failed to create realtime client: {e}")

    def _update_realtime_client(
            self,
            realtime_options: RealtimeAIOptions,
            timeout: Optional[float] = None
    ) -> None:
        """
        Updates the realtime assistant client. Currently, only the audio capture and realtime options are updated.

        :param realtime_options: The realtime AI options.
        :type realtime_options: RealtimeAIOptions
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]
        """
        try:
            if self._realtime_client:
                if self._realtime_client.is_running:
                    # Restart the realtime client to apply the new options
                    self._realtime_client.stop()
                    self._realtime_client.update_session(options=realtime_options)
                    self._realtime_client.start()
                else:
                    self._realtime_client.update_session(options=realtime_options)
            else:
                raise EngineError("Realtime client is not set and cannot be updated.")

        except Exception as e:
            logger.error(f"Failed to update realtime client: {e}")
            raise EngineError(f"Failed to update realtime client: {e}")

    def start(
            self,
            thread_name: str,
            timeout: Optional[float] = None
    ) -> None:
        """
        Starts the realtime assistant.

        :param thread_name: The name of the thread to process.
        :type thread_name: str
        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        try:
            self._event_handler.set_thread_name(thread_name)
            if not self._realtime_client.is_running:
                logger.info(f"Starting realtime assistant with name: {self.name}")
                self._realtime_client.start()
            self.callbacks.on_connected(assistant_name=self.name, assistant_type=AssistantType.REALTIME_ASSISTANT.value, thread_name=thread_name)
        except Exception as e:
            logger.error(f"Failed to start realtime assistant: {e}")
            raise EngineError(f"Failed to start realtime assistant: {e}")

    def stop(
            self,
            timeout: Optional[float] = None
    ) -> None:
        """
        Stops the realtime assistant.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        try:
            if self._realtime_client.is_running:
                logger.info(f"Stopping realtime assistant with name: {self.name}")
                self._realtime_client.stop()
            self.callbacks.on_disconnected(assistant_name=self.name, assistant_type=AssistantType.REALTIME_ASSISTANT.value)
        except Exception as e:
            logger.error(f"Failed to stop realtime assistant: {e}")
            raise EngineError(f"Failed to stop realtime assistant: {e}")

    def connect(
            self,
            timeout: Optional[float] = None
    ) -> None:
        """
        Connects the realtime assistant (uses WebSockets).

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        try:
            self._realtime_client.start()
        except Exception as e:
            logger.error(f"Failed to connect realtime assistant: {e}")
            raise EngineError(f"Failed to connect realtime assistant: {e}")

    def disconnect(
            self,
            timeout: Optional[float] = None
    ) -> None:
        """
        Closes the connection to the realtime assistant.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        try:
            self._realtime_client.stop()
        except Exception as e:
            logger.error(f"Failed to disconnect realtime assistant: {e}")
            raise EngineError(f"Failed to disconnect realtime assistant: {e}")

    def generate_response(
                self,
                user_input : str
        ) -> None:
            """
            Generates a realtime assistant response using the user's text input in the specified thread.
    
            :param user_input: The user's text input.
            :type user_input: str
            """
            try:
                if not self._realtime_client.is_running:
                    logger.info(f"Starting realtime assistant with name: {self.name}")
                    self._realtime_client.start()
    
                if self._event_handler.is_run_active():
                    self._realtime_client.cancel_response()
                    self._audio_player.drain_and_restart()
    
                logger.info(f"Sending text message: {user_input}")
                self._realtime_client.send_text(user_input)
    
            except Exception as e:
                logger.error(f"Error occurred during generating response: {e}")
                raise EngineError(f"Error occurred during generating response: {e}")

    def set_active_thread(
            self,
            thread_name: str
    ) -> None:
        """
        Sets the active thread for the realtime assistant.

        :param thread_name: The name of the thread to set as active.
        :type thread_name: str

        :return: None
        :rtype: None
        """
        if self._event_handler:
            self._event_handler.set_thread_name(thread_name)
        else:
            raise EngineError("Active thread cannot be set, check if the event handler is set in initialization.")

    def is_active_run(
            self
    ) -> bool:
        """
        Checks if the realtime assistant has an active run.

        :return: True if the assistant has an active run, False otherwise.
        :rtype: bool
        """
        if self._event_handler:
            return self._event_handler.is_run_active()
        return False

    def purge(
            self,
            timeout: Optional[float] = None
    )-> None:
        """
        Purges the realtime assistant from the local configuration.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        self._purge(timeout)

    def _purge(
            self,
            timeout: Optional[float] = None
    )-> None:
        try:
            logger.info(f"Purging realtime assistant with name: {self.name}")
            # retrieve the assistant configuration
            config_manager = AssistantConfigManager.get_instance()
            assistant_config = config_manager.get_config(self.name)

            # remove from the local config
            config_manager.delete_config(assistant_config.name)

            self._clear_variables()

        except Exception as e:
            logger.error(f"Failed to purge realtime assistant with name: {self.name}: {e}")
            raise EngineError(f"Failed to purge realtime assistant with name: {self.name}: {e}")
        
    def _send_conversation_history(self, thread_name: str):
        try:
            max_text_messages = self._assistant_config.text_completion_config.max_text_messages if self._assistant_config.text_completion_config else None
            conversation = self._conversation_thread_client.retrieve_conversation(thread_name=thread_name, max_text_messages=max_text_messages)
            for message in reversed(conversation.messages):
                if message.text_message:
                    logger.info(f"Sending text message: {message.text_message.content}, role: {message.role}")
                    self._realtime_client.send_text(message.text_message.content, role=message.role, generate_response=False)
        except Exception as e:
            logger.error(f"Failed to send conversation history: {e}")
            raise EngineError(f"Failed to send conversation history: {e}")
        
    @property
    def event_handler(self) -> RealtimeAssistantEventHandler:
        """
        Get the event handler for the realtime assistant client.

        :return: The event handler for the realtime assistant client.
        :rtype: RealtimeAssistantEventHandler
        """
        return self._event_handler