# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtWidgets import QMessageBox
from gui.status_bar import ActivityStatus
from azure.ai.assistant.management.logger_module import logger
import azure.cognitiveservices.speech as speechsdk
import os


class SpeechInputHandler:
    def __init__(self, main_window, update_signal=None, send_signal=None):
        self.main_window = main_window
        self.update_signal = update_signal
        self.send_signal = send_signal
        self.is_initialized = False
        self.is_listening = False

        speech_key = os.environ.get('SPEECH_KEY')
        speech_region = os.environ.get('SPEECH_REGION')

        if not os.environ.get('SPEECH_KEY'):
            logger.error("No SPEECH_KEY environment variable found.")
            return
        if not os.environ.get('SPEECH_REGION'):
            logger.error("No SPEECH_REGION environment variable found.")
            return

        try:
            self.speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
            self.speech_config.set_property(speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, "1000")
            self.speech_recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_config)
            self.speech_recognizer.recognizing.connect(self.recognizing_cb)
            self.speech_recognizer.recognized.connect(self.recognized_cb)
            self.speech_recognizer.session_stopped.connect(self.stop_cb)
            self.speech_recognizer.canceled.connect(self.stop_cb)

            self.user_input = ""
            self.user_consent_obtained = False
            if self.speech_config:
                self.is_initialized = True
        except Exception as e:
            logger.error("Error initializing speech input handler: {}".format(e))

    def recognizing_cb(self, evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            self.user_input = evt.result.text
            logger.info('Recognizing: {}'.format(evt.result.text))
            # if text is empty, do not send signal
            if evt.result.text.strip() != "" and self.is_listening and self.update_signal:
                self.update_signal.emit(evt.result.text)

    def recognized_cb(self, evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            self.user_input = evt.result.text
            logger.info('Recognized: {}'.format(evt.result.text))
            # if text is empty, do not send signal
            if evt.result.text.strip() != "" and self.is_listening:
                if self.update_signal:
                    self.update_signal.emit(evt.result.text)
                if self.send_signal:
                    self.send_signal.emit(evt.result.text)

    def stop_cb(self, evt):
        logger.info('Closing on {}'.format(evt))

    def start_listening_from_mic(self):
        if not self.is_listening:
            # Check if consent has already been obtained
            if not self.user_consent_obtained:
                # Consent query
                consent_reply = QMessageBox.question(self.main_window, "Microphone Access", "Do you allow the application to access your microphone for speech recognition?",
                                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

                if consent_reply == QMessageBox.Yes:
                    logger.info("User consented to microphone access.")
                    self.user_consent_obtained = True  # Update the consent flag
                else:
                    logger.info("User denied microphone access. Aborting start.")
                    return False  # Exit the method if consent is not given

            # Proceed with starting the microphone listening as consent is given or already obtained
            logger.info("Starting recognition from microphone.")
            if hasattr(self.main_window, 'start_animation_signal'):
                self.main_window.start_animation_signal.start_signal.emit(ActivityStatus.LISTENING)
            self.speech_recognizer.start_continuous_recognition_async().get()
            self.is_listening = True  # Set flag to indicate listening has started
            return True

    def stop_listening_from_mic(self):
        if self.is_listening:
            logger.info("Stopping recognition from microphone.")
            self.is_listening = False  # Reset flag to indicate not listening
            if hasattr(self.main_window, 'stop_animation_signal'):
                self.main_window.stop_animation_signal.stop_signal.emit(ActivityStatus.LISTENING)
            self.speech_recognizer.stop_continuous_recognition_async().get()
