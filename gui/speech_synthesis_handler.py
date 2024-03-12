# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import ResultFuture

import os, time

from azure.ai.assistant.management.logger_module import logger


class SpeechSynthesisHandler:
    def __init__(self, 
                 main_window,
                 complete_signal=None
    ):
        self.main_window = main_window
        self.complete_signal = complete_signal
        self.is_initialized = False
        speech_key = os.environ.get('AZURE_AI_SPEECH_KEY')
        speech_region = os.environ.get('AZURE_AI_SPEECH_REGION')

        if not speech_key or not speech_region:
            logger.error("AZURE_AI_SPEECH_KEY or AZURE_AI_SPEECH_REGION environment variables not found.")
            return

        try:
            self.speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
            self.speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"
            self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config)
            self.speech_synthesizer.synthesis_completed.connect(self.synthesis_completed_cb)
            self.is_initialized = True
        except Exception as e:
            logger.error(f"Error initializing speech synthesis handler: {e}")

    def synthesis_completed_cb(self, evt):
        if evt.result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            logger.info("Speech synthesis completed successfully.")
        elif evt.result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = evt.result.cancellation_details
            logger.error(f"Speech synthesis canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                logger.error(f"Error details: {cancellation_details.error_details}")
        if self.complete_signal:
            self.complete_signal.emit()

    def synthesize_speech_async(self, text) -> ResultFuture:
        if not self.is_initialized:
            logger.error("SpeechSynthesisHandler is not initialized properly.")
            return

        try:
            start_time = time.time()
            result_future = self.speech_synthesizer.speak_text_async(text)
            stop_time = time.time()
            logger.debug(f"Time taken for async speech synthesis to start: {stop_time - start_time} seconds")
            return result_future
        except Exception as e:
            logger.error(f"Error during speech synthesis: {e}")