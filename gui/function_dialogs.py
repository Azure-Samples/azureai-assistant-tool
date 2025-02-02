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
        self.saveButton.clicked.connect(self.saveFunction)
        buttonLayout.addWidget(self.saveButton)

        self.removeButton = QPushButton("Remove Function", self)
        self.removeButton.clicked.connect(self.removeFunction)
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
        """Creates the Azure Logic Apps tab with a combo box to list the connected logic apps,
           a button to generate the user function, and a text edit to display the generated function."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(QLabel("Select Azure Logic App:"))
        self.azureLogicAppSelector = QComboBox(self)
        self.azureLogicAppSelector.addItems(self.list_logic_app_names())
        layout.addWidget(self.azureLogicAppSelector)

        self.generateUserFunctionFromLogicAppButton = QPushButton("Generate User Function from Logic App...", self)
        self.generateUserFunctionFromLogicAppButton.clicked.connect(self.generateUserFunctionFromLogicApp)
        layout.addWidget(self.generateUserFunctionFromLogicAppButton)

        self.azureUserFunctionEdit = self.create_text_edit()
        azureFunctionWidget = self.create_text_edit_labeled("Generated User Function:", self.azureUserFunctionEdit)
        layout.addWidget(azureFunctionWidget)

        return tab

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

    def generateUserFunctionFromLogicApp(self):
        """
        Generates a user function based on the selected Azure Logic App.
        Replace or extend this logic to integrate with your application's flow.
        """
        logic_app_name = self.azureLogicAppSelector.currentText()
        # Create a function name by sanitizing the logic app name
        function_name = logic_app_name.replace(" ", "_").replace("(", "").replace(")", "").lower()
        generated_function = (
            f"def function_from_{function_name}(params):\n"
            f"    # TODO: Add logic to invoke Azure Logic App '{logic_app_name}' using the callback URL\n"
            f"    pass\n"
        )
        self.azureUserFunctionEdit.setText(generated_function)

    def toggleMaxHeight(self):
        if not self.isMaximized():
            self.previousSize = self.size()
            self.showMaximized()
        else:
            self.showNormal()
            self.resize(self.previousSize) 

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            self.toggleMaxHeight()
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
        self.generateSpecButton.clicked.connect(self.generateFunctionSpec)
        layout.addWidget(self.generateSpecButton)

        splitter = QSplitter(Qt.Vertical, self)
        splitter.addWidget(self.create_text_edit_labeled("Function Specification:", self.userSpecEdit))
        splitter.addWidget(self.create_text_edit_labeled("Function Implementation:", self.userImplEdit))
        layout.addWidget(splitter)

        self.generateImplButton = QPushButton("Generate Implementation with AI...", self)
        self.generateImplButton.clicked.connect(self.generateFunctionImpl)
        layout.addWidget(self.generateImplButton)

        return tab

    def create_text_edit_labeled(self, label_text, text_edit_widget):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(label_text)
        layout.addWidget(label)
        layout.addWidget(text_edit_widget)
        return widget

    def create_text_edit(self):
        textEdit = QTextEdit(self)
        textEdit.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #e0e0e0;
                font-family: 'Consolas', 'Monaco', 'monospace';
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
        if hasattr(self, 'spec_json') and self.spec_json is not None:
            self.userSpecEdit.setText(self.spec_json)
        if hasattr(self, 'code') and self.code is not None:
            self.userImplEdit.setText(self.code)

    def generateFunctionSpec(self):
        user_request = self.userRequest.toPlainText()
        threading.Thread(target=self._generateFunctionSpec, args=(user_request,)).start()

    def _generateFunctionSpec(self, user_request):
        try:
            if not hasattr(self, 'function_spec_creator'):
                raise Exception("Function spec creator not available, check the system assistant settings")
            self.start_processing_signal.start_signal.emit(ActivityStatus.PROCESSING)
            self.spec_json = self.function_spec_creator.process_messages(user_request=user_request, stream=False)
        except Exception as e:
            self.error_signal.error_signal.emit(f"An error occurred while generating the function spec: {e}")
        finally:
            self.stop_processing_signal.stop_signal.emit(ActivityStatus.PROCESSING)

    def generateFunctionImpl(self):
        user_request = self.userRequest.toPlainText()
        spec_json = self.userSpecEdit.toPlainText()
        threading.Thread(target=self._generateFunctionImpl, args=(user_request, spec_json)).start()

    def _generateFunctionImpl(self, user_request, spec_json):
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

    def saveFunction(self):
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

    def removeFunction(self):
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