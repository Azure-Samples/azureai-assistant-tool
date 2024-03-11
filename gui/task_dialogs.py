# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtWidgets import QDialog, QComboBox, QFrame, QTabWidget, QScrollArea, QHBoxLayout, QWidget, QFileDialog, QListWidget, QLineEdit, QVBoxLayout, QPushButton, QLabel, QDateTimeEdit, QTextEdit, QMessageBox
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QColor, QPalette, QIntValidator

import json, os, threading, ast

from azure.ai.assistant.management.ai_client_factory import AIClientType
from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.chat_assistant_client import ChatAssistantClient
from azure.ai.assistant.management.task import BasicTask, BatchTask, MultiTask
from azure.ai.assistant.management.task_manager import TaskManager
from azure.ai.assistant.management.logger_module import logger
from gui.signals import ErrorSignal, StartStatusAnimationSignal, StopStatusAnimationSignal
from gui.status_bar import ActivityStatus, StatusBar


class CreateTaskDialog(QDialog):
    def __init__(self, main_window, task_manager : TaskManager = None, config_folder="config"):
        super().__init__(main_window)

        self.main_window = main_window
        self.assistant_config_manager = main_window.assistant_config_manager
        self.task_manager = task_manager
        self.config_folder = config_folder
        self.request_list = []
        self.setWindowTitle("Create/Edit Task")
        self.setGeometry(100, 100, 700, 600)

        layout = QVBoxLayout()

        # Initialize task selection dropdowns for each tab
        self.basic_task_selector = self.create_task_selector("Basic")
        self.batch_task_selector = self.create_task_selector("Batch")
        self.multi_task_selector = self.create_task_selector("Multi")

        # Set up tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        basic_tab = self.create_basic_tab()
        batch_tab = self.create_batch_tab()
        multi_tab = self.create_multi_tab()

        # Add tabs
        self.tabs.addTab(basic_tab, "Basic")
        self.tabs.addTab(batch_tab, "Batch")
        self.tabs.addTab(multi_tab, "Multi")
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Create the Save and Remove Task buttons
        save_task_btn = QPushButton("Save")
        remove_task_btn = QPushButton("Remove")

        # Connect buttons to their respective methods
        save_task_btn.clicked.connect(self.save_task)
        remove_task_btn.clicked.connect(self.remove_task)

        # Create a horizontal layout and add both buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(save_task_btn)
        buttons_layout.addWidget(remove_task_btn)

        # Add the buttons layout to the main layout
        layout.addLayout(buttons_layout)

        # setup status bar
        self.status_bar = StatusBar(self)
        layout.addWidget(self.status_bar.get_widget())
        self.setLayout(layout)

        self.start_processing_signal = StartStatusAnimationSignal()
        self.stop_processing_signal = StopStatusAnimationSignal()
        self.error_signal = ErrorSignal()
        self.start_processing_signal.start_signal.connect(self.start_processing)
        self.stop_processing_signal.stop_signal.connect(self.stop_processing)
        self.error_signal.error_signal.connect(lambda error_message: QMessageBox.warning(self, "Error", error_message))
        self.basic_task_selector.currentIndexChanged.connect(lambda: self.on_task_selected(self.basic_task_selector))
        self.batch_task_selector.currentIndexChanged.connect(lambda: self.on_task_selected(self.batch_task_selector))
        self.multi_task_selector.currentIndexChanged.connect(lambda: self.on_task_selected(self.multi_task_selector))
        self.init_task_assistant()

    def init_task_assistant(self):
        task_request_config : AssistantConfig = self.assistant_config_manager.get_config("TaskRequestsCreator")

        try:
            ai_client_type : AIClientType = self.main_window.active_ai_client_type
            if ai_client_type is None:
                QMessageBox.warning(self, "Warning", f"Selected active AI client is not initialized properly, task request generation may not work as expected.")
            else:
                # update the ai_client_type in the config_json
                task_request_config.ai_client_type = ai_client_type.name

            model = task_request_config.model
            if not model:
                logger.warning("Model not found in the function spec assistant config, using the system assistant model.")
                model = self.main_window.system_assistant_model
                task_request_config.model = model
            if not model:
                QMessageBox.warning(self, "Error", "Model not found in the function spec assistant config, please check the system settings.")
                return

            self.task_requests_creator = ChatAssistantClient.from_config(task_request_config)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while initializing the function assistants, check the system settings: {e}")

    def start_processing(self, status):
        self.status_bar.start_animation(status)

    def stop_processing(self, status):
        self.status_bar.stop_animation(status)
        self.requests_list.clear()
        try:
            # Convert the string representation of the list back to a list
            actual_list = ast.literal_eval(self.request_list)
            # Join the list items into a single string with each item on a new line
            requests_text = "\n".join(actual_list)
            self.requests_list.setText(requests_text)
        except Exception as e:
            self.requests_list.setText(self.request_list)
        
    def on_tab_changed(self, index):
        # Update dropdowns based on the selected tab
        if index == 0:  # Basic Tab
            self.load_and_display_tasks(self.basic_task_selector, "Basic")
        elif index == 1:  # Batch Tab
            self.load_and_display_tasks(self.batch_task_selector, "Batch")
        elif index == 2:  # Multi Tab
            self.load_and_display_tasks(self.basic_task_selector, "Multi")

    def on_task_selected(self, task_selector):
        task = task_selector.currentData()
        active_tab_index = self.tabs.currentIndex()

        if task:
            # Populate fields with selected task's details
            # Disable the task name input to prevent editing
            if active_tab_index == 0:  # Basic Tab
                self.task_name_input.setText(task['name'])
                self.user_request_basic.setText(task['user_request'])
            elif active_tab_index == 1:  # Batch Tab
                self.batch_name_input.setText(task['name'])
                self.src_folders_list.clear()
                for folder in task['input_folders']:
                    self.src_folders_list.addItem(folder)
                self.requests_list.setText('\n'.join(task['requests']))
            elif active_tab_index == 2:  # Multi Tab
                self.assistant_selection.setEnabled(False)
                self.add_button.setEnabled(False)
                self.multi_name_input.setText(task['name'])
                self.clear_assistants()  # Clear existing assistants before populating new ones
                for request in task['requests']:
                    assistant_layout = QHBoxLayout()
                    assistant_label = QLabel(f"{request['assistant']}:")
                    assistant_request = QLineEdit()
                    assistant_request.setText(request['task'])

                    assistant_layout.addWidget(assistant_label)
                    assistant_layout.addWidget(assistant_request)

                    # Add new assistant at the end of the layout
                    self.assistants_layout.insertLayout(self.assistants_layout.count() - 1, assistant_layout)
        else:
            # "New Task" selected, enable input fields for new task details
            if active_tab_index == 0:
                self.task_name_input.clear()
                self.user_request_basic.clear()
            elif active_tab_index == 1:
                self.batch_name_input.clear()
                self.user_request_batch.clear()
                self.src_folders_list.clear()
                self.requests_list.clear()
            elif active_tab_index == 2:
                self.assistant_selection.setEnabled(True)
                self.add_button.setEnabled(True)
                self.multi_name_input.clear()
                self.clear_assistants()

    def clear_assistants(self):
        # Remove all widgets and layouts in the assistants layout
        while self.assistants_layout.count() > 0:
            layout_item = self.assistants_layout.takeAt(0)

            # If the item is a widget, remove it
            if layout_item.widget():
                layout_item.widget().deleteLater()

            # If the item is a layout, recursively clear it and then delete it
            elif layout_item.layout():
                self.clear_layout(layout_item.layout())
                layout_item.layout().deleteLater()
        
        # Re-add stretch to ensure proper alignment
        self.assistants_layout.addStretch(1)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                self.clear_layout(item.layout())

    def create_task_selector(self, task_type):
        task_selector = QComboBox()
        self.load_and_display_tasks(task_selector, task_type)
        return task_selector

    def load_and_display_tasks(self, task_selector, task_type):
        tasks = self.load_tasks()
        task_selector.clear()
        task_selector.addItem("New Task", None)  # Default option for creating a new task
        for task in tasks:
            if task['type'] == task_type:
                task_selector.addItem(task['name'], task)

    def create_basic_tab(self):
        basic_tab = QWidget()
        basic_layout = QVBoxLayout()
        basic_layout.addWidget(self.basic_task_selector)
        self.task_name_input = QLineEdit()
        self.task_name_input.setStyleSheet(
            "QLineEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}"
        )
        self.user_request_basic = QTextEdit()
        self.user_request_basic.setStyleSheet(
            "QTextEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}"
        )
        basic_layout.addWidget(QLabel("Task Name:"))
        basic_layout.addWidget(self.task_name_input)
        basic_layout.addWidget(QLabel("User Request:"))
        basic_layout.addWidget(self.user_request_basic)
        basic_tab.setLayout(basic_layout)
        return basic_tab

    def create_batch_tab(self):
        batch_tab = QWidget()
        batch_layout = QVBoxLayout()
        batch_layout.addWidget(self.batch_task_selector)
        self.batch_name_input = QLineEdit()
        self.batch_name_input.setStyleSheet(
            "QLineEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}"
        )
        self.src_folders_list = QListWidget()
        self.src_folders_list.setMaximumHeight(100)
        self.src_folders_list.setStyleSheet(
            "QListWidget {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}"
        )
        add_remove_layout = QHBoxLayout()
        add_src_folder_btn = QPushButton("Add Folder...")
        remove_src_folder_btn = QPushButton("Remove Folder")
        add_remove_layout.addWidget(add_src_folder_btn)
        add_remove_layout.addWidget(remove_src_folder_btn)
        add_src_folder_btn.clicked.connect(self.add_folder)
        remove_src_folder_btn.clicked.connect(self.remove_folder)
        self.user_request_batch = QTextEdit()
        self.user_request_batch.setStyleSheet(
            "QTextEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}"
        )
        self.user_request_batch.setMaximumHeight(50)
        self.requests_list = QTextEdit()
        self.requests_list.setStyleSheet(
            "QTextEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}"
        )
        generate_requests_btn = QPushButton("Generate Requests with AI...")
        generate_requests_btn.clicked.connect(self.generate_requests)

        batch_layout.addWidget(QLabel("Task Name:"))
        batch_layout.addWidget(self.batch_name_input)
        batch_layout.addWidget(QLabel("Source Folders:"))
        batch_layout.addWidget(self.src_folders_list)
        batch_layout.addLayout(add_remove_layout)
        batch_layout.addWidget(QLabel("User Request:"))
        batch_layout.addWidget(self.user_request_batch)
        batch_layout.addWidget(generate_requests_btn)
        batch_layout.addWidget(QLabel("Generated Requests"))
        batch_layout.addWidget(self.requests_list)

        batch_tab.setLayout(batch_layout)
        return batch_tab

    def create_multi_tab(self):
        multi_tab = QWidget()
        self.multi_tab_layout = QVBoxLayout()
        self.multi_tab_layout.addWidget(self.multi_task_selector)

        self.multi_name_input = QLineEdit()
        self.multi_name_input.setStyleSheet(
            "QLineEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}"
        )
        # ComboBox and button at the top
        top_layout = QHBoxLayout()
        assistants = self.main_window.assistant_config_manager.get_all_assistant_names()
        self.assistant_selection = QComboBox()
        self.assistant_selection.addItems(assistants)
        self.add_button = QPushButton('Add Selected Assistant')
        self.add_button.clicked.connect(self.add_selected_assistant)
        top_layout.addWidget(self.assistant_selection)
        top_layout.addWidget(self.add_button)

        self.multi_tab_layout.addLayout(top_layout)

        # Scroll Area for assistants
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.assistant_list_widget = QWidget()
        self.assistants_layout = QVBoxLayout(self.assistant_list_widget)
        self.assistants_layout.setSpacing(5)  # Reduced spacing between assistants
        self.scroll_area.setWidget(self.assistant_list_widget)

        # Add a stretch to push all items to the top
        self.assistants_layout.addStretch(1)

        self.multi_tab_layout.addWidget(QLabel("Task Name:"))
        self.multi_tab_layout.addWidget(self.multi_name_input)
        self.multi_tab_layout.addWidget(self.scroll_area)
        multi_tab.setLayout(self.multi_tab_layout)

        return multi_tab

    def add_selected_assistant(self):
        selected_assistant = self.assistant_selection.currentText()
        assistant_layout = QHBoxLayout()
        assistant_label = QLabel(f"{selected_assistant}:")
        assistant_request = QLineEdit()
        assistant_request.setPlaceholderText("Enter request for " + selected_assistant)
        remove_button = QPushButton('Remove')
        remove_button.clicked.connect(lambda: self.remove_assistant(assistant_layout))
        assistant_layout.addWidget(assistant_label)
        assistant_layout.addWidget(assistant_request)
        assistant_layout.addWidget(remove_button)
        self.assistants_layout.insertLayout(self.assistants_layout.count() - 1, assistant_layout)

    def remove_assistant(self, assistant_layout):
        # Remove all widgets in the layout
        while assistant_layout.count():
            item = assistant_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        # Remove the layout itself
        self.assistants_layout.removeItem(assistant_layout)

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.src_folders_list.addItem(folder_path)

    def remove_folder(self):
        selected_item = self.src_folders_list.currentItem()
        if selected_item:
            row = self.src_folders_list.row(selected_item)
            self.src_folders_list.takeItem(row)

    def load_tasks(self):
        file_path = os.path.join("config", "assistant_tasks.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                return json.load(file)
        return []

    def generate_requests(self):
        threading.Thread(target=self._generate_requests, args=()).start()
    
    def _generate_requests(self):
        try:
            self.start_processing_signal.start_signal.emit(ActivityStatus.PROCESSING)
            if self.src_folders_list.count() == 0:
                error_message = "Please add at least one source folder."
                raise Exception(error_message)

            user_request = self.user_request_batch.toPlainText()
            if not user_request:
                error_message = "Please enter a request."
                raise Exception(error_message)

            folders_list = [self.src_folders_list.item(i).text() for i in range(self.src_folders_list.count())]
            user_request = user_request + " Input folders:" + " ".join(folders_list)
            self.request_list = self.task_requests_creator.process_messages(user_request=user_request, stream=False, temperature=0.2)

        except Exception as e:
            self.error_signal.error_signal.emit(str(e))

        finally:
            self.stop_processing_signal.stop_signal.emit(ActivityStatus.PROCESSING)

    def save_task(self):
        try:
            active_tab_index = self.tabs.currentIndex()

            # include all to selected task basic, batch and multi tab
            selected_task = (self.basic_task_selector.currentData() 
                            if active_tab_index == 0 else 
                            (self.batch_task_selector.currentData() 
                            if active_tab_index == 1 else 
                            self.multi_task_selector.currentData()))

            if active_tab_index == 0:
                task_name = self.task_name_input.text()
            elif active_tab_index == 1:
                task_name = self.batch_name_input.text()
            else:
                task_name = self.multi_name_input.text()

            if not task_name:
                QMessageBox.warning(self, "Task Name Required", "Please enter a name for the task.")
                return

            if selected_task is None:
                if active_tab_index == 0:  # Basic Task
                    user_request = self.user_request_basic.toPlainText()
                    new_task = self.task_manager.create_basic_task(user_request)
                elif active_tab_index == 1:  # Batch Task
                    requests_text = self.requests_list.toPlainText()
                    requests = requests_text.split('\n')  # Split requests by newline
                    new_task = self.task_manager.create_batch_task(requests)
                elif active_tab_index == 2:  # Multi Task
                    requests = []
                    for i in range(self.assistants_layout.count() - 1):  # Exclude the stretch at the end
                        layout = self.assistants_layout.itemAt(i).layout()
                        if isinstance(layout, QHBoxLayout):
                            assistant_label = layout.itemAt(0).widget().text().rstrip(':')
                            assistant_request = layout.itemAt(1).widget().text()
                            requests.append({"assistant": assistant_label, "task": assistant_request})
                    new_task = self.task_manager.create_multi_task(requests)
                self.add_new_task_to_file(task_name, new_task)
            else:
                self.update_existing_task(selected_task['id'])

            self.refresh_dropdowns()
            QMessageBox.information(self, "Success", "Task saved successfully.")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while saving the task: {e}")

    def update_existing_task(self, task_id):
        tasks = self.load_tasks()
        for task in tasks:
            if task['id'] == task_id:
                if task['type'] == "Basic":
                    task['name'] = self.task_name_input.text()
                    task['user_request'] = self.user_request_basic.toPlainText()
                elif task['type'] == "Batch":
                    task['name'] = self.batch_name_input.text()
                    task['requests'] = self.requests_list.toPlainText().split('\n')
                    task['input_folders'] = [self.src_folders_list.item(i).text() for i in range(self.src_folders_list.count())]
                elif task['type'] == "Multi":
                    task['name'] = self.multi_name_input.text()
                    requests = []
                    for i in range(self.assistants_layout.count() - 1):  # Exclude the stretch at the end
                        layout = self.assistants_layout.itemAt(i).layout()
                        if isinstance(layout, QHBoxLayout):
                            assistant_label = layout.itemAt(0).widget().text().rstrip(':')
                            assistant_request = layout.itemAt(1).widget().text()
                            requests.append({"assistant": assistant_label, "task": assistant_request})
                    task['requests'] = requests
                break
        self.save_tasks_to_file(tasks)

    def add_new_task_to_file(self, task_name, task):
        task_data = {
            "id": str(task.id),
            "name": task_name,
            "type": "Basic" if isinstance(task, BasicTask) else ("Batch" if isinstance(task, BatchTask) else "Multi")
        }

        if isinstance(task, BasicTask):
            task_data["user_request"] = task.user_request
        elif isinstance(task, BatchTask):
            task_data["requests"] = task.requests
            task_data["input_folders"] = [self.src_folders_list.item(i).text() for i in range(self.src_folders_list.count())]
        elif isinstance(task, MultiTask):
            task_data["requests"] = [{"assistant": req["assistant"], "task": req["task"]} for req in task.requests]

        tasks = self.load_tasks()
        tasks.append(task_data)
        self.save_tasks_to_file(tasks)

    def save_tasks_to_file(self, tasks):
        file_path = os.path.join(self.config_folder, "assistant_tasks.json")
        with open(file_path, "w") as file:
            json.dump(tasks, file, indent=4)

    def remove_task(self):
        try:
            active_tab_index = self.tabs.currentIndex()
            selected_task = (self.basic_task_selector.currentData() 
                            if active_tab_index == 0 else
                            (self.batch_task_selector.currentData()
                            if active_tab_index == 1 else
                            self.multi_task_selector.currentData()))

            if selected_task is None:
                QMessageBox.warning(self, "Selection Required", "Please select a task to remove.")
                return

            reply = QMessageBox.question(self, 'Confirm Removal', 'Are you sure you want to remove this task?',
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.delete_task_from_file(selected_task['id'])
                if active_tab_index == 0:
                    self.load_and_display_tasks(self.basic_task_selector, "Basic")
                elif active_tab_index == 1:
                    self.load_and_display_tasks(self.batch_task_selector, "Batch")
                elif active_tab_index == 2:
                    self.load_and_display_tasks(self.multi_task_selector, "Multi")
                self.refresh_dropdowns()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while removing the task: {e}")

    def delete_task_from_file(self, task_id):
        tasks = self.load_tasks()
        tasks = [task for task in tasks if task['id'] != task_id]
        self.save_tasks_to_file(tasks)

    def refresh_dropdowns(self):
        self.load_and_display_tasks(self.basic_task_selector, "Basic")
        self.load_and_display_tasks(self.batch_task_selector, "Batch")
        self.load_and_display_tasks(self.multi_task_selector, "Multi")


class ScheduleTaskDialog(QDialog):
    def __init__(self, main_window, task_manager : TaskManager, config_folder="config"):
        super().__init__(main_window)

        self.main_window = main_window
        self.task_manager = task_manager
        self.config_folder = config_folder

        self.setWindowTitle("Schedule Task")
        self.setGeometry(100, 100, 400, 200)

        layout = QVBoxLayout()

        # Task selection
        self.task_selection = QComboBox()
        self.load_tasks_into_dropdown()
        self.task_selection.currentIndexChanged.connect(self.on_task_selection_changed)
        layout.addWidget(QLabel("Select Task:"))
        layout.addWidget(self.task_selection)

        # Assistant selection
        self.assistant_selection = QComboBox()
        ai_client_type = self.main_window.active_ai_client_type
        assistants = self.main_window.assistant_config_manager.get_assistant_names_by_client_type(ai_client_type.name)
        self.assistant_selection.addItems(assistants)
        layout.addWidget(QLabel("Select Assistant:"))
        layout.addWidget(self.assistant_selection)

        # Schedule Time
        self.schedule_time = QDateTimeEdit()
        self.schedule_time.setDateTime(QDateTime.currentDateTime())  # Set to current date and time
        self.schedule_time.setDisplayFormat("yyyy-MM-dd HH:mm:ss")  # Set display format
        self.schedule_time.setMinimumDateTime(QDateTime.currentDateTime())  # Set minimum to current date and time
        self.schedule_time.setMaximumDateTime(QDateTime.currentDateTime().addYears(1))  # Set maximum to one year from now

        layout.addWidget(QLabel("Schedule Time:"))
        layout.addWidget(self.schedule_time)

        # Recurrence Interval
        self.recurrence_interval_input = QLineEdit()
        self.recurrence_interval_input.setValidator(QIntValidator(0, 1000000))  # Validate as an integer
        layout.addWidget(QLabel("Recurrence Interval (seconds):"))
        layout.addWidget(self.recurrence_interval_input)

        # Recurrence Count
        self.recurrence_count_input = QLineEdit()
        self.recurrence_count_input.setValidator(QIntValidator(1, 1000))  # Validate as an integer, minimum 1
        layout.addWidget(QLabel("Recurrence Count:"))
        layout.addWidget(self.recurrence_count_input)

        # Schedule/Run Now buttons
        buttons_layout = QHBoxLayout()
        self.schedule_button = QPushButton("Schedule")
        self.run_now_button = QPushButton("Run Now")
        self.schedule_button.clicked.connect(self.schedule_task)
        self.run_now_button.clicked.connect(self.run_task_now)
        buttons_layout.addWidget(self.schedule_button)
        buttons_layout.addWidget(self.run_now_button)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def on_task_selection_changed(self):
        task_id = self.task_selection.currentData()  # This is the selected task's id
        if task_id in self.tasks_by_id:
            task = self.tasks_by_id[task_id]  # Get the task object by id
            # Check the type of the task
            if task['type'] == "Multi":
                self.assistant_selection.setEnabled(False)
            else:
                self.assistant_selection.setEnabled(True)

    def load_tasks_into_dropdown(self):
        self.tasks_by_id = {}
        file_path = os.path.join(self.config_folder, "assistant_tasks.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                tasks = json.load(file)
            for task in tasks:
                # Assuming each task has a 'name' and 'id' attribute
                self.task_selection.addItem(task['name'], task['id'])
                self.tasks_by_id[task['id']] = task

        # If the file doesn't exist or there are no tasks, do nothing

    def schedule_task(self):
        selected_task_id = self.task_selection.currentData()
        selected_assistant = self.assistant_selection.currentText()
        # Convert to Python datetime object
        schedule_time = self.schedule_time.dateTime().toPython()

        # Use 0 as a default value for recurrence_interval
        recurrence_interval = int(self.recurrence_interval_input.text()) if self.recurrence_interval_input.text() else 0
        # Use 1 as a default value for recurrence_count to indicate a single execution
        recurrence_count = int(self.recurrence_count_input.text()) if self.recurrence_count_input.text() else 1

        task = self.get_task_by_id(selected_task_id)
        if task:
            self.task_manager.schedule_task(task, selected_assistant, start_time=schedule_time, interval_seconds=recurrence_interval, recurrence_count=recurrence_count)
            QMessageBox.information(self, "Scheduled", "The task has been scheduled at time: " + str(schedule_time))
        else:
            QMessageBox.warning(self, "Task Not Found", "Selected task not found.")

    def run_task_now(self):
        selected_task_id = self.task_selection.currentData()
        selected_assistant = self.assistant_selection.currentText()

        # Use 0 as a default value for recurrence_interval
        recurrence_interval = int(self.recurrence_interval_input.text()) if self.recurrence_interval_input.text() else 0
        # Use 1 as a default value for recurrence_count to indicate a single execution
        recurrence_count = int(self.recurrence_count_input.text()) if self.recurrence_count_input.text() else 1

        task = self.get_task_by_id(selected_task_id)
        if task:
            self.task_manager.schedule_task(task, selected_assistant, interval_seconds=recurrence_interval, recurrence_count=recurrence_count)
            #QMessageBox.information(self, "Executed", "The task is being executed now.")
        else:
            QMessageBox.warning(self, "Task Not Found", "Selected task not found.")

    def get_task_by_id(self, task_id):
        file_path = os.path.join(self.config_folder, "assistant_tasks.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                tasks = json.load(file)
            for task in tasks:
                if task['id'] == task_id:
                    if task['type'] == "Basic":
                        return self.task_manager.create_basic_task(task['user_request'])
                    elif task['type'] == "Batch":
                        return self.task_manager.create_batch_task(task['requests'])
                    elif task['type'] == "Multi":
                        return self.task_manager.create_multi_task(task['requests'])
        return None


class ShowScheduledTasksDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Scheduled Tasks")
        self.setGeometry(100, 100, 800, 500)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Scroll area for tasks
        scroll_area = QScrollArea()
        scroll_area.setStyleSheet(
            "QScrollArea {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "}"
        )
        scroll_area.setWidgetResizable(True)
        scroll_area_widget = QWidget()
        scroll_area.setWidget(scroll_area_widget)
        scroll_layout = QVBoxLayout(scroll_area_widget)

        # Set white background for scroll area
        palette = QPalette()
        palette.setColor(QPalette.Background, Qt.white)
        scroll_area.setAutoFillBackground(True)
        scroll_area.setPalette(palette)

        self.load_tasks(scroll_layout)

        main_layout.addWidget(scroll_area)

    def load_tasks(self, layout):
        tasks = [("Task 1", "Running"), 
                 ("Task 2", "Scheduled"), 
                 ("Task 3", "Completed"),
                 ("Task 4", "Running"), 
                 ("Task 5", "Scheduled"), 
                 ("Task 6", "Completed")]
        
        # Minimum height for each task frame
        max_height_per_task = 40

        for task_name, state in tasks:
            task_frame = QFrame()
            task_frame.setFrameShape(QFrame.StyledPanel)
            task_frame.setPalette(QPalette(QColor(255, 255, 255)))
            task_frame.setAutoFillBackground(True)
            task_frame.setMaximumHeight(max_height_per_task)
            task_layout = QHBoxLayout(task_frame)

            # Task Name and State
            task_label = QLabel(task_name)
            state_label = QLabel(state)
            task_layout.addWidget(task_label)
            task_layout.addWidget(state_label)

            # Action buttons
            start_btn = QPushButton("Start")
            cancel_btn = QPushButton("Stop/Cancel")
            start_btn.clicked.connect(lambda _, name=task_name: self.start_task(name))
            cancel_btn.clicked.connect(lambda _, name=task_name: self.cancel_task(name))
            task_layout.addWidget(start_btn)
            task_layout.addWidget(cancel_btn)

            layout.addWidget(task_frame)

        # Optionally, add extra space at the end
        layout.addStretch()

    def start_task(self, task_name):
        logger.info(f"Starting {task_name}")

    def cancel_task(self, task_name):
        logger.info(f"Stop/Cancelling {task_name}")