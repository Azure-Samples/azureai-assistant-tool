# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import azure.cognitiveservices.speech as speechsdk
from azure.ai.assistant.management.logger_module import logger
import os


class SpeechSynthesisHandler:
    def __init__(self):
        self.is_initialized = False
        speech_key = os.environ.get('SPEECH_KEY')
        speech_region = os.environ.get('SPEECH_REGION')

        if not speech_key or not speech_region:
            logger.error("SPEECH_KEY or SPEECH_REGION environment variables not found.")
            return

        try:
            self.speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
            self.speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"
            self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config)
            self.is_initialized = True
        except Exception as e:
            logger.error(f"Error initializing speech synthesis handler: {e}")

    def synthesize_speech(self, text):
        if not self.is_initialized:
            logger.error("SpeechSynthesisHandler is not initialized properly.")
            return

        try:
            # Synthesizing the received text
            result = self.speech_synthesizer.speak_text_async(text).get()

            # Checking the result
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info("Speech synthesis completed successfully.")
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                logger.error(f"Speech synthesis canceled: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    logger.error(f"Error details: {cancellation_details.error_details}")
        except Exception as e:
            logger.error(f"Error during speech synthesis: {e}")
