# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6 import QtGui
from PySide6.QtWidgets import QDialog, QComboBox, QTabWidget, QSizePolicy, QScrollArea, QHBoxLayout, QWidget, QFileDialog, QListWidget, QLineEdit, QVBoxLayout, QPushButton, QLabel, QCheckBox, QTextEdit, QMessageBox
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QTextOption

import json, os, shutil

from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.function_config_manager import FunctionConfigManager
from azure.ai.assistant.management.ai_client_factory import AIClientType, AIClientFactory
from azure.ai.assistant.management.logger_module import logger
from gui.signals import UserInputSendSignal, UserInputSignal
from gui.speech_input_handler import SpeechInputHandler
#from gui.status_bar import ActivityStatus, StatusBar
from gui.utils import resource_path


class AssistantConfigDialog(QDialog):
    def __init__(
            self, 
            parent=None, 
            function_config_manager : FunctionConfigManager = None
    ):
        super().__init__(parent)
        self.main_window = parent
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
        if index == 1:
            self.newInstructionsEdit.setPlainText(self.instructionsEdit.toPlainText())

    def closeEvent(self, event):
        # Check if the microphone is on when closing the window
        if self.is_mic_on:
            self.toggle_mic()
        super(AssistantConfigDialog, self).closeEvent(event)

    def init_ui(self):
        self.setWindowTitle("Assistant Configuration")
        tabWidget = QTabWidget(self)
        tabWidget.currentChanged.connect(self.on_tab_changed)

        # Create Configuration tab
        configTab = self.create_config_tab()
        tabWidget.addTab(configTab, "Configuration")

        # Create Instructions Editor tab
        instructionsEditorTab = self.create_instructions_tab()
        tabWidget.addTab(instructionsEditorTab, "Instructions Editor")

        # Set the main layout
        mainLayout = QVBoxLayout(self)
        mainLayout.addWidget(tabWidget)
        self.setLayout(mainLayout)

        # Set the initial size of the dialog to make it wider
        self.resize(600, 900)

    def create_config_tab(self):
        configTab = QWidget()  # Configuration tab
        configLayout = QVBoxLayout(configTab)

        # AI client selection
        self.aiClientLabel = QLabel('AI Client:')
        self.aiClientComboBox = QComboBox()
        ai_client_type_names = [client_type.name for client_type in AIClientType]
        self.aiClientComboBox.addItems(ai_client_type_names)
        # Set the default to what is selected in the main window
        active_ai_client_type = self.main_window.get_active_ai_client_type()
        self.aiClientComboBox.setCurrentIndex(ai_client_type_names.index(active_ai_client_type))
        # Connect the client selection change signal to the slot
        self.aiClientComboBox.currentIndexChanged.connect(self.ai_client_selection_changed)
        configLayout.addWidget(self.aiClientLabel)
        configLayout.addWidget(self.aiClientComboBox)

        # Assistant selection combo box
        self.assistantLabel = QLabel('Assistant:')
        self.assistantComboBox = QComboBox()
        self.assistantComboBox.currentIndexChanged.connect(self.assistant_selection_changed)
        configLayout.addWidget(self.assistantLabel)
        configLayout.addWidget(self.assistantComboBox)

        self.nameLabel = QLabel('Name:')
        self.nameEdit = QLineEdit()
        self.nameEdit.setStyleSheet(
            "QLineEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}"
        )
        configLayout.addWidget(self.nameLabel)
        configLayout.addWidget(self.nameEdit)

       # Instructions - using QTextEdit for multi-line input
        self.instructionsLabel = QLabel('Instructions:')
        self.instructionsEdit = QTextEdit()  # Changed from QLineEdit to QTextEdit
        self.instructionsEdit.setStyleSheet(
            "QTextEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}"
        )
        self.instructionsEdit.setAcceptRichText(False)  # Optional: Only accept plain text
        self.instructionsEdit.setWordWrapMode(QTextOption.WordWrap)
        self.instructionsEdit.setMinimumHeight(100)  # Set a minimum height for a bigger text box

        configLayout.addWidget(self.instructionsLabel)
        configLayout.addWidget(self.instructionsEdit)

        # Model selection
        self.modelLabel = QLabel('Model:')
        self.modelComboBox = QComboBox()
        self.modelComboBox.setEditable(True)
        self.modelComboBox.setStyleSheet(
            "QLineEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}"
        )
        configLayout.addWidget(self.modelLabel)
        configLayout.addWidget(self.modelComboBox)

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
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "}"
        )
        configLayout.addWidget(self.scrollArea)

        # Knowledge Files
        self.knowledgeFileLabel = QLabel('Knowledge Files:')
        self.knowledgeFileList = QListWidget()  # List widget to display file paths
        self.knowledgeFileList.setStyleSheet(
            "QListWidget {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "}"
        )
        self.knowledgeFileButton = QPushButton('Add File...')
        self.knowledgeFileButton.clicked.connect(self.add_file)
        self.knowledgeFileRemoveButton = QPushButton('Remove File')
        self.knowledgeFileRemoveButton.clicked.connect(self.remove_file)
        
        fileButtonLayout = QHBoxLayout()
        fileButtonLayout.addWidget(self.knowledgeFileButton)
        fileButtonLayout.addWidget(self.knowledgeFileRemoveButton)

        configLayout.addWidget(self.knowledgeFileLabel)
        configLayout.addWidget(self.knowledgeFileList)
        configLayout.addLayout(fileButtonLayout)

        # Enable Knowledge Retrieval checkbox
        self.knowledgeRetrievalCheckBox = QCheckBox("Enable Knowledge Retrieval")
        self.knowledgeRetrievalCheckBox.stateChanged.connect(lambda state: setattr(self, 'knowledge_retrieval', state == Qt.CheckState.Checked.value))
        configLayout.addWidget(self.knowledgeRetrievalCheckBox)

        # Enable Code Interpreter checkbox
        self.codeInterpreterCheckBox = QCheckBox("Enable Code Interpreter")
        self.codeInterpreterCheckBox.stateChanged.connect(lambda state: setattr(self, 'code_interpreter', state == Qt.CheckState.Checked.value))
        configLayout.addWidget(self.codeInterpreterCheckBox)

        # Create as new assistant checkbox
        self.createAsNewCheckBox = QCheckBox("Create as New Assistant")
        self.createAsNewCheckBox.stateChanged.connect(lambda state: setattr(self, 'is_create', state == Qt.CheckState.Checked.value))
        configLayout.addWidget(self.createAsNewCheckBox)

        # Code Interpreter Output Folder Path
        self.codeInterpreterFolderPathLabel = QLabel('Output Folder Path For Files')
        self.codeInterpreterFolderPathEdit = QLineEdit()
        
        self.codeInterpreterFolderPathEdit.setText(self.default_output_folder_path)
        self.codeInterpreterFolderPathButton = QPushButton('Select Folder...')
        self.codeInterpreterFolderPathButton.clicked.connect(self.select_output_folder_path)

        # Adding the output folder path widgets to the layout
        codeInterpreterFolderPathLayout = QHBoxLayout()
        codeInterpreterFolderPathLayout.addWidget(self.codeInterpreterFolderPathEdit)
        codeInterpreterFolderPathLayout.addWidget(self.codeInterpreterFolderPathButton)
        
        configLayout.addWidget(self.codeInterpreterFolderPathLabel)
        configLayout.addLayout(codeInterpreterFolderPathLayout)

        # Save Button
        self.saveButton = QPushButton('Save Configuration')
        self.saveButton.clicked.connect(self.save_configuration)
        configLayout.addWidget(self.saveButton)

        self.ai_client_selection_changed()

        return configTab

    def ai_client_selection_changed(self):
        self.ai_client_type = AIClientType[self.aiClientComboBox.currentText()]
        assistant_names = AssistantConfigManager.get_instance().get_assistant_names_by_client_type(self.ai_client_type.name)

        self.assistantComboBox.clear()
        self.assistantComboBox.insertItem(0, "New Assistant")
        for assistant_name in assistant_names:
            self.assistantComboBox.addItem(assistant_name)
        self.assistantComboBox.setCurrentIndex(0)  # Set default to "New Assistant"

        self.modelComboBox.clear()
        try:
            models = AIClientFactory.get_instance().get_models_list(self.ai_client_type)
            for model in models:
                if self.ai_client_type == AIClientType.OPEN_AI:
                    self.modelComboBox.addItem(model.id)
                elif self.ai_client_type == AIClientType.AZURE_OPEN_AI:
                    self.modelComboBox.addItem(model)
        except Exception as e:
            logger.error(f"Error getting models from AI client: {e}")
        finally:
            if self.ai_client_type == AIClientType.OPEN_AI:
                self.modelComboBox.setToolTip("Select a model ID supported for assistant from the list")
            elif self.ai_client_type == AIClientType.AZURE_OPEN_AI:
                self.modelComboBox.setToolTip("Select a model deployment name from the Azure OpenAI resource")

    def assistant_selection_changed(self):
        self.reset_fields()
        selected_assistant = self.assistantComboBox.currentText()
        if selected_assistant == "New Assistant":
            self.is_create = True
            self.nameEdit.setEnabled(True)
            self.createAsNewCheckBox.setEnabled(False)
            self.codeInterpreterFolderPathEdit.setText(self.default_output_folder_path)
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
        self.knowledgeFileList.clear()
        # Reset all checkboxes in the function sections
        for function_type, checkBoxes in self.checkBoxes.items():
            for checkBox in checkBoxes:
                checkBox.setChecked(False)
        self.selected_functions = []
        self.knowledge_retrieval = False
        self.code_interpreter = False
        self.codeInterpreterCheckBox.setChecked(False)
        self.codeInterpreterFolderPathEdit.clear()
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
        #self.newInstructionsEdit.setFont(QtGui.QFont("Arial", 14))
        self.newInstructionsEdit.setText("1. Write Your Instructions Here")
        instructionsEditorLayout.addWidget(self.newInstructionsEdit)

        # 'Check Instructions' button
        checkInstructionsButton = QPushButton('Review with AI...')
        checkInstructionsButton.clicked.connect(self.check_instructions)
        instructionsEditorLayout.addWidget(checkInstructionsButton)

        # 'Save Instructions' button
        saveInstructionsButton = QPushButton('Save Instructions')
        saveInstructionsButton.clicked.connect(self.save_instructions)
        instructionsEditorLayout.addWidget(saveInstructionsButton)
        return instructionsEditorTab

    def select_output_folder_path(self):
        options = QFileDialog.Options()
        folderPath = QFileDialog.getExistingDirectory(self, "Select Output Folder", "", options=options)
        if folderPath:
            self.codeInterpreterFolderPathEdit.setText(folderPath)

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
        # Combine instructions and check them
        instructions = self.newInstructionsEdit.toPlainText()
        if not hasattr(self.main_window, 'instructions_checker') or self.main_window.instructions_checker is None:
            QMessageBox.critical(self, "Instructions Checker Not Found", "Instructions checker not found. Check chat completion settings.")
            return
        new_instructions = self.main_window.instructions_checker.check_instructions(instructions)
        # Open new dialog with the checked instructions
        contentDialog = ContentDisplayDialog(new_instructions, "AI Reviewed Instructions", self)
        contentDialog.show()

    def save_instructions(self):
        # Get instructions and set them to the instructionsEdit in the Configuration tab
        instructions = self.newInstructionsEdit.toPlainText()
        self.instructionsEdit.setText(instructions)

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
            # Pre-fill knowledge files
            for file_path, file_id in self.assistant_config.knowledge_files.items():
                self.knowledge_files_dict[file_path] = file_id
                self.knowledgeFileList.addItem(file_path)
            # Pre-select functions
            self.pre_select_functions()
            # Pre-select knowledge retrieval
            self.knowledge_retrieval = self.assistant_config.knowledge_retrieval
            # enable knowledge retrieval checkbox
            self.knowledgeRetrievalCheckBox.setChecked(self.knowledge_retrieval)
            # Pre-select code interpreter
            self.code_interpreter = self.assistant_config.code_interpreter
            # enable code interpreter checkbox
            self.codeInterpreterCheckBox.setChecked(self.code_interpreter)
            # Set the output folder path if it's in the configuration
            output_folder_path = self.assistant_config.output_folder_path
            if output_folder_path:
                self.codeInterpreterFolderPathEdit.setText(output_folder_path)

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

    def add_file(self):
        options = QFileDialog.Options()
        filePath, _ = QFileDialog.getOpenFileName(self, "Select File", "",
                                                "All Files (*)", options=options)
        if filePath:
            if filePath in self.knowledge_files_dict:
                QMessageBox.warning(self, "File Already Added", f"The file '{filePath}' is already in the list.")
            else:
                self.knowledge_files_dict[filePath] = None  # Initialize the file ID as None
                self.knowledgeFileList.addItem(filePath)

    def remove_file(self):
        selected_items = self.knowledgeFileList.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            del self.knowledge_files_dict[item.text()]
            self.knowledgeFileList.takeItem(self.knowledgeFileList.row(item))

    def save_configuration(self):
        config = {
            'name': self.nameEdit.text(),
            'instructions': self.instructionsEdit.toPlainText(),
            'model': self.modelComboBox.currentText(),
            # if is_create is True, then the assistant_id is empty
            'assistant_id': self.assistant_id if not self.is_create else '',
            'knowledge_files': self.knowledge_files_dict,
            'selected_functions': self.selected_functions,
            'knowledge_retrieval': self.knowledge_retrieval,
            'code_interpreter': self.code_interpreter,
            'output_folder_path': self.codeInterpreterFolderPathEdit.text(),
            'ai_client_type': self.aiClientComboBox.currentText()
        }
        # if name, instructions, and model are empty, show an error message
        if not config['name'] or not config['instructions'] or not config['model']:
            QMessageBox.information(self, "Missing Fields", "Name, Instructions, and Model are required fields.")
            return
        self.assistant_config_json = json.dumps(config, indent=4)
        self.accept()


class ExportAssistantDialog(QDialog):
    def __init__(self):
        super().__init__()
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
        assistant_names = AssistantConfigManager.get_instance().get_all_assistant_names()
        return assistant_names

    def export_assistant(self):
        assistant_name = self.assistant_combo.currentText()
        export_path = os.path.join("export", assistant_name)
        config_path = os.path.join(export_path, "config")
        functions_path = os.path.join(export_path, "functions")

        # Ensure the directories exist
        os.makedirs(config_path, exist_ok=True)
        os.makedirs(functions_path, exist_ok=True)

        # Copy the required JSON files
        try:
            shutil.copyfile(f"config/{assistant_name}_assistant_config.json", os.path.join(config_path, f"{assistant_name}_assistant_config.json"))
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