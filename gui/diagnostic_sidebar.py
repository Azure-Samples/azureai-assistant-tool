# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QBrush, QColor
from gui.signals import DiagnosticAddFunctionCallSignal, DiagnosticEndRunSignal
from gui.signals import DiagnosticStartRunSignal
from azure.ai.assistant.management.logger_module import logger
import os, json


class DiagnosticsSidebar(QWidget):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.setMinimumWidth(300)

        self.function_call_signal = DiagnosticAddFunctionCallSignal()
        self.function_call_signal.call_signal.connect(self.add_function_call)

        self.start_run_signal = DiagnosticStartRunSignal()
        self.start_run_signal.start_signal.connect(self.start_new_run)

        self.end_run_signal = DiagnosticEndRunSignal()
        self.end_run_signal.end_signal.connect(self.end_run)

        # Create a tree widget for displaying the function call tree
        self.functionCallTree = QTreeWidget(self)
        self.functionCallTree.setStyleSheet(
            "QTreeWidget {"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "  padding: 1px;"
            "}"
            "QTreeWidget::item {"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "  padding: 1px;"
            "}"
            "QTreeWidget::item:hover {"
            "  background-color: #e6e6e6;"
            "}"
        )
        self.functionCallTree.setHeaderLabels(["Diagnostics"])
        header_font = self.functionCallTree.header().font()
        header_font.setBold(True)
        self.functionCallTree.header().setFont(header_font)
        self.functionCallTree.setFont(QFont("Arial", 11))
        self.functionCallTree.setColumnWidth(0, 200)
        self.functionCallTree.header().setStretchLastSection(False)
        self.functionCallTree.header().setSectionResizeMode(QHeaderView.ResizeToContents)

        # Set the horizontal scrollbar policy
        self.functionCallTree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create a button for adding new threads
        self.saveButton = QPushButton("Save Diagnostics", self)
        self.saveButton.setFixedHeight(23)
        self.saveButton.setFont(QFont("Arial", 11))

        # Create the "Clear Diagnostics" button
        self.clearButton = QPushButton("Clear Diagnostics", self)
        self.clearButton.setFixedHeight(23)
        self.clearButton.setFont(QFont("Arial", 11))

        # Create a horizontal layout for the buttons
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.clearButton)
        buttonLayout.addWidget(self.saveButton)

        # Layout for the diagnostics sidebar
        layout = QVBoxLayout(self)
        layout.addWidget(self.functionCallTree)
        layout.addLayout(buttonLayout)

        # Set the style for the sidebar
        self.setStyleSheet(
            "QWidget {"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "  padding: 0px;"
            "}"
        )

        # Initially hide the diagnostics sidebar
        self.hide()

        # Create connections for the buttons
        self.saveButton.clicked.connect(self.save_diagnostics)
        self.clearButton.clicked.connect(self.clear_diagnostics)
        self.run_items = {}  # Dictionary to map run identifiers to their tree items

    def start_new_run(self, name, run_identifier, run_start_time, run_description):
        try:
            run_item = QTreeWidgetItem(self.functionCallTree)
            run_item.setText(0, f"Assistant: {name}")
            self.run_items[run_identifier] = run_item

            # Add the run identifier, start time, and description as children of the run
            run_identifier_item = QTreeWidgetItem(run_item)
            run_identifier_item.setText(0, f"Run Identifier: {run_identifier}")

            run_start_time_item = QTreeWidgetItem(run_item)
            run_start_time_item.setText(0, f"Run Start Time: {run_start_time}")

            description_item = QTreeWidgetItem(run_item)
            description_item.setText(0, f"Description: {run_description}")

            run_item.setExpanded(True)
            self.functionCallTree.scrollToItem(run_item, QAbstractItemView.PositionAtBottom)

        except Exception as e:
            logger.error(f"Error occurred during diagnostics run start: {e}")

    def add_function_call(self, assistant_name, run_identifier, function_name, function_args, function_response):
        try:
            current_run_item = self.run_items[run_identifier]

            function_call_item = QTreeWidgetItem(current_run_item)
            function_call_item.setText(0, f"Function call: {function_name}")

            arguments_item = QTreeWidgetItem(function_call_item)
            arguments_item.setText(0, f"Arguments: {function_args}")

            response_item = QTreeWidgetItem(function_call_item)
            response_json = json.loads(function_response)
            if "function_error" in response_json:
                response_item.setText(0, f"Response: {function_response}")
                response_item.setForeground(0, QBrush(QColor("red")))
            else:
                response_item.setText(0, "Response: OK")

            function_call_item.setExpanded(True)
            self.functionCallTree.scrollToItem(function_call_item, QAbstractItemView.PositionAtBottom)
        except Exception as e:
            logger.error(f"Error occurred during diagnostics function call addition: {e}")

    def end_run(self, assistant_name, run_identifier, run_end_time, messages):
        try:
            current_run_item = self.run_items[run_identifier]

            run_end_time_item = QTreeWidgetItem(current_run_item)
            run_end_time_item.setText(0, f"Run End Time: {run_end_time}")

            messages_item = QTreeWidgetItem(current_run_item)
            messages_item.setText(0, f"Messages: {messages}")

            current_run_item.setExpanded(True)
            self.functionCallTree.scrollToItem(messages_item, QAbstractItemView.PositionAtBottom)
        except Exception as e:
            logger.error(f"Error occurred during diagnostics run end: {e}")

    def collect_diagnostics_data(self):
        try:
            runs = []
            for i in range(self.functionCallTree.topLevelItemCount()):
                run_item = self.functionCallTree.topLevelItem(i)
                run_data = {
                    "assistant_name": run_item.text(0).split(":", 1)[1].strip(),
                    "run_identifier": "",
                    "run_start_time": "",
                    "run_description": "",
                    "function_calls": [],
                    "run_end_time": "",
                    "messages": ""
                }

                # Iterate through all children of the run
                for j in range(run_item.childCount()):
                    child_item = run_item.child(j)
                    text = child_item.text(0)

                    # Extract data based on child item's prefix
                    if text.startswith("Assistant:"):
                        run_data["assistant_name"] = text.split(":", 1)[1].strip()
                    elif text.startswith("Run Identifier:"):
                        run_data["run_identifier"] = text.split(":", 1)[1].strip()
                    elif text.startswith("Run Start Time:"):
                        run_data["run_start_time"] = text.split(":", 1)[1].strip()
                    elif text.startswith("Description:"):
                        run_data["run_description"] = text.split(":", 1)[1].strip()
                    elif text.startswith("Function call:"):
                        function_call_data = {"function_name": text.split(":", 1)[1].strip(), "arguments": "", "response": ""}
                        for k in range(child_item.childCount()):
                            sub_child_item = child_item.child(k)
                            sub_text = sub_child_item.text(0)
                            if sub_text.startswith("Arguments:"):
                                function_call_data["arguments"] = sub_text.split(":", 1)[1].strip()
                            elif sub_text.startswith("Response:"):
                                function_call_data["response"] = sub_text.split(":", 1)[1].strip()
                        run_data["function_calls"].append(function_call_data)
                    elif text.startswith("Run End Time:"):
                        run_data["run_end_time"] = text.split(":", 1)[1].strip()
                    elif text.startswith("Messages:"):
                        run_data["messages"] = text.split(":", 1)[1].strip()

                runs.append(run_data)
            return runs
        except Exception as e:
            logger.error(f"Error occurred during diagnostics data collection: {e}")
            return []

    def save_diagnostics(self):
        try:
            file_path = "diagnostics/diagnostics.json"
            dir_path = os.path.dirname(file_path)

            # Ensure the diagnostics directory exists
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

            # Collect new diagnostics data
            new_data = self.collect_diagnostics_data()

            existing_data = []
            # Check if the file exists and has content
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                with open(file_path, 'r') as file:
                    try:
                        existing_data = json.load(file)
                    except json.JSONDecodeError:
                        QMessageBox.warning(self, "Error", f"Error reading JSON from {file_path}. File might be corrupted.")
                        logger.error(f"Error reading JSON from {file_path}. File might be corrupted.")

            # Append only new and unique runs
            for run in new_data:
                if not self.run_exists(existing_data, run["run_identifier"]):
                    existing_data.append(run)

            # Write data back to the file
            with open(file_path, 'w') as file:
                json.dump(existing_data, file, indent=4)

        except IOError as io_error:
            QMessageBox.warning(self, "Error", f"An error occurred while saving the diagnostics: {io_error}")
            logger.error(f"Error occurred during diagnostics saving: {io_error}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An unexpected error occurred while saving the diagnostics: {e}")
            logger.error(f"Error occurred during diagnostics saving: {e}")

    def run_exists(self, existing_runs, new_run_identifier):
        """ Check if a run with the given identifier already exists in the data. """
        return any(run["run_identifier"] == new_run_identifier for run in existing_runs)

    def clear_diagnostics(self):
        try:
            self.functionCallTree.clear()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"An unexpected error occurred while clearing the diagnostics: {e}")
            logger.error(f"Error occurred during diagnostics clearing: {e}")
