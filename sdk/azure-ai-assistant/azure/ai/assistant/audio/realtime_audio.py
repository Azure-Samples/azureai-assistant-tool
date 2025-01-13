# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.realtime_assistant_client import RealtimeAssistantClient
from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.management.exceptions import EngineError

from azure.ai.assistant.audio.audio_capture import AudioCaptureEventHandler
from azure.ai.assistant.audio.audio_capture import AudioCapture
from azure.ai.assistant.audio.audio_playback import AudioPlayer

from enum import auto, Enum
import threading


class ConversationState(Enum):
    IDLE = auto()
    KEYWORD_DETECTED = auto()
    CONVERSATION_ACTIVE = auto()


class RealtimeAudioCaptureEventHandler(AudioCaptureEventHandler):
    def __init__(self, realtime_client: "RealtimeAssistantClient", audio_player: AudioPlayer):
        """
        Initializes the event handler.
        
        :param client: Instance of RealtimeAssistantClient.
        :type client: RealtimeAssistantClient
        """
        self._client = realtime_client
        self._audio_player = audio_player
        self._state = ConversationState.IDLE
        self._silence_timer = None
        self._audio_capture = None

    def set_capture_client(self, audio_capture: AudioCapture):
        self._audio_capture = audio_capture

    def send_audio_data(self, audio_data: bytes):
        """
        Sends audio data to the RealtimeClient.

        :param audio_data: Raw audio data in bytes.
        """
        if self._state == ConversationState.CONVERSATION_ACTIVE:
            logger.debug("Sending audio data to the client.")
            self._client._realtime_client.send_audio(audio_data)

    def on_speech_start(self):
        """
        Handles actions to perform when speech starts.
        """
        logger.info("Local VAD: User speech started")
        logger.info(f"on_speech_start: Current state: {self._state}")

        if self._state == ConversationState.KEYWORD_DETECTED or self._state == ConversationState.CONVERSATION_ACTIVE:
            self._set_state(ConversationState.CONVERSATION_ACTIVE)
            self._cancel_silence_timer()

        if (self._client._realtime_client.options.turn_detection is None and
            self._audio_player.is_audio_playing() and
            self._state == ConversationState.CONVERSATION_ACTIVE):
            logger.info("User started speaking while assistant is responding; interrupting the assistant's response.")
            self._client._realtime_client.clear_input_audio_buffer()
            self._client._realtime_client.cancel_response()
            self._audio_player.drain_and_restart()

    def on_speech_end(self):
        """
        Handles actions to perform when speech ends.
        """
        logger.info("Local VAD: User speech ended")
        logger.info(f"on_speech_end: Current state: {self._state}")

        if self._state == ConversationState.CONVERSATION_ACTIVE and self._client._realtime_client.options.turn_detection is None:
            logger.debug("Using local VAD; requesting the client to generate a response after speech ends.")
            self._client._realtime_client.generate_response()
            logger.debug("Conversation is active. Starting silence timer.")
            self._start_silence_timer()

    def on_keyword_detected(self, result):
        """
        Called when a keyword is detected.

        :param result: The recognition result containing details about the detected keyword.
        """
        logger.info(f"Local Keyword: User keyword detected: {result}")
        self._on_keyword_armed(False)
        self._set_state(ConversationState.KEYWORD_DETECTED)
        self._start_silence_timer()

    def _start_silence_timer(self):
        self._cancel_silence_timer()
        self._silence_timer = threading.Timer(self._client.assistant_config.realtime_config.keyword_rearm_silence_timeout, self._reset_state_due_to_silence)
        self._silence_timer.start()

    def _cancel_silence_timer(self):
        if self._silence_timer:
            self._silence_timer.cancel()
            self._silence_timer = None

    def _reset_state_due_to_silence(self):
        if self._audio_player.is_audio_playing() or self._client.event_handler.is_function_processing():
            logger.info("Assistant is responding or processing a function. Waiting to reset keyword detection.")
            self._start_silence_timer()
            return

        logger.info("Silence timeout reached. Rearming keyword detection.")
        self._on_keyword_armed(True)
        logger.debug("Clearing input audio buffer.")
        self._client._realtime_client.clear_input_audio_buffer()
        self._set_state(ConversationState.IDLE)

    def _set_state(self, new_state: ConversationState):
        logger.debug(f"Transitioning from {self._state} to {new_state}")
        self._state = new_state
        if new_state != ConversationState.CONVERSATION_ACTIVE:
            self._cancel_silence_timer()

    def _on_keyword_armed(self, armed: bool):
        logger.info(f"Keyword detection armed: {armed}")
        if armed is False:
            if self._audio_capture:
                self._audio_capture.stop_keyword_recognition()
        else:
            if self._audio_capture:
                self._audio_capture.start_keyword_recognition()

        if self._client and self._client.event_handler:
            self._client.event_handler.on_keyword_armed(armed)


class RealtimeAudio:

    def __init__(
            self,
            realtime_client: RealtimeAssistantClient,
    ) -> None:
        """
        Initializes the realtime audio.

        :param realtime_client: The realtime assistant client.
        :type realtime_client: RealtimeAssistantClient

        """
        self._audio_player = None
        self._audio_capture = None
        self._audio_capture_event_handler = None

        self._init_realtime_audio(realtime_client)

    def _init_realtime_audio(
            self,
            realtime_client: RealtimeAssistantClient,
    ) -> None:
        """
        Creates a realtime audio instance.

        :param realtime_client: The realtime assistant client.
        :type realtime_client: RealtimeAssistantClient
        """
        try:
            self._audio_player = AudioPlayer()
            self._audio_capture = None
            self._audio_capture_event_handler = RealtimeAudioCaptureEventHandler(realtime_client=realtime_client, audio_player=self._audio_player)
            
            assistant_config = realtime_client.assistant_config
            if assistant_config.realtime_config.keyword_detection_model:
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
                        "min_silence_duration": 1.0,
                        "model_path": assistant_config.realtime_config.voice_activity_detection_model
                    },
                    enable_wave_capture=False,
                    keyword_model_file=assistant_config.realtime_config.keyword_detection_model)

                self._audio_capture_event_handler.set_capture_client(self._audio_capture)

        except Exception as e:
            logger.error(f"Failed to create realtime client: {e}")
            raise EngineError(f"Failed to create realtime client: {e}")

    def update(
            self,
            assistant_config: AssistantConfig,
    ) -> None:
        """
        Updates the realtime audio instance.

        :param assistant_config: The assistant configuration.
        :type assistant_config: AssistantConfig
        """
        try:
            # Update the audio capture by closing the existing instance and creating a new one
            if self._audio_capture:
                self._audio_capture.close()
                self._audio_capture = None

            if assistant_config.realtime_config.keyword_detection_model:
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

                if self._audio_capture_event_handler:
                    self._audio_capture_event_handler.set_capture_client(self._audio_capture)
                else:
                    raise EngineError("Failed to update realtime client: Audio capture event handler is not initialized.")

        except Exception as e:
            logger.error(f"Failed to update realtime client: {e}")
            raise EngineError(f"Failed to update realtime client: {e}")

    def start(
            self,
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
            self._start_audio()
        except Exception as e:
            logger.error(f"Failed to start realtime assistant: {e}")
            raise EngineError(f"Failed to start realtime assistant: {e}")

    def stop(
            self,
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
        except Exception as e:
            logger.error(f"Failed to stop realtime assistant: {e}")
            raise EngineError(f"Failed to stop realtime assistant: {e}")
        
    def _start_audio(self) -> None:
        """
        Starts the audio capture and playback.

        :return: None
        :rtype: None
        """
        try:
            if self._audio_player:
                self._audio_player.start()
            if self._audio_capture:
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
            if self._audio_capture:
                self._audio_capture.stop()
                self._audio_capture_event_handler._set_state(ConversationState.IDLE)
            if self._audio_player:
                self._audio_player.stop()
        except Exception as e:
            logger.error(f"Failed to stop audio: {e}")
            raise EngineError(f"Failed to stop audio: {e}")

    @property
    def audio_capture(self) -> AudioCapture:
        return self._audio_capture
    
    @property
    def audio_player(self) -> AudioPlayer:
        return self._audio_player