# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.


class AssistantClientCallbacks:

    def on_connected(self, assistant_name, assistant_type, thread_name):
        """Callback for when an assistant is connected.
        
        :param assistant_name: The name of the assistant.
        :type assistant_name: str
        :param assistant_type: The type of the assistant.
        :type assistant_type: str
        :param thread_name: The name of the thread.
        :type thread_name: str

        :return: None
        :rtype: None
        """
        pass

    def on_disconnected(self, assistant_name, assistant_type):
        """Callback for when an assistant is disconnected.
        
        :param assistant_name: The name of the assistant.
        :type assistant_name: str
        :param assistant_type: The type of the assistant.
        :type assistant_type: str

        :return: None
        :rtype: None
        """
        pass

    def on_run_start(self, assistant_name, run_identifier, run_start_time, user_input):
        """Callback for when a run starts.
        
        :param assistant_name: The name of the assistant.
        :type assistant_name: str
        :param run_identifier: The identifier for the run.
        :type run_identifier: str
        :param run_start_time: The start time of the run.
        :type run_start_time: datetime
        :param user_input: The user input.
        :type user_input: str

        :return: None
        :rtype: None
        """
        pass

    def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message=False, message=None):
        """Callback for when a run updates.
        
        :param assistant_name: The name of the assistant.
        :type assistant_name: str
        :param run_identifier: The identifier for the run.
        :type run_identifier: str
        :param run_status: The status of the run.
        :type run_status: str
        :param thread_name: The name of the thread.
        :type thread_name: str
        :param is_first_message: Whether the message is the first message, defaults to False, used when status is "streaming"
        :type is_first_message: bool, optional
        :param message: Can be partial message (streaming text content) or full message with files, citations (completed), defaults to None
        :type message: Any, optional

        :return: None
        :rtype: None
        """
        pass

    def on_function_call_processed(self, assistant_name, run_identifier, function_name, arguments, response):
        """Callback for when a function call is processed.
        
        :param assistant_name: The name of the assistant.
        :type assistant_name: str
        :param run_identifier: The identifier for the run.
        :type run_identifier: str
        :param function_name: The name of the function.
        :type function_name: str
        :param arguments: The arguments for the function.
        :type arguments: str
        :param response: The response from the function.
        :type response: str

        :return: None
        :rtype: None
        """
        pass

    def on_run_failed(self, assistant_name, run_identifier, run_end_time, error_code, error_message, thread_name):
        """Callback for when a run fails.
        
        :param assistant_name: The name of the assistant.
        :type assistant_name: str
        :param run_identifier: The identifier for the run.
        :type run_identifier: str
        :param run_end_time: The end time of the run.
        :type run_end_time: datetime
        :param error_code: The error code.
        :type error_code: str
        :param error_message: The error message.
        :type error_message: str
        :param thread_name: The name of the thread.
        :type thread_name: str

        :return: None
        :rtype: None
        """
        pass

    def on_run_cancelled(self, assistant_name, run_identifier, run_end_time, thread_name):
        """Callback for when a run is cancelled.
        
        :param assistant_name: The name of the assistant.
        :type assistant_name: str
        :param run_identifier: The identifier for the run.
        :type run_identifier: str
        :param run_end_time: The end time of the run.
        :type run_end_time: datetime
        :param thread_name: The name of the thread.
        :type thread_name: str

        :return: None
        :rtype: None
        """
        pass

    def on_run_end(self, assistant_name, run_identifier, run_end_time, thread_name, response=None):
        """Callback for when a run completes.
        
        :param assistant_name: The name of the assistant.
        :type assistant_name: str
        :param run_identifier: The identifier for the run.
        :type run_identifier: str
        :param run_end_time: The end time of the run.
        :type run_end_time: datetime
        :param thread_name: The name of the thread.
        :type thread_name: str
        :param response: The response to the user request, if applicable.
        :type response: str, optional

        :return: None
        :rtype: None
        """
        pass

    def on_run_audio_data(self, assistant_name, run_identifier, audio_data: bytes):
        """Callback for when audio data is received.
        
        :param assistant_name: The name of the assistant.
        :type assistant_name: str
        :param run_identifier: The identifier for the run.
        :type run_identifier: str
        :param audio_data: The audio data.
        :type audio_data: bytes

        :return: None
        :rtype: None
        """
        pass
