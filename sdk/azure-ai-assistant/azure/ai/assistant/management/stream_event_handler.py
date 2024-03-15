
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_client import AssistantClient
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.conversation_thread_config import ConversationThreadConfig
from azure.ai.assistant.management.logger_module import logger

from openai import AssistantEventHandler
from datetime import datetime


class StreamEventHandler(AssistantEventHandler):
    def __init__(self, parent : AssistantClient, thread_id, is_submit_tool_call=False):
        super().__init__()
        self._parent = parent
        self._name = parent._assistant_config.name
        self._is_first_message = True
        self._is_started = False
        self._is_submit_tool_call = is_submit_tool_call
        threads_config : ConversationThreadConfig = ConversationThreadClient.get_instance(self._parent._ai_client_type).get_config()
        self._thread_name = threads_config.get_thread_name_by_id(thread_id)
        self._thread_id = thread_id

    def on_exception(self, exception: Exception) -> None:
        logger.info(f"on_exception called, exception: {exception}")

    def on_timeout(self) -> None:
        logger.info(f"on_timeout called")

    def on_end(self) -> None:
        logger.info(f"on_end called, run_id: {self.current_run.id}")
        if self._is_submit_tool_call is False:
            self._parent._callbacks.on_run_update(self._name, self.current_run.id, "completed", self._thread_name)
            self._parent._callbacks.on_run_end(self._name, self.current_run.id, str(datetime.now()), self._thread_name)

    def on_message_created(self, message) -> None:
        logger.info(f"on_message_created called, message: {message}")

    def on_message_delta(self, delta, snapshot) -> None:
        logger.info(f"on_message_delta called, delta: {delta}")

    def on_message_done(self, message) -> None:
        logger.info(f"on_message_done called, message: {message}")

    def on_text_created(self, text) -> None:
        logger.info(f"on_text_created called, text: {text}")
        if self._is_started is False and self._is_submit_tool_call is False:
            self._parent._callbacks.on_run_start(self._name, self.current_run.id, str(datetime.now()), "Processing user input")
            self._is_started = True

    def on_text_delta(self, delta, snapshot):
        logger.info(f"on_text_delta called, delta: {delta}")
        self._parent._callbacks.on_run_update(self._name, self.current_run.id, "streaming", self._thread_name, self._is_first_message, delta.value)
        self._is_first_message = False

    def on_text_done(self, text) -> None:
        logger.info(f"on_text_done called, text: {text}")

    def on_tool_call_created(self, tool_call):
        logger.info(f"on_tool_call_created called, tool_call: {tool_call}")
        if self._is_started is False and self._is_submit_tool_call is False:
            self._parent._callbacks.on_run_start(self._name, self.current_run.id, str(datetime.now()), "Processing user input")
            self._is_started = True
        if self.current_run.required_action:
            logger.info(f"create, run.required_action.type: {self.current_run.required_action.type}")

    def on_tool_call_delta(self, delta, snapshot):
        logger.info(f"on_tool_call_delta called, delta: {delta}")
        if delta.type == 'function':
            if delta.function.name:
                logger.info(f"{delta.function.name}")
            if delta.function.arguments:
                logger.info(f"{delta.function.arguments}")
            if delta.function.output:
                logger.info(f"{delta.function.output}")
        if self.current_run.required_action:
            logger.info(f"delta, run.required_action.type: {self.current_run.required_action.type}")

    def on_tool_call_done(self, tool_call) -> None:
        logger.info(f"on_tool_call_done called, tool_call: {tool_call}")
        if self.current_run.required_action:
            logger.info(f"done, run.required_action.type: {self.current_run.required_action.type}")
            if self.current_run.required_action.type == "submit_tool_outputs":
                tool_calls = self.current_run.required_action.submit_tool_outputs.tool_calls
                self._parent._handle_required_action(self._name, self._thread_id, self.current_run.id, tool_calls, stream=True)