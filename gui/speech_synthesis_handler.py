# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import ResultFuture
from openai import OpenAI

import os, time

from azure.ai.assistant.management.logger_module import logger


MAX_SUMMARY_WORDS = 20

example_text = """Sure, here are some general suggestions for what you could do today:
1. Learn something new, like picking up a language or finding out about a topic you're curious about.
2. Take some time for self-care, such as meditating, exercising, or enjoying a hobby.
3. Connect with friends or family, either in person or through a video call.
4. Get outdoors, go for a walk, hike, or visit a park.
5. Organize your space, declutter, or start a home improvement project.
6. Volunteer for a local community service or help out a neighbor.
7. Cook a new recipe or try out a new local restaurant.
8. Plan your upcoming week, set goals, and organize your schedule.
If you let me know your interests or the context (like work, personal development, relaxation), I could provide more tailored suggestions."""

example_summary = """Sure, please see below list of ideas for today, let me know what do you think."""

summary_instructions = [{
    "role": "system", 
    "content": f"You are tasked to create summary of given text used in conversation. The summary must be {MAX_SUMMARY_WORDS} words long at max. "
               f"Treat the given text as your original and written answer and now your task is to summarize your text in a way "
               f"that it sounds like a positive natural answer in a conversation and avoiding any rambling. "
               f"Here is an example of given text you might write as text: {example_text}."
               f"Here is an example of the expected response you would say in conversation for the given text: {example_summary}."
}]


class SpeechSynthesisHandler:
    def __init__(self, 
                 main_window,
                 complete_signal=None
    ):
        self.main_window = main_window
        self.client : OpenAI = main_window.chat_client
        self.model = main_window.chat_completion_model
        self.complete_signal = complete_signal
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
            if self.get_words_count(text) >= MAX_SUMMARY_WORDS and self.main_window.user_text_summarization_in_synthesis:
                logger.info(f"Text is longer than {MAX_SUMMARY_WORDS} words, creating summary of text for speech synthesis.")
                start_time = time.time()
                text = self.get_summary(text)
                stop_time = time.time()
                logger.debug(f"Time taken for text summarization: {stop_time - start_time} seconds")
            start_time = time.time()
            result_future = self.speech_synthesizer.speak_text_async(text)
            stop_time = time.time()
            logger.debug(f"Time taken for async speech synthesis to start: {stop_time - start_time} seconds")
            return result_future
        except Exception as e:
            logger.error(f"Error during speech synthesis: {e}")

    def get_words_count(self, text):
        return len(text.split())
    
    def get_summary(self, text):
        try:
            messages = summary_instructions
            logger.info("Creating summary from the following text: \n" + text)
            request = "Please create a summary from the following text: \n" + text
            messages.append({"role": "user", "content": request})
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            logger.info("get_summary, response: " + response.choices[0].message.content)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error during text summarization: {e}")
            return text
