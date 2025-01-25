
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.async_assistant_client import AsyncAssistantClient
from azure.ai.assistant.management.async_conversation_thread_client import AsyncConversationThreadClient
from azure.ai.assistant.management.async_message import AsyncConversationMessage
from azure.ai.assistant.management.conversation_thread_config import ConversationThreadConfig
from azure.ai.assistant.management.logger_module import logger

from openai import AsyncAssistantEventHandler
from openai.types.beta.threads import TextDeltaBlock
from openai.types.beta import AssistantStreamEvent
from openai.types.beta.assistant_stream_event import ThreadRunFailed, ThreadRunCreated
from datetime import datetime
from typing import Optional
from typing_extensions import override


class AsyncStreamEventHandler(AsyncAssistantEventHandler):
    """
    Class to handle the streaming events from the Assistant.

    :param parent: The parent AssistantClient instance.
    :type parent: AssistantClient
    :param thread_id: The ID of the conversation thread.
    :type thread_id: str
    :param is_submit_tool_call: Whether the event handler is for a submit tool call.
    :type is_submit_tool_call: bool
    :param timeout: The timeout for the event handler.
    :type timeout: float
    """
    def __init__(
            self, 
            parent : AsyncAssistantClient, 
            thread_id, 
            is_submit_tool_call=False, 
            timeout : Optional[float] = None
    ):
        super().__init__()
        self._parent = parent
        self._name = parent._assistant_config.name
        self._is_first_message = True
        self._is_started = False
        self._is_submit_tool_call = is_submit_tool_call
        self._conversation_thread_client = AsyncConversationThreadClient.get_instance(self._parent._ai_client_type)
        threads_config : ConversationThreadConfig = self._conversation_thread_client.get_config()
        self._thread_name = threads_config.get_thread_name_by_id(thread_id)
        self._thread_id = thread_id
        self._timeout = timeout

    @override
    async def on_exception(self, exception: Exception) -> None:
        logger.debug(f"on_exception called, exception: {exception}")

    @override
    async def on_timeout(self) -> None:
        logger.debug(f"on_timeout called")

    @override
    async def on_event(self, event : AssistantStreamEvent) -> None:
        logger.debug(f"on_event called, event: {event}")
        if isinstance(event, ThreadRunFailed):
            if event.data.last_error:
                logger.error(f"last_error: {event.data.last_error.message}")
                await self._parent._callbacks.on_run_failed(self._name, self.current_run.id, str(datetime.now()), event.data.last_error.code, event.data.last_error.message, self._thread_name)
        if isinstance(event, ThreadRunCreated):
            logger.info(f"ThreadRunCreated, run_id: {event.data.id}, is_submit_tool_call: {self._is_submit_tool_call}")
            if self._is_started is False and self._is_submit_tool_call is False:
                conversation = await self._conversation_thread_client.retrieve_conversation(self._thread_name)
                user_request = conversation.get_last_text_message("user").content
                await self._parent._callbacks.on_run_start(self._name, event.data.id, str(datetime.now()), user_request)
                self._is_started = True

    @override
    async def on_end(self) -> None:
        logger.info(f"on_end called, run_id: {self.current_run.id}, is_submit_tool_call: {self._is_submit_tool_call}")
        if self._is_submit_tool_call is False:
            await self._parent._callbacks.on_run_end(self._name, self.current_run.id, str(datetime.now()), self._thread_name)

    @override
    async def on_message_created(self, message) -> None:
        logger.info(f"on_message_created called, message: {message}")

    @override
    async def on_message_delta(self, delta, snapshot) -> None:
        logger.debug(f"on_message_delta called, delta: {delta}")
        message = await AsyncConversationMessage().create(self._parent.ai_client, snapshot)
        if delta.content:
            for content_block in delta.content:
                if isinstance(content_block, TextDeltaBlock) and content_block.text:
                    message.text_message.content = content_block.text.value
        await self._parent._callbacks.on_run_update(self._name, self.current_run.id, "streaming", self._thread_name, self._is_first_message, message=message)
        self._is_first_message = False

    @override
    async def on_message_done(self, message) -> None:
        logger.info(f"on_message_done called, message: {message}")
        message = await AsyncConversationMessage().create(self._parent.ai_client, message)
        await self._parent._callbacks.on_run_update(self._name, self.current_run.id, "completed", self._thread_name, self._is_first_message, message=message)
        self._is_first_message = False

    @override
    async def on_text_created(self, text) -> None:
        logger.info(f"on_text_created called, text: {text}")

    @override
    async def on_text_delta(self, delta, snapshot):
        logger.debug(f"on_text_delta called, delta: {delta}")

    @override
    async def on_text_done(self, text) -> None:
        logger.info(f"on_text_done called, text: {text}")

    @override
    async def on_tool_call_created(self, tool_call):
        logger.info(f"on_tool_call_created called, tool_call: {tool_call}")
        if self.current_run.required_action:
            logger.info(f"create, run.required_action.type: {self.current_run.required_action.type}")

    @override
    async def on_tool_call_delta(self, delta, snapshot):
        logger.debug(f"on_tool_call_delta called, delta: {delta}")
        if delta.type == 'function':
            if delta.function.name:
                logger.debug(f"{delta.function.name}")
            if delta.function.arguments:
                logger.debug(f"{delta.function.arguments}")
            if delta.function.output:
                logger.debug(f"{delta.function.output}")
        if self.current_run.required_action:
            logger.debug(f"delta, run.required_action.type: {self.current_run.required_action.type}")

    @override
    async def on_tool_call_done(self, tool_call) -> None:
        logger.info(f"on_tool_call_done called, tool_call: {tool_call}")
        if self.current_run.required_action:
            logger.info(f"done, run.required_action.type: {self.current_run.required_action.type}")
            if self.current_run.required_action.type == "submit_tool_outputs":
                tool_calls = self.current_run.required_action.submit_tool_outputs.tool_calls
                await self._parent._handle_required_action(self._name, self._thread_id, self.current_run.id, tool_calls, timeout=self._timeout, stream=True)