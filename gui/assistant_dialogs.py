# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6 import QtGui
from PySide6.QtWidgets import QDialog, QComboBox, QTabWidget, QSizePolicy, QScrollArea, QHBoxLayout, QWidget, QFileDialog, QListWidget, QLineEdit, QVBoxLayout, QPushButton, QLabel, QCheckBox, QTextEdit, QMessageBox, QSlider
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon, QTextOption

import json, os, shutil, threading

from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.function_config_manager import FunctionConfigManager
from azure.ai.assistant.management.ai_client_factory import AIClientType, AIClientFactory
from azure.ai.assistant.management.logger_module import logger
from gui.signals import UserInputSendSignal, UserInputSignal
from gui.speech_input_handler import SpeechInputHandler
from gui.signals import ErrorSignal, StartStatusAnimationSignal, StopStatusAnimationSignal
from gui.status_bar import ActivityStatus, StatusBar
from gui.utils import resource_path


class AssistantConfigDialog(QDialog):
    assistantConfigSubmitted = Signal(str, str, str)

    def __init__(
            self, 
            parent=None, 
            assistant_type : str = "assistant",
            assistant_name : str = None,
            function_config_manager : FunctionConfigManager = None
    ):
        super().__init__(parent)
        self.main_window = parent
        if hasattr(self.main_window, 'instructions_reviewer'):
            self.instructions_reviewer = self.main_window.instructions_reviewer
        self.assistant_config_manager = self.main_window.assistant_config_manager
        self.assistant_type = assistant_type
        self.assistant_name = assistant_name
        self.function_config_manager = function_config_manager

        self.init_variables()
        self.init_speech_input()
        self.init_ui()

    def init_variables(self):
        self.knowledge_files_dict = {}  # Dictionary to store knowledge file paths and IDs
        self.selected_functions = []  # Store the selected functions
        self.code_interpreter = False  # Store the code interpreter setting
        self.knowledge_retrieval = False  # Store the knowledge retrieval setting
        self.checkBoxes = {}  # To keep track of all function checkboxes
        self.assistant_id = ''
        self.default_output_folder_path = os.path.join(os.getcwd(), 'output')
        # make sure the output folder path exists and create it if it doesn't
        if not os.path.exists(self.default_output_folder_path):
            os.makedirs(self.default_output_folder_path)

    def init_speech_input(self):
        self.is_mic_on = False
        self.currentHypothesis = ""
        self.user_input_signal = UserInputSignal()
        self.user_input_send_signal = UserInputSendSignal()
        self.user_input_signal.update_signal.connect(self.on_user_input)
        self.user_input_send_signal.send_signal.connect(self.on_user_input_complete)
        try:
            self.speech_input_handler = SpeechInputHandler(self, self.user_input_signal.update_signal, self.user_input_send_signal.send_signal)
        except ValueError as e:
            logger.error(f"Error initializing speech input handler: {e}")

    def on_tab_changed(self, index):
        # Check if the microphone is on when changing tabs
        if self.is_mic_on:
            self.toggle_mic()

        # If the Instructions Editor tab is selected, copy the instructions from the Configuration tab
        if index == 3:
            self.newInstructionsEdit.setPlainText(self.instructionsEdit.toPlainText())

    def closeEvent(self, event):
        # Check if the microphone is on when closing the window
        if self.is_mic_on:
            self.toggle_mic()
        super(AssistantConfigDialog, self).closeEvent(event)

    def init_ui(self):
        self.setWindowTitle("Assistant Configuration")
        self.tabWidget = QTabWidget(self)
        self.tabWidget.currentChanged.connect(self.on_tab_changed)

        # Create General Configuration tab
        configTab = self.create_config_tab()
        self.tabWidget.addTab(configTab, "General")

        # Create Tools tab
        toolsTab = self.create_tools_tab()
        self.tabWidget.addTab(toolsTab, "Tools")

        completionTab = self.create_completion_tab()
        self.tabWidget.addTab(completionTab, "Completion")

        # Create Instructions Editor tab
        instructionsEditorTab = self.create_instructions_tab()
        self.tabWidget.addTab(instructionsEditorTab, "Instructions Editor")

        # Set the main layout
        mainLayout = QVBoxLayout(self)
        mainLayout.addWidget(self.tabWidget)

        # Save Button
        self.saveButton = QPushButton('Save Configuration')
        self.saveButton.clicked.connect(self.save_configuration)
        mainLayout.addWidget(self.saveButton)

        # setup status bar
        self.status_bar = StatusBar(self)
        mainLayout.addWidget(self.status_bar.get_widget())

        # Set the main layout
        self.setLayout(mainLayout)

        self.start_processing_signal = StartStatusAnimationSignal()
        self.stop_processing_signal = StopStatusAnimationSignal()
        self.error_signal = ErrorSignal()
        self.start_processing_signal.start_signal.connect(self.start_processing)
        self.stop_processing_signal.stop_signal.connect(self.stop_processing)
        self.error_signal.error_signal.connect(lambda error_message: QMessageBox.warning(self, "Error", error_message))

        self.ai_client_selection_changed()

        # Set the initial size of the dialog to make it wider
        self.resize(600, 600)  # Adjusted to a more standard size, you can change it back to 600x900 if needed

    def create_config_tab(self):
        configTab = QWidget()  # Configuration tab
        configLayout = QVBoxLayout(configTab)

        # AI client selection
        self.aiClientLabel = QLabel('AI Client:')
        self.aiClientComboBox = QComboBox()
        ai_client_type_names = [client_type.name for client_type in AIClientType]
        self.aiClientComboBox.addItems(ai_client_type_names)
        active_ai_client_type = self.main_window.active_ai_client_type
        self.aiClientComboBox.setCurrentIndex(ai_client_type_names.index(active_ai_client_type.name))
        self.aiClientComboBox.currentIndexChanged.connect(self.ai_client_selection_changed)
        configLayout.addWidget(self.aiClientLabel)
        configLayout.addWidget(self.aiClientComboBox)

        # Assistant selection combo box
        self.assistantLabel = QLabel('Assistant:')
        self.assistantComboBox = QComboBox()
        self.assistantComboBox.currentIndexChanged.connect(self.assistant_selection_changed)
        configLayout.addWidget(self.assistantLabel)
        configLayout.addWidget(self.assistantComboBox)

        # Name input field
        self.nameLabel = QLabel('Name:')
        self.nameEdit = QLineEdit()
        self.nameEdit.setStyleSheet(
            "QLineEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "  padding: 1px;"
            "}"
        )
        configLayout.addWidget(self.nameLabel)
        configLayout.addWidget(self.nameEdit)

        # Instructions - using QTextEdit for multi-line input
        self.instructionsLabel = QLabel('Instructions:')
        self.instructionsEdit = QTextEdit()
        self.instructionsEdit.setStyleSheet(
            "QTextEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "  padding: 1px;"
            "}"
        )
        self.instructionsEdit.setAcceptRichText(False)
        self.instructionsEdit.setWordWrapMode(QTextOption.WordWrap)
        self.instructionsEdit.setMinimumHeight(100)
        configLayout.addWidget(self.instructionsLabel)
        configLayout.addWidget(self.instructionsEdit)

        # Knowledge Files, Add File, and Remove File buttons
        self.fileReferenceLabel = QLabel('File References:')
        self.fileReferenceList = QListWidget()
        self.fileReferenceList.setToolTip("Select files to be used as references in the assistant instructions, example: {file_reference:0}, where 0 is the index of the file in the list")
        self.fileReferenceList.setStyleSheet(
            "QListWidget {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "}"
        )
        self.fileReferenceAddButton = QPushButton('Add File...')
        self.fileReferenceAddButton.clicked.connect(self.add_reference_file)
        self.fileReferenceRemoveButton = QPushButton('Remove File')
        self.fileReferenceRemoveButton.clicked.connect(self.remove_reference_file)

        fileButtonLayout = QHBoxLayout()
        fileButtonLayout.addWidget(self.fileReferenceAddButton)
        fileButtonLayout.addWidget(self.fileReferenceRemoveButton)

        configLayout.addWidget(self.fileReferenceLabel)
        configLayout.addWidget(self.fileReferenceList)
        configLayout.addLayout(fileButtonLayout)

        # Model selection
        self.modelLabel = QLabel('Model:')
        self.modelComboBox = QComboBox()
        self.modelComboBox.setEditable(True)
        self.modelComboBox.setStyleSheet(
            "QLineEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "  padding: 1px;"
            "}"
        )
        configLayout.addWidget(self.modelLabel)
        configLayout.addWidget(self.modelComboBox)

        # Create as new assistant checkbox
        self.createAsNewCheckBox = QCheckBox("Create as New Assistant")
        self.createAsNewCheckBox.stateChanged.connect(lambda state: setattr(self, 'is_create', state == Qt.CheckState.Checked.value))
        configLayout.addWidget(self.createAsNewCheckBox)

        # Output Folder Path
        self.outputFolderPathLabel = QLabel('Output Folder Path For Files')
        self.outputFolderPathEdit = QLineEdit()
        self.outputFolderPathEdit.setText(self.default_output_folder_path)
        self.outputFolderPathButton = QPushButton('Select Folder...')
        self.outputFolderPathButton.clicked.connect(self.select_output_folder_path)

        outputFolderPathLayout = QHBoxLayout()
        outputFolderPathLayout.addWidget(self.outputFolderPathEdit)
        outputFolderPathLayout.addWidget(self.outputFolderPathButton)

        configLayout.addWidget(self.outputFolderPathLabel)
        configLayout.addLayout(outputFolderPathLayout)

        return configTab

    def create_tools_tab(self):
        toolsTab = QWidget()
        toolsLayout = QVBoxLayout(toolsTab)

        # Scroll Area for functions
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollWidget = QWidget()
        self.scrollLayout = QVBoxLayout(self.scrollWidget)

        # Function sections
        if self.function_config_manager:
            function_configs =  self.function_config_manager.get_function_configs()
            for function_type, funcs in function_configs.items():
                self.create_function_section(self.scrollLayout, function_type, funcs)

        self.scrollArea.setWidget(self.scrollWidget)
        self.scrollArea.setStyleSheet(
            "QScrollArea {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "}"
        )
        toolsLayout.addWidget(self.scrollArea)

        # Knowledge Files, Add File, and Remove File buttons
        self.knowledgeFileLabel = QLabel('Knowledge Files:')
        self.knowledgeFileList = QListWidget()
        self.knowledgeFileList.setStyleSheet(
            "QListWidget {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "}"
        )
        self.knowledgeFileButton = QPushButton('Add File...')
        self.knowledgeFileButton.clicked.connect(self.add_knowledge_file)
        self.knowledgeFileRemoveButton = QPushButton('Remove File')
        self.knowledgeFileRemoveButton.clicked.connect(self.remove_knowledge_file)

        fileButtonLayout = QHBoxLayout()
        fileButtonLayout.addWidget(self.knowledgeFileButton)
        fileButtonLayout.addWidget(self.knowledgeFileRemoveButton)

        toolsLayout.addWidget(self.knowledgeFileLabel)
        toolsLayout.addWidget(self.knowledgeFileList)
        toolsLayout.addLayout(fileButtonLayout)

        # Enable Knowledge Retrieval checkbox
        self.knowledgeRetrievalCheckBox = QCheckBox("Enable Knowledge Retrieval")
        self.knowledgeRetrievalCheckBox.stateChanged.connect(lambda state: setattr(self, 'knowledge_retrieval', state == Qt.CheckState.Checked.value))
        toolsLayout.addWidget(self.knowledgeRetrievalCheckBox)

        if self.assistant_type == "assistant":
            self.codeInterpreterCheckBox = QCheckBox("Enable Code Interpreter")
            self.codeInterpreterCheckBox.stateChanged.connect(lambda state: setattr(self, 'code_interpreter', state == Qt.CheckState.Checked.value))
            toolsLayout.addWidget(self.codeInterpreterCheckBox)
        elif self.assistant_type == "chat_assistant":
            self.knowledgeFileButton.setEnabled(False)
            self.knowledgeFileRemoveButton.setEnabled(False)
            self.knowledgeRetrievalCheckBox.setEnabled(False)
        return toolsTab

    def create_completion_tab(self):
        completionTab = QWidget()
        completionLayout = QVBoxLayout(completionTab)

        # Use Default Settings Checkbox
        self.useDefaultSettingsCheckBox = QCheckBox("Use Default Settings (when checked, the following settings will be ignored)")
        self.useDefaultSettingsCheckBox.setChecked(True)
        self.useDefaultSettingsCheckBox.stateChanged.connect(self.toggleCompletionSettings)
        completionLayout.addWidget(self.useDefaultSettingsCheckBox)

        if self.assistant_type == "assistant":
            self.init_temperature_settings(completionLayout)
        elif self.assistant_type == "chat_assistant":
            self.init_full_completion_settings(completionLayout)

        self.toggleCompletionSettings()

        return completionTab

    def init_temperature_settings(self, completionLayout):
        # Temperature
        self.temperatureLabel = QLabel('Temperature:')
        self.temperatureSlider = QSlider(Qt.Horizontal)
        self.temperatureSlider.setToolTip("Controls the randomness of the generated text. Lower values make the text more deterministic, while higher values make it more random.")
        self.temperatureSlider.setMinimum(0)
        self.temperatureSlider.setMaximum(200)
        self.temperatureSlider.setValue(70)  # Default value as 0.7 for illustration
        self.temperatureValueLabel = QLabel('0.7')
        self.temperatureSlider.valueChanged.connect(lambda: self.temperatureValueLabel.setText(f"{self.temperatureSlider.value() / 100:.1f}"))
        completionLayout.addWidget(self.temperatureLabel)
        completionLayout.addWidget(self.temperatureSlider)
        completionLayout.addWidget(self.temperatureValueLabel)

    def init_full_completion_settings(self, completionLayout):

        # Frequency Penalty
        self.frequencyPenaltyLabel = QLabel('Frequency Penalty:')
        self.frequencyPenaltySlider = QSlider(Qt.Horizontal)
        self.frequencyPenaltySlider.setToolTip("Positive values penalize new tokens based on their existing frequency in the text so far, decreasing the model's likelihood to repeat the same line verbatim.")
        self.frequencyPenaltySlider.setMinimum(-200)
        self.frequencyPenaltySlider.setMaximum(200)
        self.frequencyPenaltySlider.setValue(0)  # Default value
        self.frequencyPenaltyValueLabel = QLabel('0.0')
        self.frequencyPenaltySlider.valueChanged.connect(lambda: self.frequencyPenaltyValueLabel.setText(f"{self.frequencyPenaltySlider.value() / 100:.1f}"))
        completionLayout.addWidget(self.frequencyPenaltyLabel)
        completionLayout.addWidget(self.frequencyPenaltySlider)
        completionLayout.addWidget(self.frequencyPenaltyValueLabel)
        
        # Max Tokens
        self.maxTokensLabel = QLabel('Max Tokens:')
        self.maxTokensEdit = QLineEdit()
        self.maxTokensEdit.setToolTip("The maximum number of tokens to generate. The model will stop once it has generated this many tokens.")
        completionLayout.addWidget(self.maxTokensLabel)
        completionLayout.addWidget(self.maxTokensEdit)
        
        # Presence Penalty
        self.presencePenaltyLabel = QLabel('Presence Penalty:')
        self.presencePenaltySlider = QSlider(Qt.Horizontal)
        self.presencePenaltySlider.setToolTip("Positive values penalize new tokens based on whether they appear in the text so far, increasing the model's likelihood to talk about new topics.")
        self.presencePenaltySlider.setMinimum(-200)
        self.presencePenaltySlider.setMaximum(200)
        self.presencePenaltySlider.setValue(0)  # Default value
        self.presencePenaltyValueLabel = QLabel('0.0')
        self.presencePenaltySlider.valueChanged.connect(lambda: self.presencePenaltyValueLabel.setText(f"{self.presencePenaltySlider.value() / 100:.1f}"))
        completionLayout.addWidget(self.presencePenaltyLabel)
        completionLayout.addWidget(self.presencePenaltySlider)
        completionLayout.addWidget(self.presencePenaltyValueLabel)
        
        # Response Format
        self.responseFormatLabel = QLabel('Response Format:')
        self.responseFormatComboBox = QComboBox()
        self.responseFormatComboBox.setToolTip("Select the format of the response from the AI model")
        self.responseFormatComboBox.addItems(["text", "json_object"])
        completionLayout.addWidget(self.responseFormatLabel)
        completionLayout.addWidget(self.responseFormatComboBox)
        
        self.init_temperature_settings(completionLayout)

        # Top P
        self.topPLabel = QLabel('Top P:')
        self.topPSlider = QSlider(Qt.Horizontal)
        self.topPSlider.setToolTip("Controls the diversity of the generated text. Lower values make the text more deterministic, while higher values make it more diverse.")
        self.topPSlider.setMinimum(0)
        self.topPSlider.setMaximum(100)
        self.topPSlider.setValue(10)  # Default value as 0.1 for illustration
        self.topPValueLabel = QLabel('0.1')
        self.topPSlider.valueChanged.connect(lambda: self.topPValueLabel.setText(f"{self.topPSlider.value() / 100:.1f}"))
        completionLayout.addWidget(self.topPLabel)
        completionLayout.addWidget(self.topPSlider)
        completionLayout.addWidget(self.topPValueLabel)

        # Seed
        self.seedLabel = QLabel('Seed:')
        self.seedEdit = QLineEdit()
        self.seedEdit.setToolTip("If specified, system will make a best effort to sample deterministically, such that repeated requests with the same seed and parameters should return the same result. Determinism is not guaranteed, and you should refer to the system_fingerprint response parameter to monitor changes in the backend.")
        completionLayout.addWidget(self.seedLabel)
        completionLayout.addWidget(self.seedEdit)

        self.maxMessagesLayout = QHBoxLayout()
        self.maxMessagesLabel = QLabel('Max Number of Messages In Conversation Thread Context:')
        self.maxMessagesEdit = QLineEdit()
        self.maxMessagesEdit.setToolTip("The maximum number of messages to include in the conversation thread context. If set to None, no limit will be applied.")
        self.maxMessagesLayout.addWidget(self.maxMessagesLabel)
        self.maxMessagesLayout.addWidget(self.maxMessagesEdit)

        completionLayout.addLayout(self.maxMessagesLayout)

    def toggleCompletionSettings(self):
        # Determine if controls should be enabled based on the checkbox and assistant type
        isEnabled = not self.useDefaultSettingsCheckBox.isChecked()
        
        if self.assistant_type == "assistant":
            self.temperatureSlider.setEnabled(isEnabled)
        elif self.assistant_type == "chat_assistant":
            self.frequencyPenaltySlider.setEnabled(isEnabled)
            self.maxTokensEdit.setEnabled(isEnabled)
            self.presencePenaltySlider.setEnabled(isEnabled)
            self.responseFormatComboBox.setEnabled(isEnabled)
            self.topPSlider.setEnabled(isEnabled)
            self.seedEdit.setEnabled(isEnabled)
            self.maxMessagesEdit.setEnabled(isEnabled)
            self.temperatureSlider.setEnabled(isEnabled)

    def ai_client_selection_changed(self):
        self.ai_client_type = AIClientType[self.aiClientComboBox.currentText()]
        assistant_config_manager = AssistantConfigManager.get_instance()
        assistant_names = assistant_config_manager.get_assistant_names_by_client_type(self.ai_client_type.name)

        self.assistantComboBox.clear()
        self.assistantComboBox.insertItem(0, "New Assistant")
        for assistant_name in assistant_names:
            assistant_config = assistant_config_manager.get_config(assistant_name)
            if assistant_config.assistant_type == self.assistant_type:
                self.assistantComboBox.addItem(assistant_name)

        self.modelComboBox.clear()
        try:
            ai_client = AIClientFactory.get_instance().get_client(self.ai_client_type)
            if self.ai_client_type == AIClientType.OPEN_AI:
                if ai_client:
                    models = ai_client.models.list().data
                    for model in models:
                        self.modelComboBox.addItem(model.id)
        except Exception as e:
            logger.error(f"Error getting models from AI client: {e}")
        finally:
            if self.ai_client_type == AIClientType.OPEN_AI:
                self.modelComboBox.setToolTip("Select a model ID supported for assistant from the list")
            elif self.ai_client_type == AIClientType.AZURE_OPEN_AI:
                self.modelComboBox.setToolTip("Select a model deployment name from the Azure OpenAI resource")

        # If assistant_name is provided, set the assistantComboBox to the assistant_name
        index = self.assistantComboBox.findText(self.assistant_name)
        if index >= 0:
            self.assistantComboBox.setCurrentIndex(index)
        else:
            self.assistantComboBox.setCurrentIndex(0)  # Set default to "New Assistant"

    def assistant_selection_changed(self):
        self.reset_fields()
        selected_assistant = self.assistantComboBox.currentText()
        if selected_assistant == "New Assistant":
            self.is_create = True
            self.nameEdit.setEnabled(True)
            self.createAsNewCheckBox.setEnabled(False)
            self.outputFolderPathEdit.setText(self.default_output_folder_path)
        # if selected_assistant is not empty string, load the assistant config
        elif selected_assistant != "":
            self.is_create = False
            self.pre_load_assistant_config(selected_assistant)
            self.createAsNewCheckBox.setEnabled(True)
            # disable name edit
            self.nameEdit.setEnabled(False)

    def get_name(self):
        return self.nameEdit.text()

    def reset_fields(self):
        self.nameEdit.clear()
        self.instructionsEdit.clear()
        self.modelComboBox.setCurrentIndex(0)
        self.knowledge_files_dict = {}
        # Reset all checkboxes in the function sections
        for function_type, checkBoxes in self.checkBoxes.items():
            for checkBox in checkBoxes:
                checkBox.setChecked(False)
        self.selected_functions = []
        self.knowledge_retrieval = False
        self.code_interpreter = False
        self.knowledgeFileList.clear()
        self.knowledgeRetrievalCheckBox.setChecked(False)
        if self.assistant_type == "assistant":
            self.codeInterpreterCheckBox.setChecked(False)
        self.outputFolderPathEdit.clear()
        self.assistant_config = None

    def create_instructions_tab(self):
        instructionsEditorTab = QWidget()
        instructionsEditorLayout = QVBoxLayout(instructionsEditorTab)

        # Load icons
        self.mic_on_icon = QIcon(resource_path("gui/images/mic_on.png"))
        self.mic_off_icon = QIcon(resource_path("gui/images/mic_off.png"))

        # Microphone button
        self.micButton = QPushButton()
        self.micButton.setIcon(self.mic_off_icon)  # Set initial icon
        self.micButton.setIconSize(QSize(24, 24))  # Set icon size
        self.micButton.setFixedSize(30, 30)  # Set button size
        self.micButton.clicked.connect(self.toggle_mic)
        self.micButton.setStyleSheet("QPushButton { border: none; }")  # Optional: remove border
        self.micButton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Add microphone button to the top left corner
        topLayout = QHBoxLayout()
        topLayout.addWidget(self.micButton)
        topLayout.addStretch()  # This will push the button to the right
        instructionsEditorLayout.addLayout(topLayout)

        # QTextEdit for entering instructions
        self.newInstructionsEdit = QTextEdit()
        self.newInstructionsEdit.setText("1. Write Your Instructions Here")
        instructionsEditorLayout.addWidget(self.newInstructionsEdit)

        # 'Check Instructions' button
        checkInstructionsButton = QPushButton('Review Instructions with AI...')
        checkInstructionsButton.clicked.connect(self.check_instructions)
        instructionsEditorLayout.addWidget(checkInstructionsButton)

        return instructionsEditorTab

    def select_output_folder_path(self):
        options = QFileDialog.Options()
        folderPath = QFileDialog.getExistingDirectory(self, "Select Output Folder", "", options=options)
        if folderPath:
            self.outputFolderPathEdit.setText(folderPath)

    def toggle_mic(self):
        if self.is_mic_on:
            self.micButton.setIcon(self.mic_off_icon)
            self.speech_input_handler.stop_listening_from_mic()
        else:
            self.micButton.setIcon(self.mic_on_icon)
            self.speech_input_handler.start_listening_from_mic()
        self.is_mic_on = not self.is_mic_on

    def on_user_input(self, text):
        # Update the instructions editor with the hypothesis result
        if self.currentHypothesis:
            # Remove the last hypothesis before adding the new one
            currentText = self.newInstructionsEdit.toPlainText()
            updatedText = currentText.rsplit(self.currentHypothesis, 1)[0] + text
            self.newInstructionsEdit.setPlainText(updatedText)
        else:
            # If no previous hypothesis, just update the text
            self.newInstructionsEdit.insertPlainText(text)
        self.currentHypothesis = text

    def on_user_input_complete(self, text):
        # Replace the hypothesis with the complete result
        if self.currentHypothesis:
            # Remove the last hypothesis before adding the complete text
            currentText = self.newInstructionsEdit.toPlainText()
            updatedText = currentText.rsplit(self.currentHypothesis, 1)[0] + text + "\n"
            self.newInstructionsEdit.setPlainText(updatedText)
        else:
            # If no previous hypothesis, just append the text
            self.newInstructionsEdit.append(text)
        self.currentHypothesis = ""
        # Move the cursor to the end
        self.newInstructionsEdit.moveCursor(QtGui.QTextCursor.End)

    def check_instructions(self):
        threading.Thread(target=self._check_instructions, args=()).start()

    def _check_instructions(self):
        try:
            if not hasattr(self, 'instructions_reviewer'):
                raise Exception("Instruction reviewer is not available, check the system assistant settings")
            self.start_processing_signal.start_signal.emit(ActivityStatus.PROCESSING)
            # Combine instructions and check them
            instructions = self.newInstructionsEdit.toPlainText()
            self.reviewed_instructions = self.instructions_reviewer.process_messages(user_request=instructions, stream=False)
        except Exception as e:
            self.error_signal.error_signal.emit(str(e))
        finally:
            self.stop_processing_signal.stop_signal.emit(ActivityStatus.PROCESSING)

    def start_processing(self, status):
        self.status_bar.start_animation(status)

    def stop_processing(self, status):
        self.status_bar.stop_animation(status)
        try:
            # Open new dialog with the checked instructions
            contentDialog = ContentDisplayDialog(self.reviewed_instructions, "AI Reviewed Instructions", self)
            contentDialog.show()
        except Exception as e:
            logger.error(f"Error displaying reviewed instructions: {e}")

    def pre_load_assistant_config(self, name):
        # If an assistant_config is provided, pre-fill the fields
        self.assistant_config = AssistantConfigManager.get_instance().get_config(name)
        if self.assistant_config:
            self.nameEdit.setText(self.assistant_config.name)
            self.assistant_id = self.assistant_config.assistant_id
            self.instructionsEdit.setText(self.assistant_config.instructions)
            index = self.modelComboBox.findText(self.assistant_config.model)
            if index >= 0:
                # Set the current index of the combo box to the found index
                self.modelComboBox.setCurrentIndex(index)
            else:
                # add the model to the combo box
                self.modelComboBox.addItem(self.assistant_config.model)
                # Set the current index of the combo box to the last index
                self.modelComboBox.setCurrentIndex(self.modelComboBox.count() - 1)
            # Pre-select functions
            self.pre_select_functions()
            # Pre-select knowledge retrieval
            self.knowledge_retrieval = self.assistant_config.knowledge_retrieval
            # Pre-select code interpreter
            self.code_interpreter = self.assistant_config.code_interpreter
            # Pre-fill reference files
            for file_path in self.assistant_config.file_references:
                self.fileReferenceList.addItem(file_path)
            if self.assistant_type == "assistant":
                # Pre-fill knowledge files
                for file_path, file_id in self.assistant_config.knowledge_files.items():
                    self.knowledge_files_dict[file_path] = file_id
                    self.knowledgeFileList.addItem(file_path)
                # enable knowledge retrieval checkbox
                self.knowledgeRetrievalCheckBox.setChecked(self.knowledge_retrieval)
                # enable code interpreter checkbox
                self.codeInterpreterCheckBox.setChecked(self.code_interpreter)
                # Load only the temperature setting for assistant type
                text_completion_config = self.assistant_config.text_completion_config
                if text_completion_config:
                    self.useDefaultSettingsCheckBox.setChecked(False)
                    completion_settings = text_completion_config.to_dict()
                    temperature = completion_settings.get('temperature', 0.7) * 100
                else:
                    temperature = 70
                self.temperatureSlider.setValue(temperature)
            elif self.assistant_type == "chat_assistant":
                # pre-fill completion settings
                text_completion_config = self.assistant_config.text_completion_config

                # Check if text_completion_config exists, otherwise use default values directly
                if text_completion_config is not None:
                    self.useDefaultSettingsCheckBox.setChecked(False)
                    completion_settings = text_completion_config.to_dict()
                    frequency_penalty = completion_settings.get('frequency_penalty', 0) * 100
                    max_tokens = str(completion_settings.get('max_tokens', 100))
                    presence_penalty = completion_settings.get('presence_penalty', 0) * 100
                    response_format = completion_settings.get('response_format', 'text')
                    seed = str(completion_settings.get('seed', ''))  # Assuming '' represents no seed, as 'None' as a string might be misleading
                    temperature = completion_settings.get('temperature', 0.7) * 100
                    top_p = completion_settings.get('top_p', 0.1) * 100
                    max_text_messages = completion_settings.get('max_text_messages', '') # Assuming '' represents no limit
                else:
                    # Default values if text_completion_config is None
                    frequency_penalty = 0
                    max_tokens = "100"
                    presence_penalty = 0
                    response_format = "text"
                    seed = ""
                    temperature = 70
                    top_p = 10
                    max_text_messages = ""

                # Apply the values to UI elements
                self.frequencyPenaltySlider.setValue(frequency_penalty)
                self.maxTokensEdit.setText(max_tokens)
                self.presencePenaltySlider.setValue(presence_penalty)
                self.responseFormatComboBox.setCurrentText(response_format)
                self.seedEdit.setText(seed)
                self.temperatureSlider.setValue(temperature)
                self.topPSlider.setValue(top_p)
                self.maxMessagesEdit.setText(str(max_text_messages))

            # Set the output folder path if it's in the configuration
            output_folder_path = self.assistant_config.output_folder_path
            if output_folder_path:
                self.outputFolderPathEdit.setText(output_folder_path)

    def pre_select_functions(self):
        # Iterate over all selected functions
        for func in self.assistant_config.selected_functions:
            func_name = func['function']['name']

            # Find the category of each function
            function_configs =  self.function_config_manager.get_function_configs()
            for func_type, funcs in function_configs.items():
                if any(func_config.name == func_name for func_config in funcs):
                    # Check the corresponding checkbox
                    for checkBox in self.checkBoxes.get(func_type, []):
                        if checkBox.text() == func_name:
                            checkBox.setChecked(True)

    def create_function_section(self, layout, function_type, funcs):
        headerLabel = QLabel(f"{function_type.capitalize()} Functions:")
        layout.addWidget(headerLabel)

        self.checkBoxes[function_type] = []

        for func_config in funcs:
            checkBox = QCheckBox(func_config.name)
            checkBox.stateChanged.connect(lambda state, fc=func_config: self.handle_function_selection(state, fc))
            layout.addWidget(checkBox)
            self.checkBoxes[function_type].append(checkBox)

    def handle_function_selection(self, state, functionConfig):
        if state == Qt.CheckState.Checked.value:
            if functionConfig not in self.selected_functions:
                self.selected_functions.append(functionConfig.get_full_spec())
        elif state == Qt.CheckState.Unchecked.value:
            self.selected_functions = [f for f in self.selected_functions if f['function']['name'] != functionConfig.name]

    def add_reference_file(self):
        self.fileReferenceList.addItem(QFileDialog.getOpenFileName(None, "Select File", "", "All Files (*)")[0])

    def remove_reference_file(self):
        selected_items = self.fileReferenceList.selectedItems()
        for item in selected_items:
            self.fileReferenceList.takeItem(self.fileReferenceList.row(item))

    def add_knowledge_file(self):
        self.add_file(self.knowledge_files_dict, self.knowledgeFileList)

    def remove_knowledge_file(self):
        self.remove_file(self.knowledge_files_dict, self.knowledgeFileList)

    def add_file(self, file_dict, list_widget):
        options = QFileDialog.Options()
        filePath, _ = QFileDialog.getOpenFileName(None, "Select File", "", "All Files (*)", options=options)
        if filePath:
            if filePath in file_dict:
                QMessageBox.warning(None, "File Already Added", f"The file '{filePath}' is already in the list.")
            else:
                file_dict[filePath] = None  # Initialize the file ID as None or any default value you wish
                list_widget.addItem(filePath)

    def remove_file(self, file_dict, list_widget):
        selected_items = list_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            del file_dict[item.text()]
            list_widget.takeItem(list_widget.row(item))

    def save_configuration(self):
        if self.tabWidget.currentIndex() == 3:
            self.newInstructionsEdit.setPlainText(self.instructionsEdit.toPlainText())

        # Conditional setup for completion settings based on assistant_type
        max_text_messages = None
        completion_settings = None
        if self.assistant_type == "chat_assistant":
            if not self.useDefaultSettingsCheckBox.isChecked():
                completion_settings = {
                    'frequency_penalty': self.frequencyPenaltySlider.value() / 100,
                    'max_tokens': int(self.maxTokensEdit.text()) if self.maxTokensEdit.text().isdigit() else 100,  # Ensure it's an integer and provide a default
                    'presence_penalty': self.presencePenaltySlider.value() / 100,
                    'response_format': self.responseFormatComboBox.currentText(),
                    'seed': int(self.seedEdit.text()) if self.seedEdit.text().isdigit() else None,  # Ensure it's an integer or None
                    'temperature': self.temperatureSlider.value() / 100,
                    'top_p': self.topPSlider.value() / 100,
                    'max_text_messages': int(self.maxMessagesEdit.text()) if self.maxMessagesEdit.text().isdigit() else None  # Ensure it's an integer or None
                }
        elif self.assistant_type == "assistant":
            if not self.useDefaultSettingsCheckBox.isChecked():
                # For assistant type, save only the temperature setting
                completion_settings = {
                    'temperature': self.temperatureSlider.value() / 100,
                }
        config = {
            'name': self.nameEdit.text(),
            'instructions': self.instructionsEdit.toPlainText(),
            'model': self.modelComboBox.currentText(),
            # if is_create is True, then the assistant_id is empty
            'assistant_id': self.assistant_id if not self.is_create else '',
            'file_references': [self.fileReferenceList.item(i).text() for i in range(self.fileReferenceList.count())],
            'knowledge_files': self.knowledge_files_dict,
            'selected_functions': self.selected_functions,
            'knowledge_retrieval': self.knowledge_retrieval,
            'code_interpreter': self.code_interpreter,
            'output_folder_path': self.outputFolderPathEdit.text(),
            'ai_client_type': self.aiClientComboBox.currentText(),
            'assistant_type': self.assistant_type,
            'completion_settings': completion_settings
        }
        # if name, instructions, and model are empty, show an error message
        if not config['name'] or not config['instructions'] or not config['model']:
            QMessageBox.information(self, "Missing Fields", "Name, Instructions, and Model are required fields.")
            return
        assistant_config_json = json.dumps(config, indent=4)
        self.assistantConfigSubmitted.emit(assistant_config_json, self.aiClientComboBox.currentText(), self.assistant_type)


class ExportAssistantDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.assistant_config_manager = AssistantConfigManager.get_instance()
        self.setWindowTitle("Export Assistant")
        self.setLayout(QVBoxLayout())

        self.assistant_label = QLabel("Select Assistant:")
        self.layout().addWidget(self.assistant_label)

        self.assistant_combo = QComboBox()
        self.assistant_combo.addItems(self.get_assistant_names())
        self.layout().addWidget(self.assistant_combo)

        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export_assistant)
        self.layout().addWidget(self.export_button)
        # Set the initial size of the dialog to make it wider
        self.resize(400, 100)

    def get_assistant_names(self):
        assistant_names = self.assistant_config_manager.get_all_assistant_names()
        return assistant_names

    def export_assistant(self):
        assistant_name = self.assistant_combo.currentText()
        assistant_config = self.assistant_config_manager.get_config(assistant_name)
        export_path = os.path.join("export", assistant_name)
        config_path = os.path.join(export_path, "config")
        functions_path = os.path.join(export_path, "functions")

        # Ensure the directories exist
        os.makedirs(config_path, exist_ok=True)
        os.makedirs(functions_path, exist_ok=True)

        # Copy the required JSON files
        try:
            shutil.copyfile(f"config/{assistant_name}_assistant_config.yaml", os.path.join(config_path, f"{assistant_name}_assistant_config.yaml"))
            shutil.copyfile("config/function_error_specs.json", os.path.join(config_path, "function_error_specs.json"))
        except FileNotFoundError as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to copy configuration files: {e}")
            return

        # Check and copy user_functions.py if exists
        user_functions_src = os.path.join("functions", "user_functions.py")
        if os.path.exists(user_functions_src):
            shutil.copyfile(user_functions_src, os.path.join(functions_path, "user_functions.py"))

        # Read template, replace placeholder, and create main.py
        template_path = os.path.join("templates", "main_template.py")
        try:
            with open(template_path, "r") as template_file:
                template_content = template_file.read()

            main_content = template_content.replace("ASSISTANT_NAME", assistant_name)
            if assistant_config.assistant_type == "chat_assistant":
                main_content = main_content.replace("assistant_client", "chat_assistant_client")
                main_content = main_content.replace("AssistantClient", "ChatAssistantClient")

            with open(os.path.join(export_path, "main.py"), "w") as main_file:
                main_file.write(main_content)
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to create main.py: {e}")
            return

        QMessageBox.information(self, "Export Successful", f"Assistant '{assistant_name}' exported successfully to '{export_path}'.")
        self.accept()


class ContentDisplayDialog(QDialog):
    def __init__(self, content, title="Content Display", parent=None):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(400, 300)  # Set the size of the dialog

        layout = QVBoxLayout(self)

        self.contentEdit = QTextEdit()
        self.contentEdit.setReadOnly(True)  # Make it read-only
        self.contentEdit.setText(content)

        layout.addWidget(self.contentEdit)