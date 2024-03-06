# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtWidgets import QMainWindow, QSplitter, QVBoxLayout, QWidget, QMessageBox, QHBoxLayout, QApplication
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QFont

import threading
from concurrent.futures import ThreadPoolExecutor
import os, time, json

from azure.ai.assistant.management.ai_client_factory import AIClientFactory, AIClientType
from azure.ai.assistant.management.task_manager import TaskManager
from azure.ai.assistant.management.task import Task, BasicTask, BatchTask, MultiTask
from azure.ai.assistant.management.assistant_client import AssistantClient
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.task_manager_callbacks import TaskManagerCallbacks
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.conversation_title_creator import ConversationTitleCreator
from azure.ai.assistant.management.function_config_manager import FunctionConfigManager
from azure.ai.assistant.management.instructions_checker import InstructionsChecker
from azure.ai.assistant.management.function_creator import FunctionCreator
from azure.ai.assistant.management.task_request_creator import TaskRequestCreator
from azure.ai.assistant.management.logger_module import logger
from gui.menu import AssistantsMenu, FunctionsMenu, GuidelinesMenu, TasksMenu, SettingsMenu, DiagnosticsMenu
from gui.status_bar import ActivityStatus, StatusBar
from gui.speech_input_handler import SpeechInputHandler
from gui.speech_synthesis_handler import SpeechSynthesisHandler
from gui.assistant_client_manager import AssistantClientManager
from gui.conversation_sidebar import ConversationSidebar
from gui.diagnostic_sidebar import DiagnosticsSidebar
from gui.conversation import ConversationView
from gui.signals import ConversationAppendChunkSignal, AppendConversationSignal, ConversationViewClear, StartProcessingSignal, SpeechSynthesisCompleteSignal, StartStatusAnimationSignal, StopProcessingSignal, StopStatusAnimationSignal, UpdateConversationTitleSignal, UserInputSendSignal, UserInputSignal, ErrorSignal, ConversationAppendMessagesSignal


class MainWindow(QMainWindow, AssistantClientCallbacks, TaskManagerCallbacks):

    def __init__(self):
        super().__init__()
        self.status_messages = {
            'ai_client_type': '',
            'chat_completion': '',
        }
        self.connection_timeout : float = 90.0
        self.use_chat_completion_for_thread_name : bool = False
        self.user_text_summarization_in_synthesis : bool = False
        self.in_background = False
        self.initialize_singletons()
        self.initialize_ui()
        QTimer.singleShot(100, lambda: self.deferred_init())

    def initialize_singletons(self):
        self.function_config_manager = FunctionConfigManager.get_instance()
        self.assistant_config_manager = AssistantConfigManager.get_instance()
        self.task_manager = TaskManager.get_instance(self)
        self.assistant_client_manager = AssistantClientManager.get_instance()

    def deferred_init(self):
        try:
            self.initialize_chat_components()
            self.initialize_assistant_components()
            self.set_active_ai_client_type(AIClientType.AZURE_OPEN_AI)
        except Exception as e:
            error_message = f"An error occurred while initializing the application: {e}"
            self.error_signal.error_signal.emit(error_message)
            logger.error(error_message)

    def initialize_chat_components(self):
        try:
            self.init_chat_completion()
            self.conversation_title_creator = ConversationTitleCreator(self.chat_client, self.chat_completion_model)
            self.instructions_checker = InstructionsChecker(self.chat_client, self.chat_completion_model)
            self.function_creator = FunctionCreator(self.chat_client, self.chat_completion_model)
            self.task_request_creator = TaskRequestCreator(self.chat_client, self.chat_completion_model)
            self.speech_synthesis_handler = SpeechSynthesisHandler(self, self.speech_synthesis_complete_signal.complete_signal)
        except Exception as e:
            error_message = f"An error occurred while initializing the chat components: {e}"
            self.error_signal.error_signal.emit(error_message)
            logger.error(error_message)

    def initialize_assistant_components(self):
        self.scheduled_task_threads = {}
        self.thread_lock = threading.Lock()
        self.assistants_processing = {}
        self.active_ai_client_type = AIClientType.AZURE_OPEN_AI # default to Azure OpenAI
        self.conversation_thread_clients : dict[AIClientType, ConversationThreadClient] = {}
        for ai_client_type in AIClientType:
            try:
                self.conversation_thread_clients[ai_client_type] = ConversationThreadClient.get_instance(ai_client_type)
            except Exception as e:
                self.conversation_thread_clients[ai_client_type] = None
                logger.error(f"Error initializing conversation thread client for ai_client_type {ai_client_type.name}: {e}")
        self.executor = ThreadPoolExecutor(max_workers=5)

    def load_chat_completion_settings(self, settings_file_path = "config/chat_completion_settings.json"):
        self.chat_completion_settings = {}
        # ensure folder exists
        if not os.path.exists("config"):
            os.makedirs("config")
        if os.path.exists(settings_file_path):
            with open(settings_file_path, 'r') as file:
                loaded_settings = json.load(file)
                self.chat_completion_settings.update(loaded_settings)

    def init_chat_completion(self):
        self.load_chat_completion_settings()

        ai_client_type = self.chat_completion_settings.get("ai_client_type", AIClientType.AZURE_OPEN_AI.name)
        self.chat_completion_model = self.chat_completion_settings.get("model", "gpt-4-1106-preview")
        api_version = self.chat_completion_settings.get("api_version", "2024-02-15-preview")
        if ai_client_type == AIClientType.AZURE_OPEN_AI.name:
            self.chat_client = AIClientFactory.get_instance().get_client(
                AIClientType.AZURE_OPEN_AI,
                api_version=api_version
            )
        elif ai_client_type == AIClientType.OPEN_AI.name:
            self.chat_client = AIClientFactory.get_instance().get_client(
                AIClientType.OPEN_AI
            )

    def initialize_ui(self):
        self.initialize_ui_components()
        self.initialize_signals()
        self.initialize_ui_layout()
        self.initialize_speech_input()

    def initialize_ui_components(self):
        # Main window settings
        self.setWindowTitle('Azure AI Assistant Tool')
        self.setGeometry(100, 100, 1300, 800)
        self.conversation_view = ConversationView(self, self)

        # setup sidebars
        self.conversation_sidebar = ConversationSidebar(self)
        self.diagnostics_sidebar = DiagnosticsSidebar(self)

        # setup menus
        self.assistants_menu = AssistantsMenu(self)
        self.functions_menu = FunctionsMenu(self)
        self.tasks_menu = TasksMenu(self)
        self.guidelines_menu = GuidelinesMenu(self)
        self.diagnostics_menu = DiagnosticsMenu(self)
        self.settings_menu = SettingsMenu(self)

        # setup status bar
        self.active_client_label = QLabel("")
        self.active_client_label.setFont(QFont("Arial", 11))
        self.status_bar = StatusBar(self)

    def initialize_signals(self):
        # setup signals
        self.append_conversation_signal = AppendConversationSignal()
        self.speech_hypothesis_signal = UserInputSignal()
        self.speech_final_signal = UserInputSendSignal()
        self.speech_synthesis_complete_signal = SpeechSynthesisCompleteSignal()
        self.start_animation_signal = StartStatusAnimationSignal()
        self.stop_animation_signal = StopStatusAnimationSignal()
        self.start_processing_signal = StartProcessingSignal()
        self.stop_processing_signal = StopProcessingSignal()
        self.update_conversation_title_signal = UpdateConversationTitleSignal()
        self.error_signal = ErrorSignal()
        self.conversation_view_clear_signal = ConversationViewClear()
        self.conversation_append_messages_signal = ConversationAppendMessagesSignal()
        self.conversation_append_chunk_signal = ConversationAppendChunkSignal()

        # Connect the signals to slots (methods)
        self.append_conversation_signal.update_signal.connect(self.append_conversation_message)
        self.speech_hypothesis_signal.update_signal.connect(self.on_speech_hypothesis)
        self.speech_final_signal.send_signal.connect(self.on_user_input_complete)
        self.speech_synthesis_complete_signal.complete_signal.connect(self.on_speech_synthesis_complete)
        self.start_animation_signal.start_signal.connect(self.status_bar.start_animation)
        self.stop_animation_signal.stop_signal.connect(self.status_bar.stop_animation)
        self.start_processing_signal.start_signal.connect(self.start_processing_input)
        self.stop_processing_signal.stop_signal.connect(self.stop_processing_input)
        self.update_conversation_title_signal.update_signal.connect(self.conversation_sidebar.threadList.update_item_by_name)
        self.error_signal.error_signal.connect(lambda error_message: QMessageBox.warning(self, "Error", error_message))
        self.conversation_view_clear_signal.update_signal.connect(self.conversation_view.conversationView.clear)
        self.conversation_append_messages_signal.append_signal.connect(self.conversation_view.append_messages)
        self.conversation_append_chunk_signal.append_signal.connect(self.conversation_view.append_message_chunk)

    def initialize_ui_layout(self):
        # Create a splitter for sidebar and main content
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.conversation_sidebar)

        # Create the secondary splitter for the main conversation area and diagnostics sidebar
        secondary_splitter = QSplitter(Qt.Horizontal)

        # Central layout for conversation view and input field
        centralWidget = QWidget()
        layout = QVBoxLayout(centralWidget)
        layout.addWidget(self.conversation_view.conversationView)
        layout.addWidget(self.conversation_view.inputField)

        statusLayout = QHBoxLayout()
        statusLayout.addWidget(self.active_client_label)
        statusLayout.addStretch()  # Add stretch to push processing label to the right
        statusLayout.addWidget(self.status_bar.processingLabel)
        layout.addLayout(statusLayout)

        # Create a container for the central layout
        centralContainer = QWidget()
        centralContainer.setLayout(layout)

        # Add central container and diagnostics sidebar to the secondary splitter
        secondary_splitter.addWidget(centralContainer)
        secondary_splitter.addWidget(self.diagnostics_sidebar)
        
        # Add the secondary splitter to the main splitter
        main_splitter.addWidget(secondary_splitter)

        # left sidebar size is 300/1300 of the main window size, main area size is 1000/1300
        main_splitter.setSizes([300, 1000])
        secondary_splitter.setSizes([950, 350])

        # Set the main splitter as the central widget
        self.setCentralWidget(main_splitter)

    def initialize_speech_input(self):
        try:
            self.speech_input_handler = SpeechInputHandler(self, self.speech_hypothesis_signal.update_signal, self.speech_final_signal.send_signal)
        except ValueError as e:
            QMessageBox.warning(self, "Warning", f"An error occurred while initializing the speech input handler: {e}")
            logger.error(f"Error initializing speech input handler: {e}")

    def set_active_ai_client_type(self, ai_client_type : AIClientType):
        # If the active AI client type is not yet initialized, return and set the active AI client type in deferred_init
        if not hasattr(self, 'active_ai_client_type'):
            return

        # Save the conversation threads for the current active assistant
        if self.conversation_thread_clients[self.active_ai_client_type] is not None:
            self.conversation_thread_clients[self.active_ai_client_type].save_conversation_threads()

        self.conversation_view.conversationView.clear()
        self.active_ai_client_type = ai_client_type
        client = None
        try:
            if self.active_ai_client_type == AIClientType.AZURE_OPEN_AI:
                client = AIClientFactory.get_instance().get_client(
                    AIClientType.AZURE_OPEN_AI
                )
            elif self.active_ai_client_type == AIClientType.OPEN_AI:
                client = AIClientFactory.get_instance().get_client(
                    AIClientType.OPEN_AI
                )
        except Exception as e:
            logger.error(f"Error getting client for active_ai_client_type {self.active_ai_client_type.name}: {e}")

        finally:
            if client is None:
                message = f"{self.active_ai_client_type.name} assistant client not initialized properly, check the API keys"
                self.status_messages['ai_client_type'] = f'<span style="color: red;">{message}</span>'
                self.update_client_label()
            else:
                message = ""
                self.status_messages['ai_client_type'] = message
                self.update_client_label()

    def update_client_label(self):
        if hasattr(self, 'active_client_label'):
            # Initialize an empty list to hold the formatted messages
            formatted_messages = []

            # Iterate over the status messages
            for msg in self.status_messages.values():
                if msg:
                    # Since messages may now contain HTML, we don't need to add extra HTML formatting here
                    formatted_messages.append(msg)

            # Join the formatted messages with a separator. Since we're using HTML, we can use <br> for line breaks or keep the " | " separator.
            label_html = " | ".join(formatted_messages)

            # Set the label's text as HTML
            self.active_client_label.setText(label_html)

    def get_active_ai_client_type(self) -> str:
        return self.active_ai_client_type.name

    def on_cancel_run_button_clicked(self):
        logger.debug("on_cancel_run_button_clicked on main_window")
        # cancel runs for all assistants in self.assistants_processing
        #TODO ensure thread safety
        for assistant_name in self.assistants_processing:
            logger.debug(f"Cancel run for assistant {assistant_name}")
            assistant_client = self.assistant_client_manager.get_client(assistant_name)
            if assistant_client is not None:
                assistant_client.cancel_processing()
        # enable input field if it is disabled
        self.conversation_view.inputField.setReadOnly(False)

    def start_processing_input(self, assistant_name, is_scheduled_task=False):
        # Disable the input field
        self.conversation_view.inputField.setReadOnly(True)
        # Initialize state tracking for the assistant if not already present
        if assistant_name not in self.assistants_processing:
            self.assistants_processing[assistant_name] = {'user_input': False, 'scheduled_task': False}

        # Update the relevant state
        if is_scheduled_task:
            self.assistants_processing[assistant_name]['scheduled_task'] = True
            self.status_bar.start_animation(ActivityStatus.PROCESSING_SCHEDULED_TASK)
        else:
            self.assistants_processing[assistant_name]['user_input'] = True
            self.status_bar.start_animation(ActivityStatus.PROCESSING_USER_INPUT)

    def stop_processing_input(self, assistant_name, is_scheduled_task=False):
        # Re-enable the input field
        self.conversation_view.inputField.setReadOnly(False)
        # Check if the assistant is processing the specific type of task
        if assistant_name in self.assistants_processing:
            if is_scheduled_task and self.assistants_processing[assistant_name]['scheduled_task']:
                self.assistants_processing[assistant_name]['scheduled_task'] = False
                self.status_bar.stop_animation(ActivityStatus.PROCESSING_SCHEDULED_TASK)
            elif not is_scheduled_task and self.assistants_processing[assistant_name]['user_input']:
                self.assistants_processing[assistant_name]['user_input'] = False
                self.status_bar.stop_animation(ActivityStatus.PROCESSING_USER_INPUT)

    def on_speech_hypothesis(self, text):
        self.conversation_view.inputField.setText(text)

    def on_user_input_complete(self, user_input):
        try:
            on_user_input_complete_start = time.time() 
            assistants = self.conversation_sidebar.get_selected_assistants()
            # check if assistants is empty list
            if not assistants:
                QMessageBox.warning(self, "Error", "Please select an assistant first.")
                return
            thread_name = self.setup_conversation_thread()

            # stop listening if mic is on
            if self.conversation_sidebar.is_listening:
                self.speech_input_handler.stop_listening_from_mic()

            # Append user's text with preserved formatting
            self.append_conversation_message("user", user_input, color='blue')

            # Update the thread title based on the user's input
            if self.use_chat_completion_for_thread_name:
                start_time = time.time()
                updated_thread_name = self.update_conversation_title(user_input, thread_name, False)
                end_time = time.time()
                logger.debug(f"Total time taken for updating conversation title: {end_time - start_time} seconds")
                self.update_conversation_title_signal.update_signal.emit(thread_name, updated_thread_name)
                thread_name = updated_thread_name

            # get files from conversation thread list
            file_paths = self.conversation_sidebar.threadList.get_attached_files_for_selected_item()
            # get additional instructions
            additional_instructions = self.conversation_sidebar.threadList.get_instructions_for_selected_item()
            # if additional instructions are empty string, set to None
            if additional_instructions == "":
                additional_instructions = None

            self.executor.submit(self.process_input, user_input, assistants, thread_name, False, file_paths, additional_instructions)
            on_user_input_complete_end = time.time()  # End timing after thread starts
            logger.debug(f"Time taken for entering user input: {on_user_input_complete_end - on_user_input_complete_start} seconds")
            self.conversation_view.inputField.clear()
        except Exception as e:
            error_message = f"An error occurred while processing the user input: {e}"
            self.error_signal.error_signal.emit(error_message)
            logger.error(error_message)

    def append_conversation_message(self, sender, message, color):
        # Append the message to the conversation view
        self.conversation_view.append_message(sender, message, color)

    def setup_conversation_thread(self, is_scheduled_task=False):
        threads_client = self.conversation_thread_clients[self.active_ai_client_type]
        if threads_client is None:
            error_message = f"Conversation thread client not initialized for active_ai_client_type {self.active_ai_client_type.name}, cannot setup conversation thread"
            logger.error(error_message)
            raise ValueError(error_message)
        if is_scheduled_task:
            logger.debug(f"setup_conversation_thread for scheduled task")
            return self.conversation_sidebar.create_conversation_thread(threads_client, is_scheduled_task, timeout=self.connection_timeout)
        else:
            logger.debug(f"setup_conversation_thread for user input")
            if self.conversation_sidebar.threadList.count() == 0 or not self.conversation_sidebar.threadList.selectedItems():
                thread_name = self.conversation_sidebar.create_conversation_thread(threads_client, is_scheduled_task, timeout=self.connection_timeout)
                self.conversation_sidebar.select_conversation_thread_by_name(thread_name)
                return thread_name
            else:
                return self.conversation_sidebar.threadList.get_current_text()

    def process_input(self, user_input, assistants, thread_name, is_scheduled_task, file_paths=None, additional_instructions=None):
        try:
            logger.debug(f"Processing user input: {user_input} with assistants {assistants} for thread {thread_name}")

            # Create message to thread
            self.conversation_thread_clients[self.active_ai_client_type].create_conversation_thread_message(user_input, thread_name, file_paths, additional_instructions, timeout=self.connection_timeout)

            for assistant_name in assistants:
                # Signal the start of processing
                self.start_processing_signal.start_signal.emit(assistant_name, is_scheduled_task)

                # Send the user input to the assistant client
                assistant_client = self.assistant_client_manager.get_client(assistant_name)
                if assistant_client is not None:
                    start_time = time.time()
                    assistant_client.process_messages(thread_name, additional_instructions, timeout=self.connection_timeout)
                    end_time = time.time()
                    logger.debug(f"Total time taken for processing user input: {end_time - start_time} seconds")

                self.stop_processing_signal.stop_signal.emit(assistant_name, is_scheduled_task)

        except Exception as e:
            error_message = f"An error occurred while processing the input: {e}"
            self.error_signal.error_signal.emit(error_message)
            self.stop_processing_signal.stop_signal.emit(assistant_name, is_scheduled_task)
            logger.error(error_message)

    def update_conversation_title(self, text, thread_name, is_scheduled_task):
        if not hasattr(self, 'conversation_title_creator') or self.conversation_title_creator is None:
            error_message = "Conversation title creator not initialized, cannot update conversation title, check the chat completion settings"
            self.error_signal.error_signal.emit(error_message)
            logger.error(error_message)
            return thread_name

        # Generate a new thread title based on the user's input text
        new_thread_name = self.conversation_title_creator.get_thread_title(thread_name + " " + text)
        if is_scheduled_task:
            new_thread_name = "Scheduled_" + new_thread_name
        unique_thread_title = self.conversation_thread_clients[self.active_ai_client_type].set_conversation_thread_name(new_thread_name, thread_name)
        return unique_thread_title

    # Callbacks for ConversationSidebarCallbacks
    def on_listening_started(self):
        logger.debug("on_listening_started on main_window")
        if not self.speech_input_handler.is_initialized:
            QMessageBox.warning(self, "Error", "Speech input is not properly initialized, check the AZURE_AI_SPEECH_KEY and AZURE_AI_SPEECH_REGION environment variables are set correctly.")
            return False
        return self.speech_input_handler.start_listening_from_mic()

    def on_listening_stopped(self):
        logger.debug("on_listening_stopped on main_window")
        self.speech_input_handler.stop_listening_from_mic()

    def on_speech_synthesis_complete(self):
        logger.debug("on_speech_synthesis_complete on main_window")
        if self.conversation_sidebar.is_listening:
            self.speech_input_handler.start_listening_from_mic()

    # Callbacks for ConversationViewCallbacks
    def on_text_input_field_clicked(self):
        logger.debug("on_text_field_clicked on main_window")

    # Callbacks for AssistantManagerCallbacks
    def on_run_start(self, assistant_name, run_identifier, run_start_time, user_input):
        #if self.conversation_sidebar.is_listening and self.in_background:
            # TODO Add notification to the user that the assistant is processing the input
        self.diagnostics_sidebar.start_run_signal.start_signal.emit(assistant_name, run_identifier, run_start_time, user_input)

    def on_function_call_processed(self, assistant_name, run_identifier, function_name, arguments, response):
        self.diagnostics_sidebar.function_call_signal.call_signal.emit(
            assistant_name, run_identifier, function_name, arguments, response
        )

    def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message = False, message=None):
        logger.info(f"Run update for assistant {assistant_name} with run identifier {run_identifier}, status {run_status}, and thread name {thread_name}")

        is_current_thread = self.conversation_thread_clients[self.active_ai_client_type].is_current_conversation_thread(thread_name)
        if not is_current_thread:
            logger.info(f"Run update for assistant {assistant_name} with run identifier {run_identifier} and status {run_status} is not current assistant thread, conversation not updated")
            return

        if run_status == "streaming":
            logger.info(f"Run update for assistant {assistant_name} with run identifier {run_identifier} and status {run_status} is streaming")
            self.conversation_append_chunk_signal.append_signal.emit(assistant_name, message, is_first_message)
            return

        conversation = self.conversation_thread_clients[self.active_ai_client_type].retrieve_conversation(thread_name, timeout=self.connection_timeout)
        if run_status == "in_progress" and conversation.messages:
            logger.info(f"Run update for assistant {assistant_name} with run identifier {run_identifier} and status {run_status} is in progress, conversation updated")
            self.conversation_view_clear_signal.update_signal.emit()
            self.conversation_append_messages_signal.append_signal.emit(conversation.messages)

        elif run_status == "completed" and conversation.messages:
            logger.info(f"Run update for assistant {assistant_name} with run identifier {run_identifier} and status {run_status} is completed, conversation updated")
            self.conversation_view_clear_signal.update_signal.emit()
            self.conversation_append_messages_signal.append_signal.emit(conversation.messages)

            if self.conversation_sidebar.is_listening:
                self.speech_input_handler.start_listening_from_mic()

    def on_run_failed(self, assistant_name, run_identifier, run_end_time, error_code, error_message, thread_name):
        error_string = f"Run failed due to error code: {error_code}, message: {error_message}"
        logger.warning(error_string)
        self.diagnostics_sidebar.end_run_signal.end_signal.emit(assistant_name, run_identifier, run_end_time, error_string)

        # failed state is terminal state, so update all messages in conversation view after the run has ended
        conversation = self.conversation_thread_clients[self.active_ai_client_type].retrieve_conversation(thread_name, timeout=self.connection_timeout)

        self.conversation_view_clear_signal.update_signal.emit()
        self.conversation_append_messages_signal.append_signal.emit(conversation.messages)

    def on_run_cancelled(self, assistant_name, run_identifier, run_end_time):
        logger.info(f"Run cancelled for assistant {assistant_name} with run identifier {run_identifier}")
        self.diagnostics_sidebar.end_run_signal.end_signal.emit(assistant_name, run_identifier, run_end_time, "Run cancelled")

    def on_run_end(self, assistant_name, run_identifier, run_end_time, thread_name):
        logger.info(f"Run end for assistant {assistant_name} with run identifier {run_identifier} and thread name {thread_name}")

        conversation = self.conversation_thread_clients[self.active_ai_client_type].retrieve_conversation(thread_name, timeout=self.connection_timeout)
        last_assistant_message = conversation.get_last_text_message(assistant_name)
        if self.conversation_sidebar.is_listening:
            # microphone needs to be stopped before speech synthesis otherwise synthesis output will be heard by the microphone
            self.speech_input_handler.stop_listening_from_mic()
            logger.debug(f"Start speech synthesis for last assistant message: {last_assistant_message.content}")
            result_future = self.speech_synthesis_handler.synthesize_speech_async(last_assistant_message.content)
            logger.debug(f"Speech synthesis result_future: {result_future}")
            # when synthesis is complete, on_speech_synthesis_complete will be called and listening from microphone will be started again

        self.diagnostics_sidebar.end_run_signal.end_signal.emit(assistant_name, run_identifier, run_end_time, last_assistant_message.content)
        assistant_config = self.assistant_config_manager.get_config(assistant_name)

        # copy files from conversation to output folder at the end of the run
        for message in conversation.messages:
            if message.type == "file":
                file_path = message.retrieve_file(assistant_config.output_folder_path)
                logger.debug(f"File downloaded to {file_path} on run end")

    # Callbacks for TaskManagerCallbacks
    def on_task_started(self, task: Task, schedule_id):
        with self.thread_lock:  # Ensure thread-safe access
            if schedule_id not in self.scheduled_task_threads:
                thread_name = self.setup_conversation_thread(True)
                self.scheduled_task_threads[schedule_id] = thread_name
                logger.info(f"Created thread {thread_name} for scheduled task {task.id}")
            logger.info(f"Task: {task.id} started with assistant {task.assistant_name}")

    def on_task_completed(self, task : Task, schedule_id, result):
        logger.info(f"Task: {task.id} completed with assistant {task.assistant_name} and result {result}")
        self.cleanup_scheduled_thread(schedule_id)

    def on_task_failed(self, task : Task, schedule_id, error):
        logger.info(f"Task: {task.id} failed with assistant {task.assistant_name} and error {error}")
        self.cleanup_scheduled_thread(schedule_id)

    def on_task_execute(self, task: Task, schedule_id):
        if isinstance(task, BasicTask):
            logger.info(f"Executing basic task {task.id} with assistant {task.assistant_name}")
            self.handle_execution(task.user_request, schedule_id, task.assistant_name)
        elif isinstance(task, BatchTask):
            logger.info(f"Executing batch task {task.id} with assistant {task.assistant_name}")
            for request in task.requests:
                    self.handle_execution(request, schedule_id, task.assistant_name)
        elif isinstance(task, MultiTask):
            logger.info(f"Executing multi task {task.id}")
            for request in task.requests:
                assistant = request['assistant']
                task_request = request['task']
                logger.info(f"Executing task for assistant {assistant}")
                self.handle_execution(task_request, schedule_id, assistant)

    def handle_execution(self, user_request, schedule_id, assistant_name):
        with self.thread_lock:
            thread_name = self.scheduled_task_threads.get(schedule_id)
            logger.info(f"Handling execution for scheduled task {schedule_id} with thread {thread_name}")
            # If the thread is selected, append the update to the conversation
            if self.conversation_sidebar.threadList.is_thread_selected(thread_name):
                logger.info(f"Thread {thread_name} is selected, appending update to conversation")
                self.append_conversation_signal.update_signal.emit("user", user_request, 'blue')

            if self.use_chat_completion_for_thread_name:
                updated_thread_name = self.update_conversation_title(user_request, thread_name, True)
                self.update_conversation_title_signal.update_signal.emit(thread_name, updated_thread_name)
                thread_name = updated_thread_name

            self.scheduled_task_threads[schedule_id] = thread_name

            # Process the scheduled task
            assistant_list = [assistant_name]
            self.process_input(user_request, assistant_list, thread_name, True)

    def cleanup_scheduled_thread(self, schedule_id):
        with self.thread_lock:  # Ensure thread-safe access
            if schedule_id in self.scheduled_task_threads:
                del self.scheduled_task_threads[schedule_id]

    def _is_thread_name_in_scheduled_tasks(self, thread_name):
        return thread_name in self.scheduled_task_threads.values()

    # PySide6 overrides, UI events

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange:
            if self.isActiveWindow():
                self.in_background = False
            else:
                self.in_background = True

    def closeEvent(self, event):
        try:
            # Stop microphone listening if it's on
            if hasattr(self, 'speech_input_handler') and self.speech_input_handler is not None:
                self.speech_input_handler.stop_listening_from_mic()
            self.assistant_config_manager.save_configs()
            for ai_client_type in AIClientType:
                logger.debug(f"CloseEvent: save_conversation_threads for ai_client_type {ai_client_type.name}")
                if self.conversation_thread_clients[ai_client_type] is not None:
                    self.conversation_thread_clients[ai_client_type].save_conversation_threads()
            self.executor.shutdown(wait=True)
            logger.info("Application closed successfully")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while saving the configuration: {e}")
            logger.error(f"Error saving configuration: {e}")
        finally:
            event.accept()
