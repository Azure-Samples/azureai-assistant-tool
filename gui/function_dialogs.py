# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

import threading
from PySide6.QtWidgets import QDialog, QSplitter, QComboBox, QTabWidget, QHBoxLayout, QWidget, QListWidget, QLineEdit, QVBoxLayout, QPushButton, QLabel, QTextEdit, QMessageBox
from PySide6.QtCore import Qt
import json, re

from azure.ai.assistant.management.function_config_manager import FunctionConfigManager
from azure.ai.assistant.management.logger_module import logger
from gui.signals import ErrorSignal, StartStatusAnimationSignal, StopStatusAnimationSignal
from gui.status_bar import ActivityStatus, StatusBar


class CreateFunctionDialog(QDialog):
    def __init__(self, main_window, function_config_manager : FunctionConfigManager):
        super().__init__(main_window)
        self.main_window = main_window
        self.function_config_manager = function_config_manager
        self.initUI()
        self.previousSize = self.size()

    def initUI(self):
        self.setWindowTitle("Create/Edit Functions")
        self.resize(800, 900)

        mainLayout = QVBoxLayout(self)

        # Define necessary UI elements before connecting signals
        self.systemSpecEdit = self.create_text_edit()
        self.userSpecEdit = self.create_text_edit()
        self.userImplEdit = self.create_text_edit()

        # Tabs for System and User Functions
        self.tabs = QTabWidget(self)
        self.systemFunctionsTab = self.create_system_functions_tab()
        self.userFunctionsTab = self.create_user_functions_tab()

        self.tabs.addTab(self.systemFunctionsTab, "System Functions")
        self.tabs.addTab(self.userFunctionsTab, "User Functions")

        mainLayout.addWidget(self.tabs)

        # Buttons layout
        buttonLayout = QHBoxLayout()

        # Shared Save Button
        self.saveButton = QPushButton("Save Function", self)
        self.saveButton.clicked.connect(self.saveFunction)
        buttonLayout.addWidget(self.saveButton)

        # Remove Button
        self.removeButton = QPushButton("Remove Function", self)
        self.removeButton.clicked.connect(self.removeFunction)
        self.removeButton.setEnabled(False)  # Disabled by default
        buttonLayout.addWidget(self.removeButton)

        mainLayout.addLayout(buttonLayout)

        # Connect tab changed signal
        self.tabs.currentChanged.connect(self.onTabChanged)

        self.status_bar = StatusBar(self)
        mainLayout.addWidget(self.status_bar.get_widget())

        self.start_processing_signal = StartStatusAnimationSignal()
        self.stop_processing_signal = StopStatusAnimationSignal()
        self.error_signal = ErrorSignal()
        self.start_processing_signal.start_signal.connect(self.start_processing)
        self.stop_processing_signal.stop_signal.connect(self.stop_processing)
        self.error_signal.error_signal.connect(lambda error_message: QMessageBox.warning(self, "Error", error_message))

    def toggleMaxHeight(self):
        if not self.isMaximized():
            self.previousSize = self.size()  # Store the current size
            self.showMaximized()  # Maximize the window
        else:
            self.showNormal()  # Restore to the previous size
            self.resize(self.previousSize) 

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            self.toggleMaxHeight()
        else:
            super().keyPressEvent(event)

    def onTabChanged(self, index):
        # Enable the Remove button only for the User Functions tab
        self.removeButton.setEnabled(index == 1) 

    def create_system_functions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # System Functions Selector
        self.systemFunctionSelector = self.create_function_selector("system")
        layout.addWidget(QLabel("Select System Function:"))
        layout.addWidget(self.systemFunctionSelector)

        # System Function Spec Edit
        layout.addWidget(QLabel("Function Specification:"))
        layout.addWidget(self.systemSpecEdit)

        return tab

    def create_user_functions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # User Functions Selector
        self.userFunctionSelector = self.create_function_selector("user")
        layout.addWidget(QLabel("Select User Function:"))
        layout.addWidget(self.userFunctionSelector)

        # Function requirements
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

        # Button to generate specification with AI
        self.generateSpecButton = QPushButton("Generate Specification with AI...", self)
        self.generateSpecButton.clicked.connect(self.generateFunctionSpec)
        layout.addWidget(self.generateSpecButton)

        # QSplitter for resizable userSpecEdit and userImplEdit
        splitter = QSplitter(Qt.Vertical, self)
        splitter.addWidget(self.create_text_edit_labeled("Function Specification:", self.userSpecEdit))
        splitter.addWidget(self.create_text_edit_labeled("Function Implementation:", self.userImplEdit))
        layout.addWidget(splitter)

        # Button to generate implementation with AI
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
            lambda: self.on_function_selected(function_selector, self.systemSpecEdit if function_type == "system" else self.userSpecEdit, self.userImplEdit if function_type == "user" else None)
        )
        self.load_functions(function_selector, function_type)
        return function_selector

    def load_functions(self, function_selector, function_type):
        functions_data = self.function_config_manager.get_all_functions_data()
        function_selector.clear()

        # Add "New Function" option only for user functions
        if function_type == "user":
            function_selector.addItem("New Function", None)

        for f_type, function_spec, _ in functions_data:
            # Filter functions based on the specified type ('system' or 'user')
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
            # "New Function" selected, clear inputs for new function
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
            self.start_processing_signal.start_signal.emit(ActivityStatus.PROCESSING)
            self.spec_json = self.main_window.function_creator.get_function_spec(user_request)
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
            self.start_processing_signal.start_signal.emit(ActivityStatus.PROCESSING)
            func_impl = self.main_window.function_creator.get_function_impl(user_request, spec_json)
            self.code = self.extract_python_code(func_impl)
        except Exception as e:
            self.error_signal.error_signal.emit(f"An error occurred while generating the function implementation: {e}")
        finally:
            self.stop_processing_signal.stop_signal.emit(ActivityStatus.PROCESSING)

    def extract_python_code(self, text):
        # Regular expression pattern to find code blocks
        pattern = r"```python\s+(.*?)```"
        # Use re.DOTALL to match across multiple lines
        matches = re.findall(pattern, text, re.DOTALL)
        # Join all matches (if there are multiple code blocks)
        extracted_code = "\n\n".join(matches)
        return extracted_code

    def saveFunction(self):
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:  # System Functions Tab
            functionSpec = self.systemSpecEdit.toPlainText()
            functionImpl = None
            function_selector = self.systemFunctionSelector
        elif current_tab == 1:  # User Functions Tab
            functionSpec = self.userSpecEdit.toPlainText()
            functionImpl = self.userImplEdit.toPlainText()
            function_selector = self.userFunctionSelector
        else:
            QMessageBox.warning(self, "Error", "Invalid tab selected")
            return

        # Validate the function spec and (if applicable) implementation
        try:
            is_valid, message = self.function_config_manager.validate_function(functionSpec, functionImpl)
            if not is_valid:
                QMessageBox.warning(self, "Error", f"Function is invalid: {message}")
                return
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while validating the function: {e}")

        new_function_name = None
        current_function_name = function_selector.currentText()
        if current_function_name == "New Function":
            current_function_name = None

        try:
            _, new_function_name = self.function_config_manager.save_function_spec(functionSpec, current_function_name)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while saving the function spec: {e}")
            return

        if functionImpl:  # Only for user functions
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
        # remove function is only available for user functions
        current_tab = self.tabs.currentIndex()
        if current_tab != 1:
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
        # Reloads the functions into the user and system function selector comboboxes
        self.load_functions(self.userFunctionSelector, "user")
        self.load_functions(self.systemFunctionSelector, "system")


class FunctionErrorsDialog(QDialog):
    def __init__(self, main_window, function_config_manager : FunctionConfigManager):
        super().__init__(main_window)
        self.main_window = main_window
        self.function_config_manager = function_config_manager
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