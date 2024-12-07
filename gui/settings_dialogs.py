# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QLabel, QPushButton, QComboBox, QMessageBox, QHBoxLayout, QCheckBox

import os, json

from azure.ai.assistant.management.ai_client_factory import AIClientType, AIClientFactory


class GeneralSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super(GeneralSettingsDialog, self).__init__(parent)
        self.setWindowTitle("General Settings")
        self.main_window = parent

        # Initialize the UI components
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)

        # HTTP connection timeout configuration
        self.connectionTimeoutLayout = QHBoxLayout()
        self.connectionTimeoutLabel = QLabel("HTTP Connection Timeout (s):", self)
        self.connectionTimeoutEdit = QLineEdit(self)
        self.connectionTimeoutEdit.setText(str(self.main_window.connection_timeout))
        self.connectionTimeoutLayout.addWidget(self.connectionTimeoutLabel)
        self.connectionTimeoutLayout.addWidget(self.connectionTimeoutEdit)
        
        # System assistant for friendly conversation thread names
        self.useSystemAssistantForThreadsCheckbox = QCheckBox("Enable system assistant to generate friendly conversation thread names", self)
        self.useSystemAssistantForThreadsCheckbox.setChecked(self.main_window.use_system_assistant_for_thread_name)

        # Streaming for assistant
        self.useStreamingForAssistantCheckbox = QCheckBox("Use streaming for assistant", self)
        self.useStreamingForAssistantCheckbox.setChecked(self.main_window.use_streaming_for_assistant)

        # Buttons
        self.buttonsLayout = QHBoxLayout()
        self.okButton = QPushButton("OK", self)
        self.cancelButton = QPushButton("Cancel", self)
        self.buttonsLayout.addWidget(self.okButton)
        self.buttonsLayout.addWidget(self.cancelButton)

        # Adding layouts to the main layout
        self.layout.addLayout(self.connectionTimeoutLayout)
        self.layout.addWidget(self.useStreamingForAssistantCheckbox)
        self.layout.addWidget(self.useSystemAssistantForThreadsCheckbox)
        self.layout.addLayout(self.buttonsLayout)

        # Connect signals
        self.okButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

    def accept(self):
        try:
            connection_timeout = float(self.connectionTimeoutEdit.text())
            self.main_window.connection_timeout = connection_timeout
            self.main_window.use_system_assistant_for_thread_name = self.useSystemAssistantForThreadsCheckbox.isChecked()
            self.main_window.use_streaming_for_assistant = self.useStreamingForAssistantCheckbox.isChecked()
            # Here you would save these values to your settings or pass them to where they are needed
            super(GeneralSettingsDialog, self).accept()  # Close the dialog on success
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numbers for the timeouts.")


class ClientSettingsDialog(QDialog):
    def __init__(self, main_window):
        super(ClientSettingsDialog, self).__init__(main_window)
        self.main_window = main_window
        self.init_settings()
        self.init_ui()

    def init_settings(self):
        self.config_folder = "config"
        self.file_name = "system_assistant_settings.json"
        self.file_path = os.path.join(self.config_folder, self.file_name)
        os.makedirs(self.config_folder, exist_ok=True)
        self.settings = {}
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle("System Assistants")
        self.resize(400, 400)
        self.layout = QVBoxLayout(self)

        # Client Selection Label
        self.clientSelectionLabel = QLabel("Select AI client for System Assistants:")
        self.layout.addWidget(self.clientSelectionLabel)

        # Create combo box for client selection
        self.clientSelection = QComboBox()
        self.clientSelection.addItem(AIClientType.OPEN_AI.name)
        self.clientSelection.addItem(AIClientType.AZURE_OPEN_AI.name)
        self.layout.addWidget(self.clientSelection)
        # Connect the client selection change signal to the slot
        self.clientSelection.currentIndexChanged.connect(self.update_model_selection)

        # OpenAI API Key
        self.openai_api_key_input = QLineEdit()
        self.openai_api_key_input.setPlaceholderText("Enter your OpenAI API key")
        self.layout.addWidget(QLabel("OpenAI API Key:"))
        self.layout.addWidget(self.openai_api_key_input)

        # Azure OpenAI API Key
        self.azure_api_key_input = QLineEdit()
        self.azure_api_key_input.setPlaceholderText("Enter your Azure OpenAI API key")
        self.layout.addWidget(QLabel("Azure OpenAI API Key:"))
        self.layout.addWidget(self.azure_api_key_input)

        # Azure Endpoint
        self.azure_endpoint_input = QLineEdit()
        self.azure_endpoint_input.setPlaceholderText("Enter your Azure OpenAI Endpoint")
        self.layout.addWidget(QLabel("Azure OpenAI Endpoint:"))
        self.layout.addWidget(self.azure_endpoint_input)

        # Azure API Version
        self.azure_api_version_input = QLineEdit()
        self.azure_api_version_input.setPlaceholderText("Enter your Azure OpenAI API Version")
        self.layout.addWidget(QLabel("Azure OpenAI API Version:"))
        self.layout.addWidget(self.azure_api_version_input)

        # Model selection
        self.model_selection = QComboBox()
        self.model_selection.setEditable(True)
        self.model_selection.toolTip = "Select the model to use for the system assistant, e.g. for function generation"
        ai_client_type = AIClientType[self.clientSelection.currentText()]
        self.layout.addWidget(QLabel("Model for System Assistants:"))
        self.layout.addWidget(self.model_selection)

        # Apply Button
        self.applyButton = QPushButton("Apply")
        self.applyButton.clicked.connect(self.apply_settings)
        self.layout.addWidget(self.applyButton)

        # Set initial states based on settings
        self.set_initial_states()

    def load_settings(self):
        """ Load settings from JSON file. """
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as file:
                loaded_settings = json.load(file)
                self.settings.update(loaded_settings)

    def set_initial_states(self):
        ai_client_type = self.settings.get("ai_client_type", AIClientType.AZURE_OPEN_AI.name)
        api_version = self.settings.get("api_version", "2024-02-15-preview")
        self.azure_api_version_input.setText(api_version)

        if ai_client_type == AIClientType.OPEN_AI.name:
            api_version = None

        # Fill the model selection
        self.fill_client_model_selection(AIClientType[ai_client_type], api_version)

        # Set the API keys and endpoint values from environment variables
        self.set_key_input_value(self.openai_api_key_input, "OPENAI_API_KEY")
        self.set_key_input_value(self.azure_api_key_input, "AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        endpoint = AIClientFactory.get_instance()._get_http_endpoint(endpoint)
        self.azure_endpoint_input.setText(endpoint)

    def fill_client_model_selection(self, ai_client_type, api_version=None):

        if ai_client_type == AIClientType.AZURE_OPEN_AI:
            self.clientSelection.setCurrentText(AIClientType.AZURE_OPEN_AI.name)
            self.azure_endpoint_input.setEnabled(True)
            self.azure_api_key_input.setEnabled(True)
            self.openai_api_key_input.setEnabled(False)
            self.azure_api_version_input.setEnabled(True)
        else:
            self.clientSelection.setCurrentText(AIClientType.OPEN_AI.name)
            self.azure_endpoint_input.setEnabled(False)
            self.azure_api_key_input.setEnabled(False)
            self.openai_api_key_input.setEnabled(True)
            self.azure_api_version_input.setEnabled(False)

        # Clear existing items in model_selection
        self.model_selection.clear()

        try:
            if ai_client_type == AIClientType.OPEN_AI:
                # Get the AI client instance, pass the api_version if it's set
                ai_client = AIClientFactory.get_instance().get_client(ai_client_type, api_version)
                # Fetch and add new models to the model_selection
                if ai_client:
                    models = ai_client.models.list().data
                    for model in models:
                        self.model_selection.addItem(model.id)
            elif ai_client_type == AIClientType.AZURE_OPEN_AI:
                models = []

            # Set the default model
            default_model = self.settings.get("model", "")
            if default_model:
                self.model_selection.setCurrentText(default_model)

        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to fill model selection: {e}")

    def update_model_selection(self):
        # Get the current AI client type
        ai_client_type = AIClientType[self.clientSelection.currentText()]

        # Determine the API version for Azure OpenAI, if needed
        api_version = None
        if ai_client_type == AIClientType.AZURE_OPEN_AI:
            api_version = self.azure_api_version_input.text().strip() or "2024-02-15-preview"

        # Call fill_model_selection with the selected AI client type and API version
        self.fill_client_model_selection(ai_client_type, api_version)

    def set_key_input_value(self, input_field, env_var):
        key = os.getenv(env_var, "")
        if key:
            # Obscure all but the last 4 characters of the key
            obscured_key = '*' * (len(key) - 4) + key[-4:]
            input_field.setText(obscured_key)

    def apply_settings(self):
        ai_client_type = self.clientSelection.currentText()
        # Check for empty required fields
        if ai_client_type == AIClientType.OPEN_AI and not self.openai_api_key_input.text():
            QMessageBox.critical(self, "Error", "OpenAI API Key is required when applying OpenAI settings.")
            return
        elif ai_client_type == AIClientType.AZURE_OPEN_AI and (not self.azure_api_key_input.text() or not self.azure_endpoint_input.text()):
            QMessageBox.critical(self, "Error", "Azure OpenAI API Key and Endpoint are required when applying Azure OpenAI settings.")
            return

        settings = {
            "ai_client_type": ai_client_type,
            "model": self.model_selection.currentText(),
            "api_version": self.azure_api_version_input.text()
        }

        # Save the API keys and endpoint to environment variables
        self.save_environment_variable("OPENAI_API_KEY", self.openai_api_key_input.text())
        self.save_environment_variable("AZURE_OPENAI_API_KEY", self.azure_api_key_input.text())
        self.save_environment_variable("AZURE_OPENAI_ENDPOINT", self.azure_endpoint_input.text())

        # Save the settings to file
        self.save_settings(json.dumps(settings, indent=4))
        self.accept()

    def save_environment_variable(self, var_name, value):
        if value and not value.startswith('*******'):
            os.environ[var_name] = value

    def save_settings(self, settings_json : str):
        with open(self.file_path, 'w') as file:
            file.write(settings_json)
