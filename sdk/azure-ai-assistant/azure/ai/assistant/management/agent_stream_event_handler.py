
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.agent_client import AgentClient
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.message import ConversationMessage
from azure.ai.assistant.management.conversation_thread_config import ConversationThreadConfig
from azure.ai.assistant.management.logger_module import logger

from azure.ai.projects.models import AgentEventHandler, SubmitToolOutputsAction, RunStep, ThreadMessage, ThreadRun, MessageDeltaChunk
from datetime import datetime
from typing import Optional, Any


class AgentStreamEventHandler(AgentEventHandler):
    """
    Class to handle the streaming events from the Assistant using the AgentEventHandler interface.
    """

    def __init__(
        self,
        parent: AgentClient,
        thread_id: str,
        is_submit_tool_call: bool = False,
        timeout: Optional[float] = None
    ):
        super().__init__()
        self._parent = parent
        self._name = parent._assistant_config.name
        self._is_first_message = True
        self._is_started = False
        self._is_submit_tool_call = is_submit_tool_call
        self._conversation_thread_client = ConversationThreadClient.get_instance(
            self._parent._ai_client_type
        )
        threads_config: ConversationThreadConfig = (
            self._conversation_thread_client.get_config()
        )
        self._thread_name = threads_config.get_thread_name_by_id(thread_id)
        self._thread_id = thread_id
        self._timeout = timeout

    def on_message_delta(
        self, delta: "MessageDeltaChunk"  # type: ignore[name-defined]
    ) -> None:
        """
        When a portion of a message is streamed back (text delta).
        """
        logger.debug(f"on_message_delta called, delta: {delta}")
        # TODO: Update ConversationMessage
        message = ConversationMessage(self._parent.ai_client, delta)
        if delta.text:
            # Append the delta text to your conversation message, if you wish:
            message.text_message.content += delta.text
        # Fire your "stream update" callback (previously in on_message_delta)
        self._parent._callbacks.on_run_update(
            self._name,
            self.current_run.id,
            "streaming",
            self._thread_name,
            self._is_first_message,
            message=message
        )
        self._is_first_message = False

    def on_thread_message(
        self, message: "ThreadMessage"  # type: ignore[name-defined]
    ) -> None:
        """
        A new message in the conversation (fully created).
        """
        logger.info(f"on_thread_message called, message: {message}")
        # If you used to handle "on_message_created" or "on_message_done",
        # you can fold that logic here. For instance:
        if message.status == "done" or message.status == "completed":
            # This could be your "on_message_done" logic:
            logger.info(f"Message completed with ID: {message.id}")
            # TODO: Update ConversationMessage
            retrieved_msg = ConversationMessage(self._parent.ai_client, message)
            self._parent._callbacks.on_run_update(
                self._name,
                self.current_run.id,
                "completed",
                self._thread_name,
                self._is_first_message,
                message=retrieved_msg
            )
            self._is_first_message = False
        else:
            # Otherwise treat as a "newly created" message
            logger.info(f"Message created with ID: {message.id}")

    def on_thread_run(
        self, run: "ThreadRun"  # type: ignore[name-defined]
    ) -> None:
        """
        A run event has occurred, such as a new run or status change
        (created, failed, requires_action, done, etc.).
        """
        logger.info(f"on_thread_run called, run_id: {run.id}, status: {run.status}")

        if run.status == "queued":
            logger.info(f"ThreadRunCreated, run_id: {run.id}, is_submit_tool_call: {self._is_submit_tool_call}")
            if not self._is_started and not self._is_submit_tool_call:
                conversation = self._conversation_thread_client.retrieve_conversation(self._thread_name)
                user_request = conversation.get_last_text_message("user").content
                self._parent._callbacks.on_run_start(
                    self._name,
                    run.id,
                    str(datetime.now()),
                    user_request
                )
                self._is_started = True

        if run.status == "failed":
            logger.error(f"Run failed, last_error: {run.last_error}")
            if run.last_error:
                self._parent._callbacks.on_run_failed(
                    self._name,
                    self.current_run.id,
                    str(datetime.now()),
                    run.last_error.code if run.last_error.code else "UNKNOWN_ERROR",
                    run.last_error.message if run.last_error.message else "No error message",
                    self._thread_name
                )

        if run.status == "completed":
            # You could also handle the "on_end" logic here if so desired
            logger.info(f"Run completed, run_id: {run.id}, is_submit_tool_call: {self._is_submit_tool_call}")
            if not self._is_submit_tool_call:
                self._parent._callbacks.on_run_end(
                    self._name,
                    run.id,
                    str(datetime.now()),
                    self._thread_name
                )

        # If the run requires action (tool calls)
        if run.status == "requires_action" and isinstance(run.required_action, SubmitToolOutputsAction):
            logger.info(f"Run requires action for tool outputs, run_id: {run.id}")
            # Potentially handle this directly, or call a helper method:
            self._handle_required_tool_outputs(run)

    def _handle_required_tool_outputs(self, run: "ThreadRun") -> None:
        """
        If the run requires us to submit tool outputs, handle it here.
        (Similar logic you had in old 'on_tool_call_done' or 'on_event' checks.)
        """
        if isinstance(run.required_action, SubmitToolOutputsAction):
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            logger.info(f"Handling required tool outputs for run_id: {run.id}")

            # Let your parent figure out how to submit the outputs, or do it here:
            self._parent._handle_required_action(
                self._name,
                self._thread_id,
                run.id,
                tool_calls,
                timeout=self._timeout,
                stream=True
            )

    def on_run_step(
        self, step: "RunStep"  # type: ignore[name-defined]
    ) -> None:
        """
        Handle a RunStep event. This might replace on_tool_call_created / on_message_created, etc.
        """
        logger.info(f"on_run_step called. Type: {step.type}, Status: {step.status}")
        # If you need to handle "tool_call_created" logic:
        if step.type == "function" and step.status == "created":
            logger.info(f"Tool call created: {step}")
            if self.current_run.required_action:
                logger.info(f"run.required_action.type: {self.current_run.required_action.type}")
        # If the step is done (similar to old on_tool_call_done)
        if step.type == "function" and step.status == "done":
            logger.info(f"Tool call done: {step}")
            if self.current_run.required_action:
                logger.info(f"done, run.required_action.type: {self.current_run.required_action.type}")
                if self.current_run.required_action.type == "submit_tool_outputs":
                    tool_calls = self.current_run.required_action.submit_tool_outputs.tool_calls
                    self._parent._handle_required_action(
                        self._name,
                        self._thread_id,
                        self.current_run.id,
                        tool_calls,
                        timeout=self._timeout,
                        stream=True
                    )

    def on_run_step_delta(
        self, delta: "RunStepDeltaChunk"  # type: ignore[name-defined]
    ) -> None:
        """
        Handle run-step deltas (like partial tool call info, partial function name/args, etc.).
        """
        logger.debug(f"on_run_step_delta called, delta: {delta}")
        # If it's a function tool call with partial data:
        if delta.type == "function":
            if delta.function.name:
                logger.debug(f"Function name: {delta.function.name}")
            if delta.function.arguments:
                logger.debug(f"Function arguments: {delta.function.arguments}")
            if delta.function.output:
                logger.debug(f"Function output: {delta.function.output}")
        if self.current_run.required_action:
            logger.debug(f"delta, run.required_action.type: {self.current_run.required_action.type}")

    def on_error(self, data: str) -> None:
        """
        Handle error events from the agent stream.
        """
        logger.error(f"An error occurred in the agent stream. Data: {data}")

    def on_done(self) -> None:
        """
        Called when the stream is fully completed.
        (Equivalent to old `on_end` in prior code.)
        """
        logger.info(f"on_done called, run_id: {self.current_run.id}, is_submit_tool_call: {self._is_submit_tool_call}")
        # If you still want to call on_run_end (and haven't already in on_thread_run),
        # you can do so here. Example:
        if not self._is_submit_tool_call:
            self._parent._callbacks.on_run_end(
                self._name,
                self.current_run.id,
                str(datetime.now()),
                self._thread_name
            )

    def on_unhandled_event(
        self, event_type: str, event_data: Any
    ) -> None:
        """
        Called for any event types that do not map to the known handlers.
        """
        logger.warning(f"Unhandled event. Type: {event_type}, Data: {event_data}")
