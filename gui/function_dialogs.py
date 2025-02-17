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
from gui.utils import camel_to_snake


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

        # Separate variables for each tab's results.
        self.user_spec_json = None
        self.user_code = None
        self.azure_spec_json = None
        self.azure_code = None

    def init_UI(self):
        self.setWindowTitle("Create/Edit Functions")
        self.resize(800, 900)

        mainLayout = QVBoxLayout(self)

        # Define necessary UI elements before connecting signals
        self.systemSpecEdit = self.create_text_edit()
        self.userSpecEdit = self.create_text_edit()
        self.userImplEdit = self.create_text_edit()

        # Tabs for System, User, Azure Logic Apps (optional), and OpenAPI (optional)
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

        # Add OpenAPI tab if we are in an agent mode 
        if getattr(self.main_window, 'active_ai_client_type', None) == AIClientType.AZURE_AI_AGENT:
            self.openapiTab = self.create_openapi_tab()
            self.tabs.addTab(self.openapiTab, "OpenAPI")

        mainLayout.addWidget(self.tabs)

        # Buttons layout at the bottom
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

        self.setLayout(mainLayout)

    def create_openapi_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # Choose an existing OpenAPI function (if any) or create a new one
        select_label = QLabel("Select OpenAPI Function:")
        main_layout.addWidget(select_label)

        self.openapiSelector = QComboBox(self)
        self.load_openapi_functions()  # Populates self.openapiSelector
        self.openapiSelector.currentIndexChanged.connect(self.on_openapi_function_selected)
        main_layout.addWidget(self.openapiSelector)

        # Name
        name_label = QLabel("Name:")
        self.openapiNameEdit = QLineEdit()
        main_layout.addWidget(name_label)
        main_layout.addWidget(self.openapiNameEdit)

        # Description
        desc_label = QLabel("Description:")
        self.openapiDescriptionEdit = QLineEdit()
        main_layout.addWidget(desc_label)
        main_layout.addWidget(self.openapiDescriptionEdit)

        # Auth
        auth_label = QLabel("Auth Type:")
        self.openapiAuthSelector = QComboBox()
        self.openapiAuthSelector.addItems(["anonymous", "connection", "managed_identity"])
        main_layout.addWidget(auth_label)
        main_layout.addWidget(self.openapiAuthSelector)

        # Raw JSON text for the spec
        self.openapiSpecEdit = self.create_text_edit()
        openapiSpecWidget = self.create_text_edit_labeled("OpenAPI Specification:", self.openapiSpecEdit)
        main_layout.addWidget(openapiSpecWidget)

        return tab

    def load_openapi_functions(self):
        self.openapiSelector.clear()
        self.openapiSelector.addItem("New OpenAPI Function", None)

        try:
            openapi_functions = self.function_config_manager.get_all_openapi_functions()
            for item in openapi_functions:
                # item is presumed to be a dict with the shape: {'type':'openapi','openapi': {...}}
                try:
                    name = item["openapi"]["name"]
                    self.openapiSelector.addItem(name, item)  # store the entire dict as data
                except Exception:
                    logger.warning("Malformed OpenAPI entry encountered while loading.")
        except Exception as e:
            logger.error(f"Error loading OpenAPI functions: {e}")

    def on_openapi_function_selected(self):
        data = self.openapiSelector.currentData()
        if data:
            try:
                openapi_data = data.get("openapi", {})
                auth_data = data.get("auth", {})
                
                # Name
                name_val = openapi_data.get("name", "")
                self.openapiNameEdit.setText(name_val)

                # Description
                desc_val = openapi_data.get("description", "")
                self.openapiDescriptionEdit.setText(desc_val)

                # Auth
                auth_type_val = auth_data.get("type", "anonymous")
                index = self.openapiAuthSelector.findText(auth_type_val)
                if index >= 0:
                    self.openapiAuthSelector.setCurrentIndex(index)

                # Spec (convert dict to JSON text)
                spec_dict = openapi_data.get("spec", {})
                spec_text = json.dumps(spec_dict, indent=4)
                self.openapiSpecEdit.setText(spec_text)

            except Exception as ex:
                logger.warning(f"Malformed OpenAPI entry: {ex}")
                self.openapiNameEdit.clear()
                self.openapiDescriptionEdit.clear()
                self.openapiSpecEdit.clear()
        else:
            # "New OpenAPI Function" selected or no data
            self.openapiNameEdit.clear()
            self.openapiDescriptionEdit.clear()
            self.openapiSpecEdit.clear()
            self.openapiAuthSelector.setCurrentIndex(0)  # default to "anonymous", for example

    def save_openapi_function(self):
        # Gather fields
        name_val = self.openapiNameEdit.text().strip()
        desc_val = self.openapiDescriptionEdit.text().strip()
        auth_val = self.openapiAuthSelector.currentText()
        raw_spec = self.openapiSpecEdit.toPlainText().strip()

        if not name_val:
            QMessageBox.warning(self, "Error", "OpenAPI name is required.")
            return
        
        if not raw_spec:
            QMessageBox.warning(self, "Error", "OpenAPI spec is empty or invalid.")
            return

        try:
            spec_dict = json.loads(raw_spec)
        except json.JSONDecodeError as ex:
            QMessageBox.warning(self, "Error", f"Invalid JSON for OpenAPI spec:\n{e}")
            return

        openapi_data = {
            "type": "openapi",
            "openapi": {
                "name": name_val,
                "description": desc_val,
                "spec": spec_dict
            },
            "auth": {
                "type": auth_val
            }
        }

        # Pass this object to our manager to handle creation/update in openapi_functions.json
        try:
            self.function_config_manager.save_openapi_function(openapi_data)
            QMessageBox.information(self, "Success", "OpenAPI definition saved successfully.")
            self.load_openapi_functions()
        except Exception as e:
            logger.error(f"Error saving OpenAPI function: {e}")
            QMessageBox.warning(self, "Error", f"Could not save OpenAPI function: {e}")

    def create_azure_logic_apps_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        selector_label = QLabel("Select Azure Logic App:", self)
        main_layout.addWidget(selector_label)
        
        selector_layout = QHBoxLayout()

        self.azureLogicAppSelector = QComboBox(self)
        selector_layout.addWidget(self.azureLogicAppSelector, stretch=3)

        self.loadAzureLogicAppsButton = QPushButton("Load", self)
        self.loadAzureLogicAppsButton.clicked.connect(self.load_azure_logic_apps)
        self.loadAzureLogicAppsButton.setFixedWidth(100)
        selector_layout.addWidget(self.loadAzureLogicAppsButton, stretch=1)

        self.viewLogicAppDetailsButton = QPushButton("Details..", self)
        self.viewLogicAppDetailsButton.clicked.connect(self.open_logic_app_details_dialog)
        self.viewLogicAppDetailsButton.setFixedWidth(100)
        selector_layout.addWidget(self.viewLogicAppDetailsButton, stretch=1)

        main_layout.addLayout(selector_layout)

        buttons_layout = QHBoxLayout()
        self.generateUserFunctionFromLogicAppButton = QPushButton("Generate User Function from Logic App", self)
        self.generateUserFunctionFromLogicAppButton.clicked.connect(self.generate_user_function_for_logic_app)
        buttons_layout.addWidget(self.generateUserFunctionFromLogicAppButton)

        self.clearImplementationButton = QPushButton("Clear Implementation", self)
        self.clearImplementationButton.clicked.connect(self.clear_azure_user_function_impl)
        buttons_layout.addWidget(self.clearImplementationButton)
        main_layout.addLayout(buttons_layout)

        self.azureUserFunctionSpecEdit = self.create_text_edit()
        self.azureUserFunctionImplEdit = self.create_text_edit()

        splitter = QSplitter(Qt.Vertical, self)
        splitter.addWidget(self.create_text_edit_labeled("Function Specification:", self.azureUserFunctionSpecEdit))
        splitter.addWidget(self.create_text_edit_labeled("Function Implementation:", self.azureUserFunctionImplEdit))
        main_layout.addWidget(splitter)

        return tab

    def clear_azure_user_function_impl(self):
        self.azureUserFunctionSpecEdit.clear()
        self.azureUserFunctionImplEdit.clear()

    def load_azure_logic_apps(self):
        self.azureLogicAppSelector.clear()
        self.azureLogicAppSelector.addItems(self.list_logic_app_names())

    def open_logic_app_details_dialog(self):
        from PySide6.QtWidgets import QMessageBox
        try:
            if hasattr(self.main_window, 'azure_logic_app_manager'):
                azure_manager: AzureLogicAppManager = self.main_window.azure_logic_app_manager
                logic_app_name = self.azureLogicAppSelector.currentText()
                if logic_app_name:
                    base_name = logic_app_name.split(" (HTTP Trigger)")[0]
                    logic_app_details = azure_manager.get_logic_app_details(base_name)
                    dialog = LogicAppDetailsDialog(details=logic_app_details, parent=self)
                    dialog.exec()
                else:
                    QMessageBox.warning(self, "Warning", "No Logic App selected.")
            else:
                QMessageBox.warning(self, "Warning", "Azure Logic App Manager is not available.")
        except Exception as e:
            logger.error(f"Error retrieving logic app details: {e}")
            QMessageBox.warning(self, "Error", "Error retrieving logic app details.")

    def list_logic_app_names(self) -> List[str]:
        names = []
        try:
            if hasattr(self.main_window, 'azure_logic_app_manager'):
                azure_manager: AzureLogicAppManager = self.main_window.azure_logic_app_manager
                azure_manager.initialize_logic_apps(trigger_name="When_a_HTTP_request_is_received")
                names = azure_manager.list_logic_apps()
        except Exception as e:
            logger.error(f"Error listing logic apps: {e}")
        return names

    def generate_user_function_for_logic_app(self):
        try:
            if not hasattr(self, 'azure_logic_app_function_creator'):
                raise Exception("Azure Logic App function creator not available, check the system assistant settings")
            logic_app_name = self.azureLogicAppSelector.currentText()
            base_name = logic_app_name.split(" (HTTP Trigger)")[0]
            azure_manager: AzureLogicAppManager = self.main_window.azure_logic_app_manager
            schema = azure_manager.get_http_trigger_schema(
                logic_app_name=base_name,
                trigger_name="When_a_HTTP_request_is_received"
            )
            schema_text = json.dumps(schema, indent=4)
            if not schema_text:
                raise ValueError("Schema is empty. Please ensure the schema is loaded correctly.")

            request_message = (
                f"Function name: {camel_to_snake(base_name)}\n"
                f"Logic App Name for the invoke method inside the function: {base_name}\n"
                f"JSON Schema: {schema_text}\n"
                "Please generate a Python function which name is given logic app name "
                "and that accepts input parameters based on the given JSON schema."
            )

            self.start_processing_signal.start_signal.emit(ActivityStatus.PROCESSING)
            # Generate the spec (goes into self.azure_spec_json on completion)
            threading.Thread(target=self._generate_function_spec, args=(request_message, "Azure Logic Apps")).start()
            # Generate the code (goes into self.azure_code on completion)
            threading.Thread(target=self._generate_logic_app_user_function_thread, args=(request_message,)).start()
        except Exception as e:
            self.error_signal.error_signal.emit(
                f"An error occurred while generating the user function for the Logic App: {e}"
            )

    def _generate_logic_app_user_function_thread(self, request_message):
        try:
            self.azure_code = self.azure_logic_app_function_creator.process_messages(
                user_request=request_message, 
                stream=False
            )
            logger.info("User function implementation generated successfully.")
        except Exception as e:
            self.error_signal.error_signal.emit(
                f"An error occurred while generating the user function for the Logic App: {e}"
            )
        finally:
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
        tab_text = self.tabs.tabText(index)
        if tab_text in ["User Functions", "OpenAPI"]:
            self.removeButton.setEnabled(True)
            self.removeButton.setDisabled(False)
        else:
            self.removeButton.setEnabled(False)
            self.removeButton.setDisabled(True)

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
        widget.setStyleSheet("background-color: #2b2b2b;")
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

    def get_user_function_names(self):
        functions_data = self.function_config_manager.get_all_functions_data()
        return [f_spec['function']['name'] for f_type, f_spec, _ in functions_data if f_type == "user"]

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
            # If user-type function, also load its implementation
            if impl_edit and function_type == "user":
                impl_edit.setText(self.function_config_manager.get_user_function_code(function_spec['function']['name']))
            elif impl_edit:
                impl_edit.clear()
        else:
            # "New Function" selected or no data
            spec_edit.clear()
            if impl_edit:
                impl_edit.clear()

    def start_processing(self, status):
        self.status_bar.start_animation(status)

    def stop_processing(self, status):
        self.status_bar.stop_animation(status)
        # Based on the current active tab, update only that tab's controls if needed
        current_tab = self.tabs.tabText(self.tabs.currentIndex())
        if current_tab == "User Functions":
            if self.user_spec_json is not None:
                self.userSpecEdit.setText(self.user_spec_json)
            if self.user_code is not None:
                self.userImplEdit.setText(self.user_code)
        elif current_tab == "Azure Logic Apps":
            if self.azure_spec_json is not None:
                self.azureUserFunctionSpecEdit.setText(self.azure_spec_json)
            if self.azure_code is not None:
                self.azureUserFunctionImplEdit.setText(self.azure_code)

    def generate_function_spec(self):
        user_request = self.userRequest.toPlainText()
        # When generating for user functions, indicate target as "User Functions".
        threading.Thread(
            target=self._generate_function_spec, 
            args=(user_request, "User Functions")
        ).start()

    def _generate_function_spec(self, user_request, target_tab):
        try:
            if not hasattr(self, 'function_spec_creator'):
                raise Exception("Function spec creator not available, check the system assistant settings")
            self.start_processing_signal.start_signal.emit(ActivityStatus.PROCESSING)
            result = self.function_spec_creator.process_messages(user_request=user_request, stream=False)
            if target_tab == "User Functions":
                self.user_spec_json = result
            elif target_tab == "Azure Logic Apps":
                self.azure_spec_json = result
        except Exception as e:
            self.error_signal.error_signal.emit(f"An error occurred while generating the function spec: {e}")
        finally:
            self.stop_processing_signal.stop_signal.emit(ActivityStatus.PROCESSING)

    def generate_function_impl(self):
        user_request = self.userRequest.toPlainText()
        spec_json = self.userSpecEdit.toPlainText()
        threading.Thread(
            target=self._generate_function_impl, 
            args=(user_request, spec_json)
        ).start()

    def _generate_function_impl(self, user_request, spec_json):
        try:
            if not hasattr(self, 'function_impl_creator'):
                raise Exception("Function impl creator not available, check the system assistant settings")
            self.start_processing_signal.start_signal.emit(ActivityStatus.PROCESSING)
            request = user_request + " that follows the following spec: " + spec_json
            self.user_code = self.function_impl_creator.process_messages(user_request=request, stream=False)
        except Exception as e:
            self.error_signal.error_signal.emit(f"An error occurred while generating the function implementation: {e}")
        finally:
            self.stop_processing_signal.stop_signal.emit(ActivityStatus.PROCESSING)

    def save_function(self):
        current_tab_text = self.tabs.tabText(self.tabs.currentIndex())
        
        if current_tab_text == "System Functions":
            functionSpec = self.systemSpecEdit.toPlainText()
            functionImpl = None
            function_selector = self.systemFunctionSelector

        elif current_tab_text == "User Functions":
            functionSpec = self.userSpecEdit.toPlainText()
            functionImpl = self.userImplEdit.toPlainText()
            function_selector = self.userFunctionSelector

        elif current_tab_text == "Azure Logic Apps":
            functionSpec = self.azureUserFunctionSpecEdit.toPlainText()
            functionImpl = self.azureUserFunctionImplEdit.toPlainText()
            function_selector = None

        elif current_tab_text == "OpenAPI":
            try:
                self.save_openapi_function()
                return
            except Exception as e:
                QMessageBox.warning(self, "Error", f"An error occurred while saving the OpenAPI function: {e}")
                return
        else:
            QMessageBox.warning(self, "Error", "Invalid tab selected")
            return

        # Validate spec and impl
        try:
            is_valid, message = self.function_config_manager.validate_function(functionSpec, functionImpl)
            if not is_valid:
                QMessageBox.warning(self, "Error", f"Function is invalid: {message}")
                return
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while validating the function: {e}")
            return

        new_function_name = None

        # Figure out the function name from the spec or the selector
        if current_tab_text == "Azure Logic Apps":
            try:
                spec_dict = json.loads(functionSpec)
                current_user_function_names = self.get_user_function_names()
                logic_app_function_name = spec_dict["function"]["name"]
                if logic_app_function_name in current_user_function_names:
                    QMessageBox.warning(self, "Error", f"Function '{logic_app_function_name}' already exists.")
                    return
                current_function_name = None
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error extracting function name from the spec: {e}")
                return

        elif function_selector is not None:
            current_function_name = function_selector.currentText()
            if current_function_name == "New Function":
                current_function_name = None
        else:
            current_function_name = None

        # Save the spec
        try:
            _, new_function_name = self.function_config_manager.save_function_spec(functionSpec, current_function_name)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while saving the function spec: {e}")
            return

        # Save the impl if any
        if functionImpl:
            try:
                file_path = self.function_config_manager.save_function_impl(
                    functionImpl, 
                    current_function_name, 
                    new_function_name
                )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"An error occurred while saving the function implementation: {e}")
                return

        # Reload and refresh
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
        current_tab_text = self.tabs.tabText(self.tabs.currentIndex())

        if current_tab_text == "System Functions":
            # If your FunctionConfigManager has no method to remove system functions,
            # show a warning or implement your own logic here.
            QMessageBox.warning(self, "Not Supported", "Removing system functions is not supported.")
            return

        elif current_tab_text == "User Functions":
            # Example: remove using the name from a combo box (or text field)
            function_name = self.userFunctionSelector.currentText().strip()
            if not function_name:
                QMessageBox.warning(self, "Error", "Please select a user function to remove.")
                return

            confirm = QMessageBox.question(
                self, "Confirm Remove", 
                f"Are you sure you want to remove the user function '{function_name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.No:
                return

            success = self.function_config_manager.delete_user_function(function_name)
            if success:
                QMessageBox.information(self, "Removed", f"User function '{function_name}' was removed successfully.")
                self.function_config_manager.load_function_configs()
                self.refresh_dropdown()
            else:
                QMessageBox.warning(self, "Error", f"User function '{function_name}' was not found.")

        elif current_tab_text == "Azure Logic Apps":
            # If you don't have a remove method for Azure logic apps yet, show a message (or implement similarly)
            QMessageBox.warning(self, "Not Supported", "Removing Azure Logic App functions is not yet supported.")
            return

        elif current_tab_text == "OpenAPI":
            # Remove the OpenAPI function, using its name from an edit or the combo box
            openapi_name = self.openapiNameEdit.text().strip()
            if not openapi_name:
                QMessageBox.warning(self, "Error", "Cannot remove OpenAPI function: no name specified.")
                return

            confirm = QMessageBox.question(
                self, "Confirm Remove", 
                f"Are you sure you want to remove the OpenAPI definition '{openapi_name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.No:
                return

            success = self.function_config_manager.delete_openapi_function(openapi_name)
            if success:
                QMessageBox.information(self, "Removed", f"OpenAPI definition '{openapi_name}' was removed successfully.")
                self.load_openapi_functions()
            else:
                QMessageBox.warning(self, "Error", f"OpenAPI definition '{openapi_name}' was not found.")

        else:
            QMessageBox.warning(self, "Error", "Invalid tab selected for removal.")


    def refresh_dropdown(self):
        self.load_functions(self.userFunctionSelector, "user")
        self.load_functions(self.systemFunctionSelector, "system")
        # If an openapi tab is present, re-load that combobox too:
        if hasattr(self, 'openapiSelector'):
            self.load_openapi_functions()


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
        layout.addWidget(self.messageEdit)

        # Buttons row
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

        # If there's at least one error category, select the first by default
        if self.errorList.count() > 0:
            self.errorList.setCurrentRow(0)

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
            self.saveErrorSpecsToFile()

    def saveErrorSpecsToFile(self):
        try:
            self.function_config_manager.save_function_error_specs(self.error_specs)
        except Exception as e:
            logger.error(f"Error saving error specs: {e}")


def format_logic_app_details(details: dict) -> str:
    from datetime import datetime

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
        
        layout = QVBoxLayout(self)
        
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
        
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        
        self.setLayout(layout)