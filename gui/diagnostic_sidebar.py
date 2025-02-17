# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont, QBrush, QColor

import os, json

from azure.ai.assistant.management.logger_module import logger
from gui.signals import DiagnosticAddFunctionCallSignal, DiagnosticEndRunSignal
from gui.signals import DiagnosticStartRunSignal


class DiagnosticAddRunStepsSignal(QObject):
    steps_signal = Signal(str, list)  # run_identifier, run_steps_list


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

        self.add_run_steps_signal = DiagnosticAddRunStepsSignal()
        self.add_run_steps_signal.steps_signal.connect(self.add_run_steps)

        # Create a tree widget for displaying the function (and other) diagnostics
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
        self.functionCallTree.setHeaderLabels(["Run View"])
        header_font = self.functionCallTree.header().font()
        header_font.setBold(True)
        self.functionCallTree.header().setFont(header_font)
        self.functionCallTree.setFont(QFont("Arial", 11))
        self.functionCallTree.setColumnWidth(0, 200)
        self.functionCallTree.header().setStretchLastSection(False)
        self.functionCallTree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.functionCallTree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create buttons
        self.saveButton = QPushButton("Save Diagnostics", self)
        self.saveButton.setFixedHeight(23)
        self.saveButton.setFont(QFont("Arial", 11))

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

        # Set the style, hide initially, wire up buttons
        self.setStyleSheet(
            "QWidget {"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "  padding: 0px;"
            "}"
        )
        self.hide()

        self.saveButton.clicked.connect(self.save_diagnostics)
        self.clearButton.clicked.connect(self.clear_diagnostics)

        # This maps run identifiers to their top-level QTreeWidgetItems
        self.run_items = {}

    def start_new_run(self, name, run_identifier, run_start_time, run_description):
        try:
            run_item = QTreeWidgetItem(self.functionCallTree)
            run_item.setText(0, f"Assistant: {name}")
            self.run_items[run_identifier] = run_item

            # Additional sub-items
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
            current_run_item = self.run_items.get(run_identifier)
            if not current_run_item:
                return  # If no run item yet, do nothing

            function_call_item = QTreeWidgetItem(current_run_item)
            function_call_item.setText(0, f"Function call: {function_name}")

            arguments_item = QTreeWidgetItem(function_call_item)
            arguments_item.setText(0, f"Arguments: {function_args}")

            response_item = QTreeWidgetItem(function_call_item)
            try:
                response_json = json.loads(function_response)
                if "function_error" in response_json:
                    response_item.setText(0, f"Response: {function_response}")
                    response_item.setForeground(0, QBrush(QColor("red")))
                else:
                    response_item.setText(0, "Response: OK")
            except json.JSONDecodeError:
                # If the response isn't valid JSON, just store raw
                response_item.setText(0, f"Response: {function_response}")

            function_call_item.setExpanded(True)
            self.functionCallTree.scrollToItem(function_call_item, QAbstractItemView.PositionAtBottom)
        except Exception as e:
            logger.error(f"Error occurred during diagnostics function call addition: {e}")

    def end_run(self, assistant_name, run_identifier, run_end_time, messages):
        try:
            current_run_item = self.run_items.get(run_identifier)
            if not current_run_item:
                return

            run_end_time_item = QTreeWidgetItem(current_run_item)
            run_end_time_item.setText(0, f"Run End Time: {run_end_time}")

            messages_item = QTreeWidgetItem(current_run_item)
            messages_item.setText(0, f"Messages: {messages}")

            current_run_item.setExpanded(True)
            self.functionCallTree.scrollToItem(messages_item, QAbstractItemView.PositionAtBottom)
        except Exception as e:
            logger.error(f"Error occurred during diagnostics run end: {e}")

    def add_run_steps(self, run_identifier, steps):
        try:
            current_run_item = self.run_items.get(run_identifier)
            if not current_run_item:
                return

            # Create a parent item for "Steps," so user can collapse or expand them
            steps_parent_item = QTreeWidgetItem(current_run_item)
            steps_parent_item.setText(0, "Steps")

            for step in steps:
                step_item = QTreeWidgetItem(steps_parent_item)
                step_item.setText(
                    0, 
                    f"Step {step.get('id', 'unknown')} status: {step.get('status', 'n/a')}"
                )

                # If the step has tool calls, we'll list them under each step
                tool_calls = step.get('tool_calls', [])
                if tool_calls:
                    tool_calls_parent = QTreeWidgetItem(step_item)
                    tool_calls_parent.setText(0, "Tool calls:")

                    for call in tool_calls:
                        # Show the base line with ID + type
                        call_item = QTreeWidgetItem(tool_calls_parent)
                        call_item.setText(
                            0,
                            f"  Tool Call ID: {call.get('id', '')}"
                            f" | Type: {call.get('type', '')}"
                        )

                        # Then, branch on the type to display further detail
                        call_type = call.get("type", "").lower()

                        # -- (A) openapi / function calls --
                        if call_type in ("openapi", "function"):
                            fn_item = QTreeWidgetItem(call_item)
                            fn_item.setText(
                                0,
                                f"    Function name: {call.get('function_name','')}"
                            )

                            arg_item = QTreeWidgetItem(call_item)
                            arg_item.setText(
                                0,
                                f"    Arguments: {call.get('arguments','')}"
                            )

                        # -- (B) azure_ai_search calls --
                        elif call_type == "azure_ai_search":
                            input_item = QTreeWidgetItem(call_item)
                            input_item.setText(
                                0,
                                f"    Search Input: {call.get('azure_ai_search_input', '')}"
                            )

                            output_item = QTreeWidgetItem(call_item)
                            output_item.setText(
                                0,
                                f"    Search Output: {call.get('azure_ai_search_output', '')}"
                            )

                        else:
                            # Some unknown type — just mark it
                            unknown_item = QTreeWidgetItem(call_item)
                            unknown_item.setText(0, "    (Unrecognized tool call type)")

            # Optionally expand or collapse
            steps_parent_item.setExpanded(False)
            self.functionCallTree.scrollToItem(steps_parent_item, QAbstractItemView.PositionAtBottom)
        except Exception as e:
            logger.error(f"Error occurred while adding run steps for {run_identifier}: {e}")

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
                    "messages": "",
                    "steps": []
                }

                for j in range(run_item.childCount()):
                    child_item = run_item.child(j)
                    text = child_item.text(0)

                    # Identify each child item by its prefix
                    if text.startswith("Assistant:"):
                        run_data["assistant_name"] = text.split(":", 1)[1].strip()
                    elif text.startswith("Run Identifier:"):
                        run_data["run_identifier"] = text.split(":", 1)[1].strip()
                    elif text.startswith("Run Start Time:"):
                        run_data["run_start_time"] = text.split(":", 1)[1].strip()
                    elif text.startswith("Description:"):
                        run_data["run_description"] = text.split(":", 1)[1].strip()
                    elif text.startswith("Function call:"):
                        # function call data
                        function_call_data = {
                            "function_name": text.split(":", 1)[1].strip(),
                            "arguments": "",
                            "response": "",
                        }
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
                    elif text == "Steps":
                        # Parent item for the step items
                        for step_index in range(child_item.childCount()):
                            step_item = child_item.child(step_index)
                            step_text = step_item.text(0)
                            # e.g. "Step step_RTKjdT7ROJ9tUT35iqCAysh4 status: completed"
                            if step_text.startswith("Step "):
                                # Extract ID and status
                                step_id_part, status_part = step_text.replace("Step ", "").split(" status:", 1)
                                step_id = step_id_part.strip()
                                step_status = status_part.strip()

                                step_dict = {
                                    "id": step_id,
                                    "status": step_status,
                                    "tool_calls": []
                                }
                                # Look for the "Tool calls:" child
                                for maybe_calls_idx in range(step_item.childCount()):
                                    calls_parent = step_item.child(maybe_calls_idx)
                                    if calls_parent.text(0) == "Tool calls:":
                                        # Each child is a single tool call
                                        for call_idx in range(calls_parent.childCount()):
                                            call_text = calls_parent.child(call_idx).text(0)
                                            # e.g. "Tool Call ID: call_xxx | Type: openapi"
                                            call_info = {}

                                            # Parse the top line to get ID + Type
                                            # (We do a .split("|") but be mindful each part may have an extra prefix)
                                            call_parts = call_text.strip().split("|")
                                            for part in call_parts:
                                                part = part.strip()
                                                if part.startswith("Tool Call ID:"):
                                                    call_info["id"] = part.split(":", 1)[1].strip()
                                                elif part.startswith("Type:"):
                                                    call_info["type"] = part.split(":", 1)[1].strip()

                                            # Now, check that call's children for function name/arguments or search input/output
                                            for subcall_idx in range(calls_parent.child(call_idx).childCount()):
                                                subcall_item = calls_parent.child(call_idx).child(subcall_idx)
                                                subcall_text = subcall_item.text(0).strip()

                                                # If it's a function call
                                                if subcall_text.startswith("Function name:"):
                                                    call_info["function_name"] = subcall_text.split(":", 1)[1].strip()
                                                elif subcall_text.startswith("Arguments:"):
                                                    call_info["arguments"] = subcall_text.split(":", 1)[1].strip()

                                                # If it's an azure_ai_search call
                                                elif subcall_text.startswith("Search Input:"):
                                                    call_info["azure_ai_search_input"] = subcall_text.split(":", 1)[1].strip()
                                                elif subcall_text.startswith("Search Output:"):
                                                    call_info["azure_ai_search_output"] = subcall_text.split(":", 1)[1].strip()

                                            step_dict["tool_calls"].append(call_info)

                                run_data["steps"].append(step_dict)

                runs.append(run_data)
            return runs
        except Exception as e:
            logger.error(f"Error occurred during diagnostics data collection: {e}")
            return []

    def save_diagnostics(self):
        try:
            file_path = "diagnostics/diagnostics.json"
            dir_path = os.path.dirname(file_path)

            # Ensure directory exists
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

            # Collect new diagnostics data
            new_data = self.collect_diagnostics_data()

            existing_data = []
            # If the file exists and is non-empty, load it
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

            # Write data back to disk
            with open(file_path, 'w') as file:
                json.dump(existing_data, file, indent=4)

        except IOError as io_error:
            QMessageBox.warning(self, "Error", f"An error occurred while saving the diagnostics: {io_error}")
            logger.error(f"Error occurred during diagnostics saving: {io_error}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An unexpected error occurred while saving the diagnostics: {e}")
            logger.error(f"Error occurred during diagnostics saving: {e}")

    def run_exists(self, existing_runs, new_run_identifier):
        """Check if a run with the given identifier already exists in the data."""
        return any(
            run["run_identifier"] == new_run_identifier 
            for run in existing_runs
        )

    def clear_diagnostics(self):
        try:
            self.functionCallTree.clear()
            self.run_items.clear()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An unexpected error occurred while clearing diagnostics: {e}")
            logger.error(f"Error occurred during diagnostics clearing: {e}")

