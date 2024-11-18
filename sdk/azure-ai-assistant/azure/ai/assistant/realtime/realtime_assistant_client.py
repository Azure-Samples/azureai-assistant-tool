# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.base_assistant_client import BaseAssistantClient
from azure.ai.assistant.management.message import ConversationMessage
from azure.ai.assistant.management.text_message import TextMessage
from azure.ai.assistant.management.exceptions import EngineError, InvalidJSONError
from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.realtime.audio_capture import AudioCapture, AudioCaptureEventHandler
from azure.ai.assistant.realtime.audio_playback import AudioPlayer
from realtime_ai.realtime_ai_client import RealtimeAIClient, RealtimeAIOptions, RealtimeAIEventHandler, AudioStreamOptions
from realtime_ai.models.realtime_ai_events import *

from typing import Optional
import json, uuid, yaml
from datetime import datetime
import threading, base64


class MyAudioCaptureEventHandler(AudioCaptureEventHandler):
    def __init__(self, client: RealtimeAIClient, event_handler: "MyRealtimeEventHandler"):
        """
        Initializes the event handler.
        
        :param client: Instance of RealtimeClient.
        :param event_handler: Instance of MyRealtimeEventHandler.
        """
        self._client = client
        self._event_handler = event_handler
        self._keyword_detected = False
        self._conversation_active = False
        self._silence_timeout = 10  # Silence timeout in seconds for rearming keyword detection
        self._silence_timer = None

    def send_audio_data(self, audio_data: bytes):
        """
        Sends audio data to the RealtimeClient.

        :param audio_data: Raw audio data in bytes.
        """
        if self._conversation_active:
            logger.debug("Sending audio data to the client.")
            self._client.send_audio(audio_data)

    def on_speech_start(self):
        """
        Handles actions to perform when speech starts.

        """
        logger.info("Local VAD: User speech started")
        logger.info(f"on_speech_start: Keyword detected: {self._keyword_detected}, Conversation active: {self._conversation_active}")

        if self._keyword_detected:
            self._conversation_active = True
            if self._silence_timer:
                self._silence_timer.cancel()

        if (self._client.options.turn_detection is None and
            self._event_handler.is_audio_playing() and
            self._conversation_active):
            logger.info("User started speaking while assistant is responding; interrupting the assistant's response.")
            self._client.clear_input_audio_buffer()
            self._client.cancel_response()
            self._event_handler.audio_player.drain_and_restart()

    def on_speech_end(self):
        """
        Handles actions to perform when speech ends.
        """
        logger.info("Local VAD: User speech ended")
        logger.info(f"on_speech_end: Keyword detected: {self._keyword_detected}, Conversation active: {self._conversation_active}")

        if self._conversation_active and self._client.options.turn_detection is None:
            logger.debug("Using local VAD; requesting the client to generate a response after speech ends.")
            self._client.generate_response()
            logger.debug("Conversation is active. Starting silence timer.")
            self._start_silence_timer()

    def on_keyword_detected(self, result):
        """
        Called when a keyword is detected.

        :param result: The recognition result containing details about the detected keyword.
        """
        logger.info(f"Local Keyword: User keyword detected: {result}")
        self._event_handler.on_keyword_armed(False)
        self._keyword_detected = True
        self._conversation_active = True

    def _start_silence_timer(self):
        if self._silence_timer:
            self._silence_timer.cancel()
        self._silence_timer = threading.Timer(self._silence_timeout, self._reset_keyword_detection)
        self._silence_timer.start()

    def _reset_keyword_detection(self):
        if self._event_handler.is_audio_playing() or self._event_handler.is_function_processing():
            logger.info("Assistant is responding or processing a function. Waiting to reset keyword detection.")
            self._start_silence_timer()
            return

        logger.info("Silence timeout reached. Rearming keyword detection.")
        self._event_handler.on_keyword_armed(True)
        logger.debug("Clearing input audio buffer.")
        self._client.clear_input_audio_buffer()

        self._keyword_detected = False
        self._conversation_active = False


class MyRealtimeEventHandler(RealtimeAIEventHandler):
    def __init__(self, audio_player: AudioPlayer, ai_client: "RealtimeAssistantClient"):
        super().__init__()
        self._audio_player = audio_player
        self._current_item_id = None
        self._current_audio_content_index = None
        self._call_id_to_function_name = {}
        self._lock = threading.Lock()
        self._realtime_client = None
        self._function_processing = False
        self._ai_client = ai_client
        self._run_identifier = None
        self._is_first_message = True
        self._thread_name = None

    @property
    def audio_player(self):
        return self._audio_player

    def get_current_conversation_item_id(self):
        return self._current_item_id
    
    def get_current_audio_content_id(self):
        return self._current_audio_content_index
    
    def is_audio_playing(self):
        return self._audio_player.is_audio_playing()
    
    def is_function_processing(self):
        return self._function_processing
    
    def set_client(self, client: RealtimeAIClient):
        self._realtime_client = client

    def set_thread_name(self, thread_name: str):
        self._thread_name = thread_name

    def on_error(self, event: ErrorEvent):
        logger.error(f"Error occurred: {event.error.message}")

    def on_keyword_armed(self, armed: bool):
        logger.info(f"Keyword detection armed: {armed}")
        if armed is False:
            self._run_identifier = str(uuid.uuid4())
            self._ai_client.callbacks.on_run_start(assistant_name=self._ai_client.name, run_identifier=self._run_identifier, run_start_time=datetime.now(), user_input="Computer, Hello")
            self._realtime_client.send_text("Hello", generate_response=False)
        else:
            self._ai_client.callbacks.on_run_end(assistant_name=self._ai_client.name, run_identifier=self._run_identifier, run_end_time=datetime.now(), thread_name=self._thread_name)

    def on_input_audio_buffer_speech_stopped(self, event: InputAudioBufferSpeechStopped):
        logger.info(f"Server VAD: Speech stopped at {event.audio_end_ms}ms, Item ID: {event.item_id}")

    def on_input_audio_buffer_committed(self, event: InputAudioBufferCommitted):
        logger.debug(f"Audio Buffer Committed: {event.item_id}")

    def on_conversation_item_created(self, event: ConversationItemCreated):
        logger.debug(f"New Conversation Item: {event.item}")

    def on_response_created(self, event: ResponseCreated):
        logger.debug(f"Response Created: {event.response}")

    def on_response_content_part_added(self, event: ResponseContentPartAdded):
        logger.debug(f"New Part Added: {event.part}")

    def on_response_audio_delta(self, event: ResponseAudioDelta):
        logger.debug(f"Received audio delta for Response ID {event.response_id}, Item ID {event.item_id}, Content Index {event.content_index}")
        self._current_item_id = event.item_id
        self._current_audio_content_index = event.content_index
        self.handle_audio_delta(event)

    def on_response_audio_transcript_delta(self, event: ResponseAudioTranscriptDelta):
        logger.info(f"Assistant transcription delta: {event.delta}")
        message : ConversationMessage = ConversationMessage(self._ai_client)
        message.text_message = TextMessage(event.delta)
        self._ai_client.callbacks.on_run_update(
            assistant_name=self._ai_client.name, 
            run_identifier=self._run_identifier, 
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
        self.create_thread_message(message=event.transcript, role="user")

    def on_response_audio_done(self, event: ResponseAudioDone):
        logger.debug(f"Audio done for response ID {event.response_id}, item ID {event.item_id}")

    def on_response_audio_transcript_done(self, event: ResponseAudioTranscriptDone):
        logger.debug(f"Audio transcript done: '{event.transcript}' for response ID {event.response_id}")

    def on_response_content_part_done(self, event: ResponseContentPartDone):
        part_type = event.part.get("type")
        part_text = event.part.get("text", "")
        logger.debug(f"Content part done: '{part_text}' of type '{part_type}' for response ID {event.response_id}")

    def on_response_output_item_done(self, event: ResponseOutputItemDone):
        item_content = event.item.get("content", [])
        if item_content:
            for item in item_content:
                if item.get("type") == "audio":
                    transcript = item.get("transcript")
                    if transcript:
                        logger.info(f"Assistant transcription complete: {transcript}")
                        self.create_thread_message(message=transcript, role="assistant")
                        self._is_first_message = True

    def create_thread_message(self, message: str, role: str):
        if role == "user":
            self._ai_client._conversation_thread_client.create_conversation_thread_message(message=message, thread_name=self._thread_name)
        elif role == "assistant":
            self._ai_client._conversation_thread_client.create_conversation_thread_message(message=message, thread_name=self._thread_name, metadata={"chat_assistant": self._ai_client._name})

        self._ai_client.callbacks.on_run_update(
            assistant_name=self._ai_client.name, 
            run_identifier=self._run_identifier, 
            run_status="in_progress", 
            thread_name=self._thread_name)

    def on_response_done(self, event: ResponseDone):
        logger.debug(f"Assistant's response completed with status '{event.response.get('status')}' and ID '{event.response.get('id')}'")

    def on_session_created(self, event: SessionCreated):
        logger.info(f"Session created: {event.session}")

    def on_session_updated(self, event: SessionUpdated):
        logger.info(f"Session updated: {event.session}")

    def on_input_audio_buffer_speech_started(self, event: InputAudioBufferSpeechStarted):
        logger.info(f"Server VAD: User speech started at {event.audio_start_ms}ms for item ID {event.item_id}")
        if self._realtime_client.options.turn_detection is not None:
            self._realtime_client.clear_input_audio_buffer()
            self._realtime_client.cancel_response()
            self._audio_player.drain_and_restart()

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
            function_output = str(self._assistant_client._handle_function_call(function_name, arguments_str))
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
                self._audio_player.enqueue_audio_data(audio_bytes)
            except base64.binascii.Error as e:
                logger.error(f"Failed to decode audio delta: {e}")
        else:
            logger.warning("Received 'ResponseAudioDelta' event without 'delta' field.")


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

    def _init_realtime_assistant_client(
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
            tools = self._update_tools(assistant_config)
            self._tools = tools if tools else None
            self._load_selected_functions(assistant_config)
            self._assistant_config = assistant_config
            
            options = RealtimeAIOptions(
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
                max_output_tokens=None if not assistant_config.text_completion_config else assistant_config.text_completion_config.max_output_tokens
            )

            self._audio_player = AudioPlayer()
            self._event_handler = MyRealtimeEventHandler(audio_player=self._audio_player, ai_client=self)
            audio_stream_options = AudioStreamOptions(
                sample_rate=24000,
                channels=1,
                bytes_per_sample=2
            )
            self._realtime_ai_client = RealtimeAIClient(options=options, stream_options=audio_stream_options, event_handler=self._event_handler)
            self._event_handler.set_client(self._realtime_ai_client)

            self._audio_capture_event_handler = MyAudioCaptureEventHandler(
                client=self._realtime_ai_client,
                event_handler=self._event_handler
            )

            self._audio_capture = AudioCapture(
                event_handler=self._audio_capture_event_handler, 
                sample_rate=24000,
                channels=1,
                frames_per_buffer=1024,
                buffer_duration_sec=1.0,
                cross_fade_duration_ms=20,
                vad_parameters={
                    "sample_rate": 24000,
                    "chunk_size": 1024,
                    "window_duration": 1.5,
                    "silence_ratio": 1.5,
                    "min_speech_duration": 0.3,
                    "min_silence_duration": 1.0
                },
                enable_wave_capture=False,
                keyword_model_file=assistant_config.realtime_config.keyword_detection_model)
            
            # Update the local configuration using AssistantConfigManager
            # TODO make optional to save the assistant_config in the config manager
            config_manager = AssistantConfigManager.get_instance()
            config_manager.update_config(self._name, assistant_config.to_json())

        except Exception as e:
            logger.error(f"Failed to initialize assistant instance: {e}")
            raise EngineError(f"Failed to initialize assistant instance: {e}")

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
            #max_text_messages = self._assistant_config.text_completion_config.max_text_messages if self._assistant_config.text_completion_config else None
            #conversation = self._conversation_thread_client.retrieve_conversation(thread_name=thread_name, max_text_messages=max_text_messages)
            #for message in reversed(conversation.messages):
            #    if message.text_message:
            #        self._realtime_ai_client.send_text(message.text_message.content, role=message.role)
            if not self._realtime_ai_client.is_running:
                logger.info(f"Starting realtime assistant with name: {self.name}")
                self._realtime_ai_client.start()

            self._start_audio()
            self.callbacks.on_assistant_selected(assistant_name=self.name, thread_name=thread_name)
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
            self._stop_audio()
            self.callbacks.on_assistant_unselected(assistant_name=self.name)
        except Exception as e:
            logger.error(f"Failed to stop realtime assistant: {e}")
            raise EngineError(f"Failed to stop realtime assistant: {e}")

    def connect(
            self,
            timeout: Optional[float] = None
    ) -> None:
        """
        Connects the realtime assistant.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        try:
            self._realtime_ai_client.start()
        except Exception as e:
            logger.error(f"Failed to connect realtime assistant: {e}")
            raise EngineError(f"Failed to connect realtime assistant: {e}")

    def disconnect(
            self,
            timeout: Optional[float] = None
    ) -> None:
        """
        Closes the realtime assistant.

        :param timeout: The HTTP request timeout in seconds.
        :type timeout: Optional[float]

        :return: None
        :rtype: None
        """
        try:
            self._realtime_ai_client.stop()
            self._audio_capture.close()
            self._audio_player.close()
        except Exception as e:
            logger.error(f"Failed to disconnect realtime assistant: {e}")
            raise EngineError(f"Failed to disconnect realtime assistant: {e}")

    def _start_audio(self) -> None:
        """
        Starts the audio capture and playback.

        :return: None
        :rtype: None
        """
        try:
            self._audio_player.start()
            self._audio_capture.start()
        except Exception as e:
            logger.error(f"Failed to start audio: {e}")
            raise EngineError(f"Failed to start audio: {e}")

    def _stop_audio(self) -> None:
        """
        Stops the audio capture and playback.

        :return: None
        :rtype: None
        """
        try:
            self._audio_capture.stop()
            self._audio_player.stop()
        except Exception as e:
            logger.error(f"Failed to stop audio: {e}")
            raise EngineError(f"Failed to stop audio: {e}")

    def generate_response(
            self, 
            thread_name : str
    ) -> None:
        """
        Generates a realtime assistant response using the user's text input in the specified thread.

        :param thread_name: The name of the thread to process.
        :type thread_name: Optional[str]
        """
        # Ensure at least one of thread_name or user_request is provided

        try:
            logger.info(f"Generating response for thread: {thread_name}")
            # self._realtime_ai_client.generate_response()
            #if thread_name:
            #    max_text_messages = self._assistant_config.text_completion_config.max_text_messages if self._assistant_config.text_completion_config else None
            #    conversation = self._conversation_thread_client.retrieve_conversation(thread_name=thread_name, max_text_messages=max_text_messages)
            #    self._parse_conversation_messages(conversation.messages)
            #elif user_request:
            #    self._messages.append({"role": "user", "content": user_request})

        except Exception as e:
            logger.error(f"Error occurred during generating response: {e}")
            raise EngineError(f"Error occurred during generating response: {e}")

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
