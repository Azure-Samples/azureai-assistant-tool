# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.agent_client import AgentClient
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.message import ConversationMessage
from azure.ai.assistant.management.conversation_thread_config import ConversationThreadConfig
from azure.ai.assistant.management.logger_module import logger

from azure.ai.projects.models import (
    AgentEventHandler,
    SubmitToolOutputsAction,
    RunStep,
    ThreadMessage,
    ThreadRun,
    MessageDeltaChunk,
    RunStepDeltaChunk,
)
from datetime import datetime
from typing import Optional, Any


class AgentStreamEventHandler(AgentEventHandler):
    """
    Handles the streaming events from the Assistant (such as message deltas, 
    tool calls, and run status updates), bridging them into the local logic
    of an AgentClient instance.
    """

    def __init__(
        self,
        parent: AgentClient,
        thread_id: str,
        timeout: Optional[float] = None
    ):
        """
        Initializes the event handler for streaming-based interactions.

        :param parent: The AgentClient instance that owns this event handler.
        :param thread_id: The ID for the thread being processed.
        :param is_submit_tool_call: True if these events are part of a tool call submission.
        :param timeout: A timeout for API calls, if applicable.
        """
        super().__init__()
        self._parent = parent
        self._name = parent.assistant_config.name
        self._first_message = True
        self._run_id = None
        self._started = False
        self._conversation_thread_client = ConversationThreadClient.get_instance(
            self._parent._ai_client_type
        )
        threads_config: ConversationThreadConfig = self._conversation_thread_client.get_config()
        self._thread_name = threads_config.get_thread_name_by_id(thread_id)
        self._thread_id = thread_id
        self._timeout = timeout

    def on_message_delta(
        self, delta: MessageDeltaChunk
    ) -> None:
        """
        Called when a portion of a message is streamed back (text delta).
        Typically used to show partial/streamed response content to the user.
        """
        logger.debug(f"on_message_delta called, delta: {delta}")
        # Create or update a ConversationMessage with the streamed content.
        message = ConversationMessage(self._parent.ai_client, delta)
        if delta.text:
            message.text_message.content += delta.text

        # Fire a run update callback, passing the message so the UI or logs can be updated.
        self._parent._callbacks.on_run_update(
            self._name,
            self._run_id,
            "streaming",
            self._thread_name,
            self._first_message,
            message=message
        )
        self._first_message = False

    def on_thread_message(
        self, message: ThreadMessage
    ) -> None:
        """
        Called when a new message is added to the conversation thread.
        This may also be called when a message completes (status done/completed).
        """
        logger.info(f"on_thread_message called, message.id: {message.id}, status: {message.status}")

        if message.status in ["done", "completed"]:
            # A completed message event. If you track final responses, handle here.
            logger.info(f"Message completed with ID: {message.id}")
            retrieved_msg = ConversationMessage(self._parent.ai_client, message)
            self._parent._callbacks.on_run_update(
                self._name,
                self._run_id,
                "completed",
                self._thread_name,
                self._first_message,
                message=retrieved_msg
            )
            self._first_message = False
        else:
            # Otherwise, it's a newly created or in-progress message.
            logger.info(f"New thread message created with ID: {message.id}")

    def on_thread_run(
        self, run: ThreadRun
    ) -> None:
        """
        Called when any run-level event occurs, such as run creation, failure, or completion.
        """
        logger.info(f"on_thread_run called, run_id: {run.id}, status: {run.status}")
        self._run_id = run.id

        if run.status and not self._started:
            logger.info(f"Run started, run_id: {run.id}")
            conversation = self._conversation_thread_client.retrieve_conversation(self._thread_name)
            user_request = conversation.get_last_text_message("user").content
            self._parent._callbacks.on_run_start(self._name, run.id, str(datetime.now()), user_request)
            self._started = True

        elif run.status == "failed":
            logger.error(f"Run failed, run_id: {run.id}, error: {run.last_error}")
            if run.last_error:
                self._parent._callbacks.on_run_failed(
                    self._name,
                    run.id,
                    str(datetime.now()),
                    run.last_error.code if run.last_error.code else "UNKNOWN_ERROR",
                    run.last_error.message if run.last_error.message else "No error message",
                    self._thread_name
                )

        elif run.status == "completed":
            logger.info(f"Run completed, run_id: {run.id}")
            self._parent._callbacks.on_run_end(
                self._name,
                run.id,
                str(datetime.now()),
                self._thread_name
            )

        elif run.status == "requires_action" and isinstance(run.required_action, SubmitToolOutputsAction):
            logger.info(f"Run requires submitting tool outputs, run_id: {run.id}")
            self._handle_required_action(run)

        else:
            logger.debug(f"Unhandled run status: {run.status}")

    def _handle_required_action(self, run: ThreadRun) -> None:
        """
        If the run requires us to submit tool outputs, this method triggers the agent client
        to gather and submit data for any outstanding tool calls.
        """
        if isinstance(run.required_action, SubmitToolOutputsAction):
            tool_calls = run.required_action.submit_tool_outputs.tool_calls

            if not tool_calls:
                logger.error(f"Run requires tool outputs but no tool calls provided. Cancelling run: {run.id}")
                self._parent._ai_client.agents.cancel_run(thread_id=self._thread_id, run_id=run.id, timeout=self._timeout)
                return

            logger.info(f"Handling required action for run_id: {run.id}")
            tool_outputs = self._parent._process_tool_calls(self._name, self._run_id, tool_calls)

            if not tool_outputs:
                logger.warning(f"No tool outputs were generated for run_id: {run.id}")
                return

            logger.info("Submitting tool outputs with stream")
            self._parent._ai_client.agents.submit_tool_outputs_to_stream(
                thread_id=self._thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs,
                event_handler=self,
            )
    
    def on_run_step(
        self, step: RunStep
    ) -> None:
        """
        Called for each run step (e.g., creation/use of tools or partial status updates).
        """
        logger.info(f"on_run_step called. Type: {step.type}, Status: {step.status}")
        if step.type == "tool_calls":
            logger.info(f"Tool call step: {step}")
        elif step.type == "message_creation":
            logger.info(f"Message creation step: {step}")

    def on_run_step_delta(
        self, delta: RunStepDeltaChunk
    ) -> None:
        """
        Called for incremental updates within a run step, such as partial function arguments.
        """
        logger.debug(f"on_run_step_delta called, delta: {delta}")

    def on_error(
        self, data: str
    ) -> None:
        """
        Called if an internal error or exception occurs on the agent stream.
        """
        logger.error(f"An error occurred in the agent stream. Data: {data}")

    def on_done(self) -> None:
        """
        Called when the agent stream is fully completed (no more events are expected).
        """
        logger.info(f"on_done called, run_id: {self._run_id}")
        self._parent._callbacks.on_run_end(
            self._name,
            self._run_id,
            str(datetime.now()),
            self._thread_name
        )

    def on_unhandled_event(
        self, event_type: str, event_data: Any
    ) -> None:
        """
        Called if a raw event arrives that doesn't match known event types.
        """
        logger.warning(f"Unhandled event. Type: {event_type}, Data: {event_data}")
