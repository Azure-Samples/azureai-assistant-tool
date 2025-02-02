# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

import json
import threading
from typing import List

from PySide6.QtWidgets import QDialog, QSplitter, QComboBox, QTabWidget, QHBoxLayout, QWidget, QListWidget, QLineEdit, QVBoxLayout, QPushButton, QLabel, QTextEdit, QMessageBox
from PySide6.QtCore import Qt

from azure.ai.assistant.management.ai_client_type import AIClientType
from azure.ai.assistant.management.azure_logic_app_manager import AzureLogicAppManager
from azure.ai.assistant.management.function_config_manager import FunctionConfigManager
from azure.ai.assistant.management.logger_module import logger
from gui.signals import ErrorSignal, StartStatusAnimationSignal, StopStatusAnimationSignal
from gui.status_bar import ActivityStatus, StatusBar


class CreateFunctionDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        if hasattr(main_window, 'function_spec_creator') and hasattr(main_window, 'function_impl_creator'):
            self.function_spec_creator = main_window.function_spec_creator
            self.function_impl_creator = main_window.function_impl_creator
        if hasattr(main_window, 'azure_logic_app_function_creator'):
            self.azure_logic_app_function_creator = main_window.azure_logic_app_function_creator
        self.function_config_manager: FunctionConfigManager = main_window.function_config_manager
        self.init_UI()
        self.previousSize = self.size()

    def init_UI(self):
        self.setWindowTitle("Create/Edit Functions")
        self.resize(800, 900)

        mainLayout = QVBoxLayout(self)

        # Define necessary UI elements before connecting signals
        self.systemSpecEdit = self.create_text_edit()
        self.userSpecEdit = self.create_text_edit()
        self.userImplEdit = self.create_text_edit()

        # Tabs for System, User, and (optionally) Azure Logic Apps functions
        self.tabs = QTabWidget(self)
        self.systemFunctionsTab = self.create_system_functions_tab()
        self.userFunctionsTab = self.create_user_functions_tab()

        self.tabs.addTab(self.systemFunctionsTab, "System Functions")
        self.tabs.addTab(self.userFunctionsTab, "User Functions")
        
        # Add Azure Logic Apps tab if the active AI client is AZURE_AI_AGENT and azure_logic_app_manager is set
        if (getattr(self.main_window, 'active_ai_client_type', None) == AIClientType.AZURE_AI_AGENT and
            hasattr(self.main_window, 'azure_logic_app_manager')):
            self.azureLogicAppsTab = self.create_azure_logic_apps_tab()
            self.tabs.addTab(self.azureLogicAppsTab, "Azure Logic Apps")

        mainLayout.addWidget(self.tabs)

        # Buttons layout
        buttonLayout = QHBoxLayout()
        self.saveButton = QPushButton("Save Function", self)
        self.saveButton.clicked.connect(self.save_function)
        buttonLayout.addWidget(self.saveButton)

        self.removeButton = QPushButton("Remove Function", self)
        self.removeButton.clicked.connect(self.remove_function)
        self.removeButton.setEnabled(False)
        buttonLayout.addWidget(self.removeButton)
        mainLayout.addLayout(buttonLayout)

        self.tabs.currentChanged.connect(self.onTabChanged)

        self.status_bar = StatusBar(self)
        mainLayout.addWidget(self.status_bar.get_widget())

        self.start_processing_signal = StartStatusAnimationSignal()
        self.stop_processing_signal = StopStatusAnimationSignal()
        self.error_signal = ErrorSignal()
        self.start_processing_signal.start_signal.connect(self.start_processing)
        self.stop_processing_signal.stop_signal.connect(self.stop_processing)
        self.error_signal.error_signal.connect(lambda error_message: QMessageBox.warning(self, "Error", error_message))

    def create_azure_logic_apps_tab(self):
        """Creates the Azure Logic Apps tab with a combo box to list connected logic apps,
        a 'Details..' button next to the selector, a button to generate the user function, 
        and a text edit to display the generated user function."""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        selector_label = QLabel("Select Azure Logic App:", self)
        main_layout.addWidget(selector_label)
        
        # Create a horizontal layout for the selector and the new Details button.
        selector_layout = QHBoxLayout()

        self.azureLogicAppSelector = QComboBox(self)
        self.azureLogicAppSelector.addItems(self.list_logic_app_names())
        # Give the combo box a greater stretch so it will expand.
        selector_layout.addWidget(self.azureLogicAppSelector, stretch=3)

        # Create the Details button on the right side.
        self.viewLogicAppDetailsButton = QPushButton("Details..", self)
        self.viewLogicAppDetailsButton.clicked.connect(self.open_logic_app_details_dialog)
        # Set a fixed width for the Details button, making it smaller than the combo box.
        self.viewLogicAppDetailsButton.setFixedWidth(100)
        selector_layout.addWidget(self.viewLogicAppDetailsButton, stretch=1)

        main_layout.addLayout(selector_layout)

        # Button to generate user function from the Logic App.
        self.generateUserFunctionFromLogicAppButton = QPushButton("Generate User Function from Logic App...", self)
        self.generateUserFunctionFromLogicAppButton.clicked.connect(self.generate_user_function_for_logic_app)
        main_layout.addWidget(self.generateUserFunctionFromLogicAppButton)

        # Text edit to display the generated user function.
        self.azureUserFunctionEdit = self.create_text_edit()
        azureFunctionWidget = self.create_text_edit_labeled("Generated User Function:", self.azureUserFunctionEdit)
        main_layout.addWidget(azureFunctionWidget)

        return tab

    def open_logic_app_details_dialog(self):
        """
        Opens a dialog displaying the full details of the selected Azure Logic App.
        """
        from PySide6.QtWidgets import QMessageBox
        try:
            # Check if the main window contains the azure_logic_app_manager attribute.
            if hasattr(self.main_window, 'azure_logic_app_manager'):
                azure_manager : AzureLogicAppManager = self.main_window.azure_logic_app_manager
                logic_app_name = self.azureLogicAppSelector.currentText()
                if logic_app_name:
                    # Remove any suffix if it exists (e.g., " (HTTP Trigger)")
                    base_name = logic_app_name.split(" (HTTP Trigger)")[0]
                    
                    # Retrieve the complete details for the selected Logic App.
                    logic_app_details = azure_manager.get_logic_app_details(base_name)
                    
                    # Create and execute the details dialog (assuming LogicAppDetailsDialog is defined elsewhere).
                    dialog = LogicAppDetailsDialog(details=logic_app_details, parent=self)
                    dialog.exec()
                else:
                    QMessageBox.warning(self, "Warning", "No Logic App selected.")
            else:
                QMessageBox.warning(self, "Warning", "Azure Logic App Manager is not available.")
        except Exception as e:
            from azure.ai.assistant.management.logger_module import logger
            logger.error(f"Error retrieving logic app details: {e}")
            QMessageBox.warning(self, "Error", "Error retrieving logic app details.")

    def list_logic_app_names(self) -> List[str]:
        """
        Retrieves the names of Azure Logic Apps from the AzureLogicAppManager instance available in main_window.
        Returns a list of names formatted with an HTTP trigger indicator.
        """
        names = []
        try:
            azure_manager: AzureLogicAppManager = self.main_window.azure_logic_app_manager
            names = azure_manager.list_logic_apps()
        except Exception as e:
            logger.error(f"Error listing logic apps: {e}")
        return names

    def generate_user_function_for_logic_app(self):
        """
        Generates a user function for the selected Azure Logic App by using the function_impl_creator.
        The function name is derived from the Logic App's name, and the function implementation
        is built based on the provided HTTP trigger schema.
        """
        try:
            if not hasattr(self, 'azure_logic_app_function_creator'):
                raise Exception("Azure Logic App function creator not available, check the system assistant settings")

            logic_app_name = self.azureLogicAppSelector.currentText()
            base_name = logic_app_name.split(" (HTTP Trigger)")[0]
            schema_text = self.azureLogicAppSchemaEdit.toPlainText()
            if not schema_text:
                raise ValueError("Schema is empty. Please ensure the schema is loaded correctly.")

            # Construct the request message.
            request_message = (
                f"Logic App Name: {base_name}\n"
                f"JSON Schema: {schema_text}\n"
                "Please generate a Python function that accepts input parameters based on the JSON schema "
                "and invokes the Logic App via the service.invoke_logic_app() call. "
                "The function name should be derived from the Logic App name with snake_case format."
            )

            # Start the processing signal.
            self.start_processing_signal.start_signal.emit(ActivityStatus.PROCESSING)
            
            # Run the function generation on a separate thread.
            threading.Thread(target=self._generate_logic_app_user_function_thread, args=(request_message,)).start()
        except Exception as e:
            self.error_signal.error_signal.emit(
                f"An error occurred while generating the user function for the Logic App: {e}"
            )

    def _generate_logic_app_user_function_thread(self, request_message):
        try:
            self.code = self.azure_logic_app_function_creator.process_messages(user_request=request_message, stream=False)
            from azure.ai.assistant.management.logger_module import logger
            logger.info("User function implementation generated successfully.")
        except Exception as e:
            self.error_signal.error_signal.emit(
                f"An error occurred while generating the user function for the Logic App: {e}"
            )
        finally:
            # Signal to stop processing.
            self.stop_processing_signal.stop_signal.emit(ActivityStatus.PROCESSING)

    def toggle_max_height(self):
        if not self.isMaximized():
            self.previousSize = self.size()
            self.showMaximized()
        else:
            self.showNormal()
            self.resize(self.previousSize) 

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            self.toggle_max_height()
        else:
            super().keyPressEvent(event)

    def onTabChanged(self, index):
        # Enable the Remove button only for the User Functions tab.
        self.removeButton.setEnabled(self.tabs.tabText(index) == "User Functions")

    def create_system_functions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.systemFunctionSelector = self.create_function_selector("system")
        layout.addWidget(QLabel("Select System Function:"))
        layout.addWidget(self.systemFunctionSelector)

        layout.addWidget(QLabel("Function Specification:"))
        layout.addWidget(self.systemSpecEdit)

        return tab

    def create_user_functions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.userFunctionSelector = self.create_function_selector("user")
        layout.addWidget(QLabel("Select User Function:"))
        layout.addWidget(self.userFunctionSelector)

        self.userRequestLabel = QLabel("Function Requirements:")
        self.userRequest = QTextEdit(self)
        self.userRequest.setText("Create a function that...")
        self.userRequest.setMaximumHeight(50)
        self.userRequest.setStyleSheet(
            "QTextEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "  padding: 1px;"
            "}"
        )
        layout.addWidget(self.userRequestLabel)
        layout.addWidget(self.userRequest)

        self.generateSpecButton = QPushButton("Generate Specification with AI...", self)
        self.generateSpecButton.clicked.connect(self.generate_function_spec)
        layout.addWidget(self.generateSpecButton)

        splitter = QSplitter(Qt.Vertical, self)
        splitter.addWidget(self.create_text_edit_labeled("Function Specification:", self.userSpecEdit))
        splitter.addWidget(self.create_text_edit_labeled("Function Implementation:", self.userImplEdit))
        layout.addWidget(splitter)

        self.generateImplButton = QPushButton("Generate Implementation with AI...", self)
        self.generateImplButton.clicked.connect(self.generate_function_impl)
        layout.addWidget(self.generateImplButton)

        return tab

    def create_text_edit_labeled(self, label_text, text_edit_widget):
        widget = QWidget()
        widget.setStyleSheet("background-color: #2b2b2b;")  # matching background with create_text_edit
        layout = QVBoxLayout(widget)
        label = QLabel(label_text)
        label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
                background-color: #2b2b2b;
            }
        """)
        layout.addWidget(label)
        layout.addWidget(text_edit_widget)
        return widget

    def create_text_edit(self):
        textEdit = QTextEdit(self)
        textEdit.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #e0e0e0;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
            }
        """)
        textEdit.setAcceptRichText(False)
        return textEdit

    def create_function_selector(self, function_type):
        function_selector = QComboBox(self)
        function_selector.currentIndexChanged.connect(
            lambda: self.on_function_selected(
                function_selector,
                self.systemSpecEdit if function_type == "system" else self.userSpecEdit,
                self.userImplEdit if function_type == "user" else None
            )
        )
        self.load_functions(function_selector, function_type)
        return function_selector

    def load_functions(self, function_selector, function_type):
        functions_data = self.function_config_manager.get_all_functions_data()
        function_selector.clear()
        if function_type == "user":
            function_selector.addItem("New Function", None)
        for f_type, function_spec, _ in functions_data:
            if f_type == function_type:
                try:
                    func_name = function_spec['function']['name']
                    function_selector.addItem(func_name, (f_type, function_spec))
                except Exception as e:
                    logger.error(f"Error loading functions: {e}")

    def on_function_selected(self, function_selector, spec_edit, impl_edit=None):
        function_data = function_selector.currentData()
        if function_data:
            function_type, function_spec = function_data
            spec_edit.setText(json.dumps(function_spec, indent=4))
            if impl_edit and function_type == "user":
                impl_edit.setText(self.function_config_manager.get_user_function_code(function_spec['function']['name']))
            elif impl_edit:
                impl_edit.clear()
        else:
            spec_edit.clear()
            if impl_edit:
                impl_edit.clear()

    def start_processing(self, status):
        self.status_bar.start_animation(status)

    def stop_processing(self, status):
        self.status_bar.stop_animation(status)
        if self.tabs.tabText(self.tabs.currentIndex()) == "User Functions":
            if hasattr(self, 'spec_json') and self.spec_json is not None:
                self.userSpecEdit.setText(self.spec_json)
            if hasattr(self, 'code') and self.code is not None:
                self.userImplEdit.setText(self.code)
        elif self.tabs.tabText(self.tabs.currentIndex()) == "Azure Logic Apps":
            if hasattr(self, 'code') and self.code is not None:
                self.azureUserFunctionEdit.setText(self.code)

    def generate_function_spec(self):
        user_request = self.userRequest.toPlainText()
        threading.Thread(target=self._generate_function_spec, args=(user_request,)).start()

    def _generate_function_spec(self, user_request):
        try:
            if not hasattr(self, 'function_spec_creator'):
                raise Exception("Function spec creator not available, check the system assistant settings")
            self.start_processing_signal.start_signal.emit(ActivityStatus.PROCESSING)
            self.spec_json = self.function_spec_creator.process_messages(user_request=user_request, stream=False)
        except Exception as e:
            self.error_signal.error_signal.emit(f"An error occurred while generating the function spec: {e}")
        finally:
            self.stop_processing_signal.stop_signal.emit(ActivityStatus.PROCESSING)

    def generate_function_impl(self):
        user_request = self.userRequest.toPlainText()
        spec_json = self.userSpecEdit.toPlainText()
        threading.Thread(target=self._generate_function_impl, args=(user_request, spec_json)).start()

    def _generate_function_impl(self, user_request, spec_json):
        try:
            if not hasattr(self, 'function_impl_creator'):
                raise Exception("Function impl creator not available, check the system assistant settings")
            self.start_processing_signal.start_signal.emit(ActivityStatus.PROCESSING)
            request = user_request + " that follows the following spec: " + spec_json
            self.code = self.function_impl_creator.process_messages(user_request=request, stream=False)
        except Exception as e:
            self.error_signal.error_signal.emit(f"An error occurred while generating the function implementation: {e}")
        finally:
            self.stop_processing_signal.stop_signal.emit(ActivityStatus.PROCESSING)

    def save_function(self):
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            functionSpec = self.systemSpecEdit.toPlainText()
            functionImpl = None
            function_selector = self.systemFunctionSelector
        elif current_tab == 1:
            functionSpec = self.userSpecEdit.toPlainText()
            functionImpl = self.userImplEdit.toPlainText()
            function_selector = self.userFunctionSelector
        else:
            QMessageBox.warning(self, "Error", "Invalid tab selected")
            return

        try:
            is_valid, message = self.function_config_manager.validate_function(functionSpec, functionImpl)
            if not is_valid:
                QMessageBox.warning(self, "Error", f"Function is invalid: {message}")
                return
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while validating the function: {e}")
            return

        new_function_name = None
        current_function_name = function_selector.currentText()
        if current_function_name == "New Function":
            current_function_name = None

        try:
            _, new_function_name = self.function_config_manager.save_function_spec(functionSpec, current_function_name)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while saving the function spec: {e}")
            return

        if functionImpl:
            try:
                file_path = self.function_config_manager.save_function_impl(functionImpl, current_function_name, new_function_name)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"An error occurred while saving the function implementation: {e}")
                return

        try:
            self.function_config_manager.load_function_configs()
            self.refresh_dropdown()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while reloading the function specs: {e}")
            return

        success_message = f"Function '{new_function_name or current_function_name}' saved successfully."
        if functionImpl:
            success_message += f" Impl file: {file_path}"
        QMessageBox.information(self, "Success", success_message)

    def remove_function(self):
        current_tab = self.tabs.currentIndex()
        if self.tabs.tabText(current_tab) != "User Functions":
            QMessageBox.warning(self, "Error", "Invalid tab selected")
            return
        
        function_name = self.userFunctionSelector.currentText()
        if function_name == "New Function":
            QMessageBox.warning(self, "Error", "No function selected")
            return

        try:
            self.function_config_manager.delete_user_function(function_name)
            self.function_config_manager.load_function_configs()
            self.refresh_dropdown()
            QMessageBox.information(self, "Success", f"Function '{function_name}' removed successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while removing the function: {e}")

    def refresh_dropdown(self):
        self.load_functions(self.userFunctionSelector, "user")
        self.load_functions(self.systemFunctionSelector, "system")


class FunctionErrorsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.function_config_manager = main_window.function_config_manager
        self.error_specs = {}
        self.loadErrorSpecs()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Function Errors Editor")
        self.resize(700, 500)

        layout = QVBoxLayout(self)

        # Error Category Header
        categoryHeader = QLabel("Error Categories")
        layout.addWidget(categoryHeader)

        self.errorList = QListWidget()
        self.errorList.currentItemChanged.connect(self.onCategorySelected)
        layout.addWidget(self.errorList)

        # Populate the list widget with keys from the error messages
        for key in self.error_specs.keys():
            self.errorList.addItem(key)

        # New Error Category Header
        newCategoryHeader = QLabel("New Error Category")
        layout.addWidget(newCategoryHeader)

        self.categoryEdit = QLineEdit()  # For adding/editing error categories
        layout.addWidget(self.categoryEdit)

        # Error Message Header
        messageHeader = QLabel("Error Specification")
        layout.addWidget(messageHeader)

        self.messageEdit = QTextEdit()  # For editing the error message
        #self.messageEdit.setFont(QtGui.QFont("Arial", 14))  # Set font and size
        layout.addWidget(self.messageEdit)

        # Select the first category if available
        if self.errorList.count() > 0:
            self.errorList.setCurrentRow(0)

        # Buttons
        buttonLayout = QHBoxLayout()
        addButton = QPushButton("Add")
        addButton.clicked.connect(self.addCategory)
        removeButton = QPushButton("Remove")
        removeButton.clicked.connect(self.removeCategory)
        saveButton = QPushButton("Save")
        saveButton.clicked.connect(self.saveErrors)
        buttonLayout.addWidget(addButton)
        buttonLayout.addWidget(removeButton)
        buttonLayout.addWidget(saveButton)
        layout.addLayout(buttonLayout)

        self.setLayout(layout)

    def loadErrorSpecs(self):
        try:
            self.error_specs = self.function_config_manager.get_function_error_specs()
        except Exception as e:
            logger.error(f"Error loading error specs: {e}")

    def onCategorySelected(self, current, previous):
        if current:
            category = current.text()
            self.messageEdit.setText(self.error_specs[category])

    def addCategory(self):
        new_category = self.categoryEdit.text().strip()
        new_message = self.messageEdit.toPlainText().strip()

        if new_category and new_category not in self.error_specs:
            self.error_specs[new_category] = new_message
            self.errorList.addItem(new_category)
            self.categoryEdit.clear()
            self.messageEdit.clear()
        elif new_category in self.error_specs:
            # Optionally, handle the case where the category already exists
            logger.warning(f"The category '{new_category}' already exists.")

    def removeCategory(self):
        selected = self.errorList.currentItem()
        if selected:
            category = selected.text()
            del self.error_specs[category]
            self.errorList.takeItem(self.errorList.row(selected))

    def saveErrors(self):
        selected = self.errorList.currentItem()
        if selected:
            category = selected.text()
            new_message = self.messageEdit.toPlainText()
            self.error_specs[category] = new_message
            self.saveErrorSpecsToFile()  # Optionally save to file

    def saveErrorSpecsToFile(self):
        # This method saves the updated error messages back to the JSON file
        try:
            self.function_config_manager.save_function_error_specs(self.error_specs)
        except Exception as e:
            logger.error(f"Error saving error specs: {e}")


def format_logic_app_details(details: dict) -> str:
    from datetime import datetime
    """
    Formats the given logic app details dictionary into a pretty JSON string,
    converting datetime objects into ISO strings.
    """
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, datetime):
                return o.isoformat()
            return super().default(o)
    return json.dumps(details, indent=4, cls=DateTimeEncoder)


class LogicAppDetailsDialog(QDialog):
    def __init__(self, details: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Logic App Details")
        self.resize(600, 400)
        
        # Set up the layout.
        layout = QVBoxLayout(self)
        
        # Read-only text widget to display the formatted details.
        self.details_text = QTextEdit(self)
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #f0f0f0;
                color: #000000;
                font-family: Consolas, Monaco, monospace;
                font-size: 10pt;
            }
        """)
        
        formatted_details = format_logic_app_details(details)
        self.details_text.setPlainText(formatted_details)
        layout.addWidget(self.details_text)
        
        # "Close" button to dismiss the dialog.
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)