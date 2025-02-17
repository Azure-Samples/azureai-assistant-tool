# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

import os
import json
import threading
from typing import List
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtWidgets import QMainWindow, QSplitter, QVBoxLayout, QWidget, QMessageBox, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QFont

from azure.ai.assistant.management.ai_client_factory import AIClientType
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.assistant_client_callbacks import AssistantClientCallbacks
from azure.ai.assistant.management.assistant_config import AssistantType
from azure.ai.assistant.management.attachment import Attachment, AttachmentType
from azure.ai.assistant.management.azure_logic_app_manager import AzureLogicAppManager
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.function_config_manager import FunctionConfigManager
from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.management.message import ConversationMessage
from azure.ai.assistant.management.task import Task, BasicTask, BatchTask, MultiTask
from azure.ai.assistant.management.task_manager import TaskManager
from azure.ai.assistant.management.task_manager_callbacks import TaskManagerCallbacks

from gui.menu import AssistantsMenu, FunctionsMenu, TasksMenu, SettingsMenu, DiagnosticsMenu
from gui.status_bar import ActivityStatus, StatusBar
from gui.assistant_client_manager import AssistantClientManager
from gui.conversation_sidebar import ConversationSidebar
from gui.diagnostic_sidebar import DiagnosticsSidebar
from gui.conversation import ConversationView
from gui.signals import (
    ConversationAppendChunkSignal,
    AppendConversationSignal,
    ConversationViewClear,
    StartProcessingSignal,
    StartStatusAnimationSignal,
    StopProcessingSignal,
    StopStatusAnimationSignal,
    UpdateConversationTitleSignal,
    ErrorSignal,
    ConversationAppendMessageSignal,
    ConversationAppendMessagesSignal,
    ConversationAppendImageSignal
)
from gui.utils import init_system_assistant, get_ai_client


class MainWindow(QMainWindow, AssistantClientCallbacks, TaskManagerCallbacks):

    def __init__(self):
        super().__init__()
        self.status_messages = {
            'ai_client_type': ''
        }
        self.connection_timeout : float = 360.0
        self.use_system_assistant_for_thread_name : bool = False
        self.use_streaming_for_assistant : bool = True
        self.active_ai_client_type = None
        self.in_background = False
        self.initialize_singletons()
        self.initialize_ui()
        QTimer.singleShot(100, lambda: self.deferred_init())

    def initialize_singletons(self):
        self.function_config_manager = FunctionConfigManager.get_instance('config')
        self.assistant_config_manager = AssistantConfigManager.get_instance('config')
        self.task_manager = TaskManager.get_instance(self)
        self.assistant_client_manager = AssistantClientManager.get_instance()

    def deferred_init(self):
        try:
            self.initialize_variables()
            self.set_active_ai_client_type(AIClientType.AZURE_OPEN_AI)
        except Exception as e:
            error_message = f"An error occurred while initializing the application: {e}"
            self.error_signal.error_signal.emit(error_message)
            logger.error(error_message)
        try:
            self.init_system_assistant_settings()
            self.init_system_assistants()
        except Exception as e:
            error_message = f"An error occurred while initializing the system assistants: {e}"
            logger.error(error_message)

    def init_system_assistants(self):
        init_system_assistant(self, "ConversationTitleCreator")
        init_system_assistant(self, "FunctionSpecCreator")
        init_system_assistant(self, "FunctionImplCreator")
        init_system_assistant(self, "TaskRequestsCreator")
        init_system_assistant(self, "InstructionsReviewer")
        init_system_assistant(self, "AzureLogicAppFunctionCreator")

    def initialize_variables(self):
        self.scheduled_task_threads = {}
        self.thread_lock = threading.Lock()
        self.assistants_processing = {}
        self.active_ai_client_type = AIClientType.AZURE_OPEN_AI # default to Azure OpenAI
        self.conversation_thread_clients : dict[AIClientType, ConversationThreadClient] = {}
        for ai_client_type in AIClientType:
            try:
                self.conversation_thread_clients[ai_client_type] = ConversationThreadClient.get_instance(ai_client_type, config_folder='config')
            except Exception as e:
                self.conversation_thread_clients[ai_client_type] = None
                logger.error(f"Error initializing conversation thread client for ai_client_type {ai_client_type.name}: {e}")
        self.executor = ThreadPoolExecutor(max_workers=5)

    def load_system_assistant_settings(self, settings_file_path = "config/system_assistant_settings.json"):
        self.system_assistant_settings = {}
        # ensure folder exists
        if not os.path.exists("config"):
            os.makedirs("config")
        if os.path.exists(settings_file_path):
            with open(settings_file_path, 'r') as file:
                loaded_settings = json.load(file)
                self.system_assistant_settings.update(loaded_settings)

    def init_system_assistant_settings(self):
        self.load_system_assistant_settings()
        self.system_client_type = self.system_assistant_settings.get("ai_client_type", AIClientType.AZURE_OPEN_AI.name)
        self.system_model = self.system_assistant_settings.get("model", "gpt-4-1106-preview")
        self.system_api_version = self.system_assistant_settings.get("api_version", "2024-02-15-preview")

        try:
            resolved_client_type = AIClientType[self.system_client_type]
            self.system_client = get_ai_client(resolved_client_type, self.system_api_version)

            if self.system_client is None:
                raise ValueError(f"Unable to initialize AI client of type {self.system_client_type}. Check your keys or config.")

        except Exception as e:
            logger.error(f"Error initializing system assistant client {self.system_client_type}: {e}")
            raise ValueError(f"Error initializing system assistant client {self.system_client_type}: {e}")

    def initialize_ui(self):
        self.initialize_ui_components()
        self.initialize_signals()
        self.initialize_ui_layout()

    def initialize_ui_components(self):
        # Main window settings
        self.setWindowTitle('Azure AI Assistant Tool')
        self.setGeometry(100, 100, 1300, 800)
        self.conversation_view = ConversationView(self, self)

        # setup sidebars
        self.conversation_sidebar = ConversationSidebar(self)
        self.diagnostics_sidebar = DiagnosticsSidebar(self)

        # setup menus
        self.assistants_menu = AssistantsMenu(self, self.active_ai_client_type)
        self.functions_menu = FunctionsMenu(self)
        self.tasks_menu = TasksMenu(self)
        self.diagnostics_menu = DiagnosticsMenu(self)
        self.settings_menu = SettingsMenu(self)

        # setup status bar
        self.active_client_label = QLabel("")
        self.active_client_label.setFont(QFont("Arial", 11))
        self.status_bar = StatusBar(self)

    def initialize_signals(self):
        # setup signals
        self.append_conversation_signal = AppendConversationSignal()
        self.start_animation_signal = StartStatusAnimationSignal()
        self.stop_animation_signal = StopStatusAnimationSignal()
        self.start_processing_signal = StartProcessingSignal()
        self.stop_processing_signal = StopProcessingSignal()
        self.update_conversation_title_signal = UpdateConversationTitleSignal()
        self.error_signal = ErrorSignal()
        self.conversation_view_clear_signal = ConversationViewClear()
        self.conversation_append_messages_signal = ConversationAppendMessagesSignal()
        self.conversation_append_message_signal = ConversationAppendMessageSignal()
        self.conversation_append_image_signal = ConversationAppendImageSignal()
        self.conversation_append_chunk_signal = ConversationAppendChunkSignal()

        # Connect the signals to slots (methods)
        self.append_conversation_signal.update_signal.connect(self.conversation_view.append_message)
        self.start_animation_signal.start_signal.connect(self.status_bar.start_animation)
        self.stop_animation_signal.stop_signal.connect(self.status_bar.stop_animation)
        self.start_processing_signal.start_signal.connect(self.start_processing_input)
        self.stop_processing_signal.stop_signal.connect(self.stop_processing_input)
        self.update_conversation_title_signal.update_signal.connect(self.conversation_sidebar.threadList.update_item_by_name)
        self.error_signal.error_signal.connect(lambda error_message: QMessageBox.warning(self, "Error", error_message))
        self.conversation_view_clear_signal.update_signal.connect(self.conversation_view.conversationView.clear)
        self.conversation_append_messages_signal.append_signal.connect(self.conversation_view.append_conversation_messages)
        self.conversation_append_message_signal.append_signal.connect(self.conversation_view.append_conversation_message)
        self.conversation_append_image_signal.append_signal.connect(self.conversation_view.append_image)
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

    def set_active_ai_client_type(self, new_client_type : AIClientType):
        # If the active AI client type is not yet initialized, return and set the active AI client type in deferred_init
        if not hasattr(self, 'conversation_thread_clients'):
            return
        
        # Disconnect realtime clients if switching from OPEN_AI_REALTIME or from AZURE_OPEN_AI_REALTIME to other than realtime type
        if self.active_ai_client_type == AIClientType.OPEN_AI_REALTIME or self.active_ai_client_type == AIClientType.AZURE_OPEN_AI_REALTIME:

            # if new client type is the same as the current client type, do nothing
            if new_client_type == self.active_ai_client_type:
                return

            # Disconnect all realtime assistants
            assistant_clients = self.assistant_client_manager.get_all_clients()
            for assistant_client in assistant_clients:
                if self.is_realtime_assistant(assistant_client.name):
                    assistant_client.disconnect()
                    realtime_audio = self.assistant_client_manager.get_audio(assistant_client.name)
                    if realtime_audio:
                        realtime_audio.stop()

            # Stop showing listening keyword and speech animations when switching from OPEN_AI_REALTIME
            self.stop_animation_signal.stop_signal.emit(ActivityStatus.LISTENING_KEYWORD)
            self.stop_animation_signal.stop_signal.emit(ActivityStatus.LISTENING_SPEECH)
            self.stop_animation_signal.stop_signal.emit(ActivityStatus.PROCESSING_USER_INPUT)

        # Save the conversation threads for the current active assistant
        if self.conversation_thread_clients[self.active_ai_client_type] is not None:
            self.conversation_thread_clients[self.active_ai_client_type].save_conversation_threads()

        # Save assistant configurations when switching AI client types 
        self.assistant_config_manager.save_configs()

        self.conversation_view.conversationView.clear()
        self.conversation_sidebar.assistantList.setDisabled(False)

        self.active_ai_client_type = new_client_type
        if self.assistants_menu is not None:
            self.assistants_menu.update_client_type(new_client_type)  # Update the menu for the new client type

        client = get_ai_client(new_client_type)
        if client is None:
            message = f"{new_client_type.name} assistant client not initialized properly, check the API keys"
            self.status_messages['ai_client_type'] = f'<span style="color: red;">{message}</span>'
            self.update_client_label()
            return

        # If it's an AZURE_AI_AGENT, set up Azure Logic App, TODO: move this to Functions menu
        if self.active_ai_client_type == AIClientType.AZURE_AI_AGENT:
            subscription_id = client.scope["subscription_id"]
            resource_group = client.scope["resource_group_name"]
            self.azure_logic_app_manager = AzureLogicAppManager.get_instance(subscription_id, resource_group)

        self.status_messages['ai_client_type'] = ""
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

    def on_cancel_run_button_clicked(self):
        # cancel runs for all assistants in self.assistants_processing
        for assistant_name in self.assistants_processing:
            logger.debug(f"Cancel run for assistant {assistant_name}")
            assistant_client = self.assistant_client_manager.get_client(assistant_name)
            if assistant_client is not None:
                assistant_client.cancel_processing()
        
        # cancel realtime assistants if running
        selected_assistants = self.conversation_sidebar.get_selected_assistants()
        for assistant_name in selected_assistants:
            assistant_client = self.assistant_client_manager.get_client(assistant_name)
            if assistant_client.assistant_config.assistant_type == AssistantType.REALTIME_ASSISTANT.value and assistant_client.is_active_run():
                realtime_audio = self.assistant_client_manager.get_audio(assistant_name)
                # cancel the run for selected realtime assistant by stopping the assistant and starting it again
                assistant_client.stop()
                if realtime_audio:
                    realtime_audio.stop()
                assistant_client.start(self.conversation_sidebar.threadList.get_current_text())
                if realtime_audio:
                    realtime_audio.start()

        # enable assistant list if it is disabled
        self.conversation_sidebar.assistantList.setDisabled(False)
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

    def on_user_input_complete(self, user_input, pasted_image_file_paths=None):
        if pasted_image_file_paths is None:
            pasted_image_file_paths = []

        try:
            assistants = self.conversation_sidebar.get_selected_assistants()
            if not assistants:
                QMessageBox.warning(self, "Error", "Please select an assistant first.")
                return

            sidebar_attachments = self.conversation_sidebar.threadList.get_attachments_for_selected_item() or []

            pasted_image_attachments = []
            for image_path in pasted_image_file_paths:
                attachment_info = {
                    "file_id": None,
                    "file_name": os.path.basename(image_path),
                    "file_path": image_path,
                    "attachment_type": "image_file",
                    "tools": []
                }
                pasted_image_attachments.append(attachment_info)

            all_attachments = sidebar_attachments + pasted_image_attachments

            if not self.is_realtime_assistant(assistants[0]):
                thread_name = self.setup_conversation_thread()
                self.append_conversation_signal.update_signal.emit("user", user_input, "blue")

                # Update the thread title based on the user's input
                if self.use_system_assistant_for_thread_name:
                    updated_thread_name = self.update_conversation_title(user_input, thread_name, False)
                    self.update_conversation_title_signal.update_signal.emit(thread_name, updated_thread_name)
                    thread_name = updated_thread_name

                self.executor.submit(self.process_input, user_input, assistants, thread_name, False, all_attachments)
                self.conversation_view.inputField.clear()
            else:
                thread_name = self.setup_conversation_thread()
                self.append_conversation_signal.update_signal.emit("user", user_input, "blue")
                self.executor.submit(self.process_realtime_text_input, user_input, assistants, thread_name)
                self.conversation_view.inputField.clear()

        except Exception as e:
            error_message = f"An error occurred while processing the user input: {e}"
            self.error_signal.error_signal.emit(error_message)
            logger.error(error_message)

    def handle_assistant_checkbox_toggled(self, assistant_name, is_checked):
        assistant_client = self.assistant_client_manager.get_client(assistant_name)
        realtime_audio = self.assistant_client_manager.get_audio(assistant_name)
        if is_checked:
            if self.is_realtime_assistant(assistant_name):
                threads_client = self.conversation_thread_clients[self.active_ai_client_type]
  
                thread_name = ""
                if self.conversation_sidebar.threadList.count() == 0 or not self.conversation_sidebar.threadList.selectedItems():
                    thread_name = self.conversation_sidebar.create_conversation_thread(threads_client, False, timeout=self.connection_timeout)
                else:
                    if self.conversation_sidebar.threadList.selectedItems():
                        thread_name = self.conversation_sidebar.threadList.get_current_text()
                    else:
                        thread_name = self.conversation_sidebar.threadList.get_last_thread_name()
                self.conversation_sidebar.select_conversation_thread_by_name(thread_name)
                assistant_client.start(thread_name=thread_name)
                if realtime_audio:
                    realtime_audio.start()
        else:
            if self.is_realtime_assistant(assistant_name):
                assistant_client.stop()
                if realtime_audio:
                    realtime_audio.stop()

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

    def process_input(self, user_input, assistants, thread_name, is_scheduled_task, attachments_dicts=None):
        try:
            logger.debug(f"Processing user input: {user_input} with assistants {assistants} for thread {thread_name}")
            thread_client = self.conversation_thread_clients[self.active_ai_client_type]
            thread_id = thread_client.get_config().get_thread_id_by_name(thread_name)

            self.update_attachments_from_ui_to_thread(thread_client, thread_id, attachments_dicts)
            self.create_thread_message(thread_client, user_input, thread_name, attachments_dicts)
            self.update_attachments_to_sidebar_from_thread(thread_client, thread_id)

            updated_conversation = thread_client.retrieve_conversation(thread_name, timeout=self.connection_timeout)
            self.update_conversation_messages(updated_conversation)

            for assistant_name in assistants:
                self.process_assistant_input(assistant_name, thread_name, is_scheduled_task)

        except Exception as e:
            error_message = f"An error occurred while processing the input: {e}"
            self.error_signal.error_signal.emit(error_message)
            self.stop_processing_signal.stop_signal.emit(assistant_name, is_scheduled_task)
            logger.error(error_message)

    def process_realtime_text_input(self, user_input, assistants, thread_name):
        try:
            self.start_animation_signal.start_signal.emit(ActivityStatus.PROCESSING_USER_INPUT)
            thread_client = self.conversation_thread_clients[self.active_ai_client_type]
            self.create_thread_message(thread_client, user_input, thread_name)

            for assistant_name in assistants:
                assistant_client = self.assistant_client_manager.get_client(assistant_name)
                realtime_audio = self.assistant_client_manager.get_audio(assistant_name)
                if realtime_audio:
                    realtime_audio.audio_player.drain_and_restart()
                if assistant_client is not None:
                    assistant_client.generate_response(user_input)

        except Exception as e:
            error_message = f"An error occurred while processing the input: {e}"
            self.error_signal.error_signal.emit(error_message)
            logger.error(error_message)

    def update_attachments_from_ui_to_thread(self, thread_client : ConversationThreadClient, thread_id, attachments_dicts):
        if not attachments_dicts:
            return
        # Synchronize the thread configuration and cloud client for deleted attachments
        existing_thread_attachments = thread_client.get_config().get_attachments_of_thread(thread_id)
        all_attachment_file_ids = [att["file_id"] for att in attachments_dicts]
        attachments_to_remove = [att for att in existing_thread_attachments if att.file_id not in all_attachment_file_ids]
        
        for attachment in attachments_to_remove:
            thread_client.get_config().remove_attachment_from_thread(thread_id, attachment.file_id)          
            # Optionally remove from cloud thread if not an image. 
            # Do not remove images from cloud thread due to issue with OpenAI bug if image is removed.
            if attachment.attachment_type != AttachmentType.IMAGE_FILE:
                thread_client._ai_client.files.delete(file_id=attachment.file_id)

        logger.debug("Attachments synchronized from UI to thread")

    def create_thread_message(self, thread_client : ConversationThreadClient, user_input, thread_name, attachments_dicts = None):
        thread_id = thread_client.get_config().get_thread_id_by_name(thread_name)
        local_thread_attachments = thread_client.get_config().get_attachments_of_thread(thread_id)
        existing_file_ids = {att.file_id for att in local_thread_attachments}
        new_attachments = []
        for att_dict in attachments_dicts if attachments_dicts else []:
            if att_dict["file_id"] not in existing_file_ids:
                new_attachment = Attachment.from_dict(att_dict)
                new_attachments.append(new_attachment)

        cleaned_input = user_input.strip() if user_input else ""
        if not cleaned_input:
            cleaned_input = "…"

        thread_client.create_conversation_thread_message(
            cleaned_input, thread_name, 
            attachments=new_attachments if new_attachments else None,
            timeout=self.connection_timeout
        )

    def update_attachments_to_sidebar_from_thread(self, thread_client : ConversationThreadClient, thread_id):
        # Refresh the attachments in the sidebar
        thread_attachments = thread_client.get_config().get_attachments_of_thread(thread_id)
        attachments_dicts = [attachment.to_dict() for attachment in thread_attachments]
        self.conversation_sidebar.set_attachments_for_selected_thread(attachments_dicts)

    def process_assistant_input(self, assistant_name, thread_name, is_scheduled_task):
        self.start_processing_signal.start_signal.emit(assistant_name, is_scheduled_task)

        assistant_client = self.assistant_client_manager.get_client(assistant_name)
        if assistant_client is not None:
            assistant_client.process_messages(
                thread_name=thread_name, 
                timeout=self.connection_timeout, 
                stream=self.use_streaming_for_assistant
            )

        self.stop_processing_signal.stop_signal.emit(assistant_name, is_scheduled_task)

    def update_conversation_title(self, text, thread_name, is_scheduled_task):
        if not hasattr(self, 'conversation_title_creator'):
            error_message = "Conversation title creator not initialized, check the system assistant settings"
            logger.error(error_message)
            return thread_name
        # Generate a new thread title based on the user's input text
        user_request = thread_name + " " + text
        new_thread_name = self.conversation_title_creator.process_messages(user_request=user_request, stream=False)
        if is_scheduled_task:
            new_thread_name = "Scheduled_" + new_thread_name
        unique_thread_title = self.conversation_thread_clients[self.active_ai_client_type].set_conversation_thread_name(new_thread_name, thread_name)
        return unique_thread_title

    def update_conversation_messages(self, conversation):
        self.conversation_view_clear_signal.update_signal.emit()
        self.conversation_append_messages_signal.append_signal.emit(conversation.messages)

    def is_realtime_assistant(self, assistant_name):
        assistant_client = self.assistant_client_manager.get_client(assistant_name)
        if assistant_client is not None:
            return assistant_client.assistant_config.assistant_type == AssistantType.REALTIME_ASSISTANT.value
        return False

    def is_assistant_selected(self, assistant_name):
        return self.conversation_sidebar.is_assistant_selected(assistant_name)
    
    def has_keyword_detection_model(self, assistant_name):
        assistant_client = self.assistant_client_manager.get_client(assistant_name)
        if assistant_client.assistant_config.realtime_config.keyword_detection_model:
            return True
        return False

    def handle_realtime_run_start(self, assistant_name, run_identifier):
        if self.is_realtime_assistant(assistant_name):
            self.conversation_sidebar.assistantList.setDisabled(True)
            if "keyword" in run_identifier:
                self.stop_animation_signal.stop_signal.emit(ActivityStatus.LISTENING_KEYWORD)
                if self.is_assistant_selected(assistant_name):
                    self.start_animation_signal.start_signal.emit(ActivityStatus.LISTENING_SPEECH)

    def handle_realtime_run_end(self, assistant_name, run_identifier):
        if self.is_realtime_assistant(assistant_name):
            self.conversation_sidebar.assistantList.setDisabled(False)
            if "keyword" in run_identifier:
                self.stop_animation_signal.stop_signal.emit(ActivityStatus.LISTENING_SPEECH)
                if self.is_assistant_selected(assistant_name):
                    self.start_animation_signal.start_signal.emit(ActivityStatus.LISTENING_KEYWORD)
            self.stop_animation_signal.stop_signal.emit(ActivityStatus.PROCESSING_USER_INPUT)

    # Callbacks for AssistantClientCallbacks
    def on_connected(self, assistant_name, assistant_type, thread_name):
        logger.info(f"Assistant connected: {assistant_name}, {assistant_type}, {thread_name}")
        if assistant_type == AssistantType.REALTIME_ASSISTANT.value:
            if self.has_keyword_detection_model(assistant_name) and self.is_assistant_selected(assistant_name):
                logger.info(f"Assistant connected: {assistant_name}, {assistant_type}, {thread_name}, start listening keyword")
                self.stop_animation_signal.stop_signal.emit(ActivityStatus.LISTENING_SPEECH)
                self.start_animation_signal.start_signal.emit(ActivityStatus.LISTENING_KEYWORD)

    def on_disconnected(self, assistant_name, assistant_type):
        logger.info(f"Assistant disconnected: {assistant_name}, {assistant_type}")
        if assistant_type == AssistantType.REALTIME_ASSISTANT.value:
            # stop listening keyword if no realtime assistants that require keyword detection are selected
            selected_assistants = self.conversation_sidebar.get_selected_assistants()
            if not any(self.has_keyword_detection_model(assistant) for assistant in selected_assistants):
                logger.info(f"Assistant disconnected: {assistant_name}, {assistant_type}, stop listening speech and keyword")
                self.stop_animation_signal.stop_signal.emit(ActivityStatus.LISTENING_SPEECH)
                self.stop_animation_signal.stop_signal.emit(ActivityStatus.LISTENING_KEYWORD)
            self.stop_animation_signal.stop_signal.emit(ActivityStatus.PROCESSING_USER_INPUT)
    
    def on_run_start(self, assistant_name, run_identifier, run_start_time, user_input):
        self.diagnostics_sidebar.start_run_signal.start_signal.emit(assistant_name, run_identifier, run_start_time, user_input)
        self.handle_realtime_run_start(assistant_name, run_identifier)

    def on_function_call_processed(self, assistant_name, run_identifier, function_name, arguments, response):
        self.diagnostics_sidebar.function_call_signal.call_signal.emit(
            assistant_name, run_identifier, function_name, arguments, response
        )

    def on_run_update(self, assistant_name, run_identifier, run_status, thread_name, is_first_message = False, message : ConversationMessage = None):
        logger.info(f"Run update for assistant {assistant_name} with run identifier {run_identifier}, status {run_status}, and thread name {thread_name}")

        is_current_thread = self.conversation_thread_clients[self.active_ai_client_type].is_current_conversation_thread(thread_name)
        if not is_current_thread:
            logger.info(f"Run update for assistant {assistant_name} with run identifier {run_identifier} and status {run_status} is not current assistant thread, conversation not updated")
            return

        if run_status == "streaming":
            if message.text_message:
                logger.info(f"Run update for assistant {assistant_name} with run identifier {run_identifier} and status {run_status}, stream chunk update")
                self.conversation_append_chunk_signal.append_signal.emit(assistant_name, message.text_message.content, is_first_message)
            return

        if run_status == "in_progress" and message is not None:
            logger.info(f"Run update for assistant {assistant_name} with run identifier {run_identifier} and status {run_status}, message append update")
            self.conversation_append_message_signal.append_signal.emit(message)
        else:
            logger.info(f"Run update for assistant {assistant_name} with run identifier {run_identifier} and status {run_status}, full conversation update")
            conversation = self.conversation_thread_clients[self.active_ai_client_type].retrieve_conversation(thread_name, timeout=self.connection_timeout)
            if conversation.messages:
                self.update_conversation_messages(conversation)

    def on_run_failed(self, assistant_name, run_identifier, run_end_time, error_code, error_message, thread_name):
        error_string = f"Run failed due to error code: {error_code}, message: {error_message}"
        logger.warning(error_string)
        self.diagnostics_sidebar.end_run_signal.end_signal.emit(assistant_name, run_identifier, run_end_time, error_string)

        self.handle_realtime_run_end(assistant_name, run_identifier)

        # failed state is terminal state, so update all messages in conversation view after the run has ended
        conversation = self.conversation_thread_clients[self.active_ai_client_type].retrieve_conversation(thread_name, timeout=self.connection_timeout)
        self.update_conversation_messages(conversation)

    def on_run_cancelled(self, assistant_name, run_identifier, run_end_time):
        logger.info(f"Run cancelled for assistant {assistant_name} with run identifier {run_identifier}")
        self.diagnostics_sidebar.end_run_signal.end_signal.emit(assistant_name, run_identifier, run_end_time, "Run cancelled")

    def on_run_end(self, assistant_name: str, run_identifier: str, run_end_time: str, thread_name: str):
        logger.info(f"Run end for assistant {assistant_name} with run identifier {run_identifier} and thread name {thread_name}")

        self.handle_realtime_run_end(assistant_name, run_identifier)
        conversation = self.conversation_thread_clients[self.active_ai_client_type].retrieve_conversation(
            thread_name, timeout=self.connection_timeout
        )
        last_assistant_message = conversation.get_last_text_message(assistant_name)
        if last_assistant_message is None:
            logger.error(f"No last message found for assistant '{assistant_name}' in thread '{thread_name}'.")
            self.diagnostics_sidebar.end_run_signal.end_signal.emit(
                assistant_name,
                run_identifier,
                run_end_time,
                "No message found. Possibly a rate-limiting issue."
            )
        else:
            self.diagnostics_sidebar.end_run_signal.end_signal.emit(
                assistant_name,
                run_identifier,
                run_end_time,
                last_assistant_message.content
            )

        # Download any files from conversation at run-end
        assistant_config = self.assistant_config_manager.get_config(assistant_name)
        for message in conversation.messages:
            for file_message in message.file_messages:
                file_path = file_message.retrieve_file(assistant_config.output_folder_path)
                logger.debug(f"File downloaded to {file_path} on run end")

        # Retrieve steps from the active client, parse them, then emit them to the DiagnosticsSidebar when the run ends.
        try:
            # Get run steps from whichever client is active
            steps_data = self.get_run_steps(
                assistant_name=assistant_name,
                run_identifier=run_identifier,
                thread_name=thread_name
            )

            if steps_data:
                # Send them to the DiagnosticsSidebar
                # This will cause the “Steps” tree node + sub-items to appear
                self.diagnostics_sidebar.add_run_steps_signal.steps_signal.emit(run_identifier, steps_data)

        except Exception as e:
            logger.error(f"Could not retrieve steps for run {run_identifier}: {e}")

    def get_run_steps(self, assistant_name: str, run_identifier: str, thread_name: str) -> List[dict]:
        client = self.assistant_client_manager.get_client(assistant_name)

        if not hasattr(client, "get_run_steps"):
            logger.debug(f"Assistant client {assistant_name} does not support run steps retrieval.")
            return []

        raw_steps = client.get_run_steps(thread_name, run_identifier, timeout=self.connection_timeout)

        steps_data = []
        for step_obj in raw_steps:
            tool_calls_list = []

            # If step type == "tool_calls", we pull out the list of calls
            if step_obj.type.lower() == "tool_calls" and hasattr(step_obj, "step_details"):
                step_details_dict = getattr(step_obj, "step_details", {}) or {}
                maybe_tool_calls = step_details_dict.get("tool_calls", [])

                for call in maybe_tool_calls:
                    # Every call at least has "id" and "type"
                    tool_call_entry = {
                        "id":  call.get("id", ""),
                        "type": call.get("type", "")
                    }

                    # Depending on tool-call type, we read different fields
                    call_type = tool_call_entry["type"].lower()
                    if call_type in ("openapi", "function"):
                        function_dict = call.get("function", {})
                        tool_call_entry["function_name"] = function_dict.get("name", "")
                        tool_call_entry["arguments"] = function_dict.get("arguments", "")
                    elif call_type == "azure_ai_search":
                        azure_ai_search_dict = call.get("azure_ai_search", {})
                        tool_call_entry["azure_ai_search_input"] = azure_ai_search_dict.get("input", "")
                        tool_call_entry["azure_ai_search_output"] = azure_ai_search_dict.get("output", "")
                    else:
                        logger.warning(f"Unknown tool call type for run steps: {call_type}, all data not stored: {call}")

                    tool_calls_list.append(tool_call_entry)

            single_step = {
                "id": step_obj.id,
                "status": step_obj.status,
                "tool_calls": tool_calls_list,
            }
            steps_data.append(single_step)

        return steps_data

    def on_run_audio_data(self, assistant_name, run_identifier, audio_data):
        if self.is_realtime_assistant(assistant_name):
            realtime_audio = self.assistant_client_manager.get_audio(assistant_name)
            if realtime_audio:
                realtime_audio.audio_player.enqueue_audio_data(audio_data)
    
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

            if self.use_system_assistant_for_thread_name:
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
            self.assistant_config_manager.save_configs()
            for ai_client_type in AIClientType:
                logger.debug(f"CloseEvent: save_conversation_threads for ai_client_type {ai_client_type.name}")
                if self.conversation_thread_clients[ai_client_type] is not None:
                    self.conversation_thread_clients[ai_client_type].save_conversation_threads()
            
            assistant_clients = self.assistant_client_manager.get_all_clients()
            for assistant_client in assistant_clients:
                if self.is_realtime_assistant(assistant_client.name):
                    assistant_client.disconnect()
                    realtime_audio = self.assistant_client_manager.get_audio(assistant_client.name)
                    if realtime_audio:
                        realtime_audio.stop()

            self.executor.shutdown(wait=True)
            logger.info("Application closed successfully")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while saving the configuration: {e}")
            logger.error(f"Error saving configuration: {e}")
        finally:
            event.accept()
