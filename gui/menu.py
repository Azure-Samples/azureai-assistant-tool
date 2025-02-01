# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtWidgets import QDialog, QMessageBox
from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QAction

from azure.ai.assistant.management.assistant_config import AssistantType
from azure.ai.assistant.management.ai_client_type import AIClientType
from azure.ai.assistant.management.function_config_manager import FunctionConfigManager
from azure.ai.assistant.management.logger_module import add_broadcaster_to_logger
from gui.debug_dialog import DebugViewDialog
from gui.assistant_dialogs import ExportAssistantDialog
from gui.function_dialogs import CreateFunctionDialog, FunctionErrorsDialog
from gui.task_dialogs import CreateTaskDialog, ScheduleTaskDialog
from gui.settings_dialogs import ClientSettingsDialog, GeneralSettingsDialog
from gui.assistant_client_manager import AssistantClientManager
from gui.log_broadcaster import LogBroadcaster
from gui.assistant_gui_workers import open_assistant_config_dialog, ProcessAssistantWorker


class AssistantsMenu:
    def __init__(self, main_window, client_type):
        self.main_window = main_window
        self.client_type = client_type
        self.assistants_menu = self.main_window.menuBar().addMenu("&Assistants")
        self.function_config_manager = FunctionConfigManager.get_instance()
        self.assistant_client_manager = AssistantClientManager.get_instance()
        self.create_assistants_menu()

    def create_assistants_menu(self):
        self.assistants_menu.clear()  # Clear existing menu actions
        if self.client_type == AIClientType.OPEN_AI_REALTIME or self.client_type == AIClientType.AZURE_OPEN_AI_REALTIME:
            createRealtimeAssistantAction = QAction('Create New / Edit Realtime Assistant', self.main_window)
            createRealtimeAssistantAction.triggered.connect(self.create_new_edit_realtime_assistant)
            self.assistants_menu.addAction(createRealtimeAssistantAction)
        elif self.client_type == AIClientType.OPEN_AI or self.client_type == AIClientType.AZURE_OPEN_AI:
            createAssistantAction = QAction('Create New / Edit OpenAI Assistant', self.main_window)
            createAssistantAction.triggered.connect(self.create_new_edit_assistant)
            self.assistants_menu.addAction(createAssistantAction)
            
            createChatAssistantAction = QAction('Create New / Edit Chat Assistant', self.main_window)
            createChatAssistantAction.triggered.connect(self.create_new_edit_chat_assistant)
            self.assistants_menu.addAction(createChatAssistantAction)
        elif self.client_type == AIClientType.AZURE_AI_AGENT:
            createAzureAIAgentAction = QAction('Create New / Edit Azure AI Agent', self.main_window)
            createAzureAIAgentAction.triggered.connect(self.create_new_edit_azure_ai_agent)
            self.assistants_menu.addAction(createAzureAIAgentAction)
        
        exportAction = QAction('Export', self.main_window)
        exportAction.triggered.connect(self.export_assistant)
        self.assistants_menu.addAction(exportAction)

    def update_client_type(self, new_client_type):
        if self.client_type != new_client_type:
            self.client_type = new_client_type
            self.create_assistants_menu()  # Update menu based on the new client type

    def create_new_edit_assistant(self):
        self.dialog = open_assistant_config_dialog(
            parent=self.main_window,
            assistant_type=AssistantType.ASSISTANT.value,
            function_config_manager=self.function_config_manager,
            callback=self.on_assistant_config_submitted
        )

    def create_new_edit_chat_assistant(self):
        self.dialog = open_assistant_config_dialog(
            parent=self.main_window,
            assistant_type=AssistantType.CHAT_ASSISTANT.value,
            function_config_manager=self.function_config_manager,
            callback=self.on_assistant_config_submitted
        )

    def create_new_edit_realtime_assistant(self):
        self.dialog = open_assistant_config_dialog(
            parent=self.main_window,
            assistant_type=AssistantType.REALTIME_ASSISTANT.value,
            function_config_manager=self.function_config_manager,
            callback=self.on_assistant_config_submitted
        )

    def create_new_edit_azure_ai_agent(self):
        self.dialog = open_assistant_config_dialog(
            parent=self.main_window,
            assistant_type=AssistantType.AGENT.value,
            function_config_manager=self.function_config_manager,
            callback=self.on_assistant_config_submitted
        )

    def on_assistant_config_submitted(self, assistant_config_json, ai_client_type, assistant_type, assistant_name):
        worker = ProcessAssistantWorker(
            assistant_config_json=assistant_config_json,
            ai_client_type=ai_client_type,
            assistant_type=assistant_type,
            assistant_name=assistant_name,
            main_window=self.main_window,
            assistant_client_manager=self.assistant_client_manager,
        )
        worker.signals.finished.connect(self.on_assistant_config_submit_finished)
        worker.signals.error.connect(self.on_assistant_config_submit_error)

        # Execute the worker in a separate thread using QThreadPool
        QThreadPool.globalInstance().start(worker)

    def on_assistant_config_submit_finished(self, result):
        assistant_client, realtime_audio, assistant_name, ai_client_type = result
        self.assistant_client_manager.register_client(
            name=assistant_name,
            assistant_client=assistant_client,
            realtime_audio=realtime_audio
        )
        client_type = AIClientType[ai_client_type]
        # UI update runs on the main thread.
        self.main_window.conversation_sidebar.load_assistant_list(client_type)
        self.dialog.update_assistant_combobox()

    def on_assistant_config_submit_error(self, error_msg):
        # Show error using a message box on the main thread.
        QMessageBox.warning(self.main_window, "Error",
                            f"An error occurred while creating/updating the assistant: {error_msg}")

    def export_assistant(self):
        dialog = ExportAssistantDialog(main_window=self.main_window)
        dialog.exec_()


class FunctionsMenu:
    def __init__(self, main_window):
        self.main_window = main_window
        self.funtionsMenu = self.main_window.menuBar().addMenu('&Functions')
        self.setup_functions_menu()

    def setup_functions_menu(self):
        createFunctionAction = QAction('Create New/Edit', self.main_window)
        createFunctionAction.triggered.connect(lambda: self.create_function())
        self.funtionsMenu.addAction(createFunctionAction)
        editErrorMessagesAction = QAction('Error Categories', self.main_window)
        editErrorMessagesAction.triggered.connect(lambda: self.edit_error_messages())
        self.funtionsMenu.addAction(editErrorMessagesAction)

    def edit_error_messages(self):
        editor = FunctionErrorsDialog(self.main_window)
        editor.show()

    def create_function(self):
        dialog = CreateFunctionDialog(self.main_window)
        dialog.show()


class DiagnosticsMenu:
    def __init__(self, main_window):
        self.main_window = main_window
        self.diagnosticsMenu = self.main_window.menuBar().addMenu('&Diagnostics')
        self.debugViewDialog = None
        self.broadcaster = None
        self.setup_menu()

    def setup_menu(self):
        # Action for function diagnostics
        diagAction = QAction("Run View", self.main_window, checkable=True)
        diagAction.triggered.connect(self.toggle_diagnostics_sidebar)
        self.diagnosticsMenu.addAction(diagAction)

        debugViewAction = QAction("Debug View", self.main_window)
        debugViewAction.triggered.connect(self.show_debug_view)
        self.diagnosticsMenu.addAction(debugViewAction)

    def toggle_diagnostics_sidebar(self, state):
        self.main_window.diagnostics_sidebar.setVisible(not self.main_window.diagnostics_sidebar.isVisible())

    def show_debug_view(self):
        if not self.debugViewDialog:
            self.broadcaster = LogBroadcaster()
            self.debugViewDialog = DebugViewDialog(self.broadcaster, self.main_window)
            add_broadcaster_to_logger(self.broadcaster)
        self.debugViewDialog.show()
        self.debugViewDialog.raise_()
        self.debugViewDialog.activateWindow()


class SettingsMenu:
    def __init__(self, main_window):
        self.main_window = main_window
        self.settingsMenu = self.main_window.menuBar().addMenu('&Settings')
        self.debugViewDialog = None
        self.broadcaster = None
        self.setup_menu()

    def setup_menu(self):
        chatSettingsAction = QAction("System Assistants", self.main_window)
        chatSettingsAction.triggered.connect(lambda: self.show_client_settings())
        self.settingsMenu.addAction(chatSettingsAction)

        # General settings
        generalSettingsAction = QAction("General", self.main_window)
        generalSettingsAction.triggered.connect(lambda: self.show_general_settings())
        self.settingsMenu.addAction(generalSettingsAction)

    def show_client_settings(self):
        dialog = ClientSettingsDialog(self.main_window)
        if dialog.exec_() == QDialog.Accepted:
            try:
                self.main_window.init_system_assistant_settings()
                self.main_window.init_system_assistants()
            except Exception as e:
                QMessageBox.warning(self.main_window, "Error", f"An error occurred while updating the settings: {e}")

    def show_general_settings(self):
        dialog = GeneralSettingsDialog(self.main_window)
        dialog.show()


class TasksMenu:
    def __init__(self, main_window):
        self.main_window = main_window
        self.tasksMenu = self.main_window.menuBar().addMenu('&Tasks')
        self.setup_tasks_menu()

    def setup_tasks_menu(self):
        # Action for editing error messages
        createTaskAction = QAction('Create New/Edit', self.main_window)
        createTaskAction.triggered.connect(lambda: self.create_task())
        self.tasksMenu.addAction(createTaskAction)
        # Action for schedule task
        scheduleTaskAction = QAction('Schedule', self.main_window)
        scheduleTaskAction.triggered.connect(lambda: self.schedule_task())
        self.tasksMenu.addAction(scheduleTaskAction)
        # Action for Show Tasks
        showTasksAction = QAction('View', self.main_window)
        showTasksAction.triggered.connect(lambda: self.show_scheduled_tasks())
        self.tasksMenu.addAction(showTasksAction)

    def create_task(self):
        dialog = CreateTaskDialog(self.main_window, self.main_window.task_manager)
        dialog.show()

    def schedule_task(self):
        if self.main_window.active_ai_client_type == AIClientType.OPEN_AI_REALTIME or self.main_window.active_ai_client_type == AIClientType.AZURE_OPEN_AI_REALTIME:
            QMessageBox.information(self.main_window, "Not Implemented", "This feature is not implemented for Realtime Assistants.")
            return

        dialog = ScheduleTaskDialog(self.main_window, self.main_window.task_manager)
        dialog.show()

    def show_scheduled_tasks(self):
        # Show not implemented dialog
        QMessageBox.information(self.main_window, "Not Implemented", "This feature is not implemented yet.")
        #dialog = ShowScheduledTasksDialog(self.main_window)
        #dialog.show()