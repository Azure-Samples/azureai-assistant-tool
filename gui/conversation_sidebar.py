# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtWidgets import QWidget, QCheckBox, QLabel, QComboBox, QListWidgetItem, QFileDialog, QVBoxLayout, QSizePolicy, QHBoxLayout, QPushButton, QListWidget, QMessageBox, QMenu
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QIcon, QAction

import os, time

from azure.ai.assistant.management.ai_client_factory import AIClientType
from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.assistant_client import AssistantClient
from azure.ai.assistant.management.chat_assistant_client import ChatAssistantClient
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient
from azure.ai.assistant.management.logger_module import logger
from gui.assistant_client_manager import AssistantClientManager
from gui.assistant_dialogs import AssistantConfigDialog
from gui.utils import resource_path


class AssistantItemWidget(QWidget):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.checkbox = QCheckBox(self)
        self.label = QLabel(name, self)

        font = QFont("Arial", 11)
        self.checkbox.setFont(font)
        self.label.setFont(font)
        self.layout.addWidget(self.checkbox)
        self.layout.addWidget(self.label)
        self.layout.addStretch()
        self.setLayout(self.layout)


class CustomListWidget(QListWidget):
    itemDeleted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.itemToFileMap = {}  # Maps list items to attached file paths

    def clear_files(self):
        self.itemToFileMap.clear()

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        attach_file_search_action = context_menu.addAction("Attach File for File Search")
        attach_file_code_action = context_menu.addAction("Attach File for Code Interpreter")
        attach_image_action = context_menu.addAction("Attach Image File")

        current_item = self.currentItem()
        remove_file_menu = None
        if current_item:
            row = self.row(current_item)
            if row in self.itemToFileMap and self.itemToFileMap[row]:
                remove_file_menu = context_menu.addMenu("Remove File")
                for file_info in self.itemToFileMap[row]:
                    actual_file_path = file_info['file_path']
                    tool_type = file_info['tools'][0]['type'] if file_info['tools'] else "Image"

                    file_label = f"{os.path.basename(actual_file_path)} ({tool_type})"
                    action = remove_file_menu.addAction(file_label)
                    action.setData(file_info)

        selected_action = context_menu.exec_(self.mapToGlobal(event.pos()))

        if selected_action == attach_file_search_action:
            self.attach_file_to_selected_item("file_search")
        elif selected_action == attach_file_code_action:
            self.attach_file_to_selected_item("code_interpreter")
        elif selected_action == attach_image_action:
            self.attach_file_to_selected_item(None, is_image=True)
        elif remove_file_menu and isinstance(selected_action, QAction) and selected_action.parent() == remove_file_menu:
            file_info = selected_action.data()
            self.remove_specific_file_from_selected_item(file_info, self.row(current_item))

    def attach_file_to_selected_item(self, mode, is_image=False):
        """Attaches a file to the selected item with a specified mode indicating its intended use."""
        file_dialog = QFileDialog(self)
        if is_image:
            file_path, _ = file_dialog.getOpenFileName(self, "Select Image File", filter="Images (*.png *.jpg *.jpeg *.gif *.webp)")
        else:
            file_path, _ = file_dialog.getOpenFileName(self, "Select File")

        if file_path:
            current_item = self.currentItem()
            if current_item:
                row = self.row(current_item)
                if row not in self.itemToFileMap:
                    self.itemToFileMap[row] = []

                file_info = {
                    "file_id": None,  # This will be updated later
                    "file_path": file_path,
                    "attachment_type": "image_file" if is_image else "document_file",
                    "tools": [] if is_image else [{"type": mode}]  # No tools for image files
                }
                self.itemToFileMap[row].append(file_info)
                self.update_item_icon(current_item, self.itemToFileMap[row])

    def remove_specific_file_from_selected_item(self, file_info, row):
        """Removes a specific file from the selected item based on the file info provided."""
        if row in self.itemToFileMap:
            file_path_to_remove = file_info['file_path']
            self.itemToFileMap[row] = [fi for fi in self.itemToFileMap[row] if fi['file_path'] != file_path_to_remove]

            current_item = self.item(row)
            if not self.itemToFileMap[row]:
                current_item.setIcon(QIcon())
            else:
                self.update_item_icon(current_item, self.itemToFileMap[row])

    def update_item_icon(self, item, files):
        """Updates the list item's icon based on whether there are attached files."""
        if files:
            item.setIcon(QIcon("gui/images/paperclip_icon.png"))
        else:
            item.setIcon(QIcon())

    def get_attachments_for_selected_item(self):
        """Return the details of files attached to the currently selected item including file path and specific tool usage."""
        current_item = self.currentItem()
        if current_item:
            row = self.row(current_item)
            attached_files_info = self.itemToFileMap.get(row, [])
            attachments = []
            for file_info in attached_files_info:
                file_path = file_info['file_path']
                file_name = os.path.basename(file_path)
                file_id = file_info.get('file_id', None)
                tools = file_info.get('tools', [])
                attachment_type = file_info.get('attachment_type', 'document_file')

                # Create a structured entry for the attachments list including file_path
                attachments.append({
                    "file_name": file_name,
                    "file_id": file_id,
                    "file_path": file_path,  # Include the full file path for upload or further processing
                    "attachment_type": attachment_type,
                    "tools": tools
                })
            return attachments
        return []

    def set_attachments_for_selected_item(self, attachments):
        """Set the attachments for the currently selected item."""
        current_item = self.currentItem()
        if current_item is not None:
            row = self.row(current_item)
            self.itemToFileMap[row] = attachments[:]
            self.update_item_icon(current_item, attachments)
        else:
            logger.warning("No item is currently selected.")

    def load_threads_with_attachments(self, threads):
        """Load threads into the list widget, adding icons for attached files only, based on attachments info."""
        self.clear_files()  # Clear itemToFileMap before loading new threads
        for thread in threads:
            item = QListWidgetItem(thread['thread_name'])
            self.addItem(item)
            thread_tooltip_text = "You can add/remove files by right-clicking this item."
            item.setToolTip(thread_tooltip_text)

            # Get attachments from the thread data
            attachments = thread.get('attachments', [])

            # Update the item to reflect any attachments
            self.update_item_with_attachments(item, attachments)

    def update_item_with_attachments(self, item, attachments):
        """Update the given item with a paperclip icon if there are attachments."""
        row = self.row(item)
        if attachments:
            item.setIcon(QIcon("gui/images/paperclip_icon.png"))
        else:
            item.setIcon(QIcon())

        # Store complete attachment information in the mapping
        self.itemToFileMap[row] = attachments[:]

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            current_item = self.currentItem()
            if current_item:
                row = self.row(current_item)
                item_text = current_item.text()
                self.takeItem(row)
                # delete the attachments for the deleted item
                if row in self.itemToFileMap:
                    del self.itemToFileMap[row]
                self.itemDeleted.emit(item_text)
        else:
            super().keyPressEvent(event)

    def selectNewItem(self, previousRow):
        if previousRow < self.count():
            self.setCurrentRow(previousRow)
        elif self.count() > 0:
            self.setCurrentRow(self.count() - 1)

    def get_current_text(self):
        """Return the text of the currently selected item."""
        current_item = self.currentItem()
        if current_item:
            return current_item.text()
        return ""

    def update_current_item(self, thread_title):
        """Update the name of the currently selected thread item."""
        current_item = self.currentItem()
        if current_item:
            current_item.setText(thread_title)

    def update_item_by_name(self, current_thread_name, new_thread_name):
        """Update the thread title from current_thread_name to new_thread_name."""
        for i in range(self.count()):
            item = self.item(i)
            if item.text() == current_thread_name:
                item.setText(new_thread_name)
                break

    def is_thread_selected(self, thread_name):
        """Check if the given thread name is the selected thread."""
        return self.get_current_text() == thread_name


class ConversationSidebar(QWidget):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setMinimumWidth(250)
        self.assistant_config_manager = AssistantConfigManager.get_instance()
        self.assistant_client_manager = AssistantClientManager.get_instance()

        # Create a button for adding new threads
        self.addThreadButton = QPushButton("Add Thread", self)
        self.addThreadButton.setFixedHeight(23)
        self.addThreadButton.setFont(QFont("Arial", 11))

        # Create a button for canceling the current run
        self.cancelRunButton = QPushButton("Cancel Run", self)
        self.cancelRunButton.setFixedHeight(23)
        self.cancelRunButton.setFont(QFont("Arial", 11))

        # Load icons
        self.mic_on_icon = QIcon(resource_path("gui/images/mic_on.png"))
        self.mic_off_icon = QIcon(resource_path("gui/images/mic_off.png"))

        # Create a toggle button for the microphone
        self.toggle_mic_button = QPushButton(self)
        # Create and style the toggle_mic_button
        self.toggle_mic_button.setFixedSize(20, 23)
        self.toggle_mic_button.setIcon(self.mic_off_icon)
        self.toggle_mic_button.setIconSize(QSize(23, 23))  # Set size as needed
        self.toggle_mic_button.setStyleSheet("QPushButton { border: none; }")

        # Horizontal layout to hold both buttons
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.addThreadButton)
        buttonLayout.addWidget(self.cancelRunButton)
        buttonLayout.addWidget(self.toggle_mic_button)
        buttonLayout.setSpacing(10)  # Adjust spacing as needed

        self.is_listening = False

        # Create a list widget for displaying the threads
        self.threadList = CustomListWidget(self)
        self.threadList.setStyleSheet("QListWidget {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}")
        self.threadList.setFont(QFont("Arial", 11))

        # Create connections for the thread and button
        self.addThreadButton.clicked.connect(self.on_add_thread_button_clicked)
        self.cancelRunButton.clicked.connect(self.main_window.on_cancel_run_button_clicked)
        self.threadList.itemClicked.connect(self.select_conversation_thread_by_item)
        self.threadList.itemDeleted.connect(self.on_selected_thread_delete)
        self.toggle_mic_button.clicked.connect(self.toggle_mic)

        # Create a list widget for displaying assistants
        self.assistantList = QListWidget(self)
        self.assistantList.setFont(QFont("Arial", 11))
        self.assistantList.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.assistantList.setStyleSheet("QListWidget {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}")
        self.assistantList.itemDoubleClicked.connect(self.on_assistant_double_clicked)
        self.assistantList.setToolTip("Select assistants to use in the conversation or double-click to edit the selected assistant.")
        self.threadList.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.aiClientComboBox = QComboBox()
        ai_client_type_names = [client_type.name for client_type in AIClientType]
        self.aiClientComboBox.addItems(ai_client_type_names)
        self.aiClientComboBox.currentIndexChanged.connect(self.on_ai_client_type_changed)

        # Layout for the sidebar
        layout = QVBoxLayout(self)
        layout.addWidget(self.aiClientComboBox)
        layout.addWidget(self.assistantList, 1)
        layout.addWidget(self.threadList, 2)
        layout.addLayout(buttonLayout)
        layout.setAlignment(Qt.AlignTop)

        # Set the style for the sidebar
        self.setStyleSheet(
            "QWidget {"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"
            "  padding: 1px;"
            "}"
        )
        self.on_ai_client_type_changed(self.aiClientComboBox.currentIndex())

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self.assistantList.hasFocus():
                self.delete_selected_assistant()
        else:
            super().keyPressEvent(event)

    def on_assistant_double_clicked(self, item):
        widget = self.assistantList.itemWidget(item)
        assistant_name = widget.label.text()
        assistant_config = self.assistant_config_manager.get_config(assistant_name)
        if assistant_config:
            if assistant_config.assistant_type == "assistant":
                self.dialog = AssistantConfigDialog(parent=self.main_window, assistant_name=assistant_name, function_config_manager=self.main_window.function_config_manager)
            else:
                self.dialog = AssistantConfigDialog(parent=self.main_window, assistant_type="chat_assistant", assistant_name=assistant_name, function_config_manager=self.main_window.function_config_manager)
            self.dialog.assistantConfigSubmitted.connect(self.on_assistant_config_submitted)
            self.dialog.show()

    def on_assistant_config_submitted(self, assistant_config_json, ai_client_type, assistant_type):
        try:
            if assistant_type == "chat_assistant":
                assistant_client = ChatAssistantClient.from_json(assistant_config_json, self.main_window, self.main_window.connection_timeout)
            else:
                assistant_client = AssistantClient.from_json(assistant_config_json, self.main_window, self.main_window.connection_timeout)
            self.assistant_client_manager.register_client(assistant_client.name, assistant_client)
            client_type = AIClientType[ai_client_type]
            self.main_window.conversation_sidebar.load_assistant_list(client_type)
            self.dialog.update_assistant_combobox()
        except Exception as e:
            QMessageBox.warning(self.main_window, "Error", f"An error occurred while creating/updating the assistant: {e}")

    def delete_selected_assistant(self):
        current_item = self.assistantList.currentItem()
        if current_item:
            row = self.assistantList.row(current_item)
            item = self.assistantList.item(row)
            widget = self.assistantList.itemWidget(item)
            assistant_name = widget.label.text()
            reply = QMessageBox.question(self, 'Confirm Delete',
                                         f"Are you sure you want to delete '{assistant_name}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                try:
                    assistant_client : AssistantClient = self.assistant_client_manager.get_client(assistant_name)
                    if assistant_client:
                        assistant_client.purge(self.main_window.connection_timeout)
                    self.assistant_client_manager.remove_client(assistant_name)
                    self.main_window.conversation_view.conversationView.clear()
                    self.assistant_config_manager.load_configs()
                    self.load_assistant_list(self._ai_client_type)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"An error occurred while deleting the assistant: {e}")

    def populate_assistants(self, assistant_names):
        """Populate the assistant list with given assistant names."""
        # Capture the currently selected assistant's name
        currently_selected_assistants = self.get_selected_assistants()

        # Clear and repopulate the list
        self.assistantList.clear()
        for name in assistant_names:
            item = QListWidgetItem(self.assistantList)
            widget = AssistantItemWidget(name)
            item.setSizeHint(widget.sizeHint())
            self.assistantList.addItem(item)
            self.assistantList.setItemWidget(item, widget)

        # Restore selection if the assistant is still in the list
        for i in range(self.assistantList.count()):
            item = self.assistantList.item(i)
            widget : AssistantItemWidget = self.assistantList.itemWidget(item)
            if widget.label.text() in currently_selected_assistants:  # Assuming the label's text stores the assistant's name
                # self.assistantList.setCurrentItem(item)
                # check the checkbox
                widget.checkbox.setChecked(True)

    def get_selected_assistants(self):
        """Return a list of names of the selected assistants."""
        selected_assistants = []
        for i in range(self.assistantList.count()):
            item = self.assistantList.item(i)
            widget = self.assistantList.itemWidget(item)
            if isinstance(widget, AssistantItemWidget) and widget.checkbox.isChecked():
                selected_assistants.append(widget.label.text())
        return selected_assistants

    def get_ai_client_type(self):
        """Return the AI client type selected in the combo box."""
        return self._ai_client_type

    def load_assistant_list(self, ai_client_type : AIClientType):
        """Populate the assistant list with the given assistant names."""
        try:
            assistant_names = self.assistant_config_manager.get_assistant_names_by_client_type(ai_client_type.name)
            # TODO retrieve assistant clients using cloud API
            #assistant_list = AssistantClient.get_assistant_list(ai_client_type)
            for name in assistant_names:
                if not self.assistant_client_manager.get_client(name):
                    assistant_config : AssistantConfig = self.assistant_config_manager.get_config(name)
                    assistant_config.config_folder = "config"
                    if assistant_config.assistant_type == "assistant":
                        assistant_client = AssistantClient.from_json(assistant_config.to_json(), self.main_window, self.main_window.connection_timeout)
                    else:
                        assistant_client = ChatAssistantClient.from_json(assistant_config.to_json(), self.main_window, self.main_window.connection_timeout)
                    self.assistant_client_manager.register_client(name, assistant_client)
        except Exception as e:
            logger.error(f"Error while loading assistant list: {e}")
        finally:
            self.populate_assistants(assistant_names)

    def on_ai_client_type_changed(self, index):
        """Handle changes in the selected AI client type."""
        try:
            selected_ai_client = self.aiClientComboBox.itemText(index)
            self._ai_client_type = AIClientType[selected_ai_client]

            # Load the assistants for the selected AI client type
            self.load_assistant_list(self._ai_client_type)

            # Clear the existing items in the thread list
            self.threadList.clear()
            self.threadList.clear_files()

            # Get the threads for the selected AI client type
            threads_client = ConversationThreadClient.get_instance(self._ai_client_type, config_folder='config')
            threads = threads_client.get_conversation_threads()
            self.threadList.load_threads_with_attachments(threads)
        except Exception as e:
            logger.error(f"Error while changing AI client type: {e}")
        finally:
            self.main_window.set_active_ai_client_type(self._ai_client_type)

    def set_attachments_for_selected_thread(self, attachments):
        """Set the attachments for the currently selected item."""
        self.threadList.set_attachments_for_selected_item(attachments)

    def on_add_thread_button_clicked(self):
        """Handle clicks on the add thread button."""
        # Get the selected assistant
        selected_assistants = self.get_selected_assistants()
        # check if selected_assistants is empty list
        if not selected_assistants:
            QMessageBox.warning(self, "Error", "Please select an assistant first.")
            return
        try:
            threads_client = ConversationThreadClient.get_instance(self._ai_client_type)
            thread_name = self.create_conversation_thread(threads_client, timeout=self.main_window.connection_timeout)
            self._select_thread(thread_name)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while creating a new thread: {e}")

    def on_cancel_run_button_clicked(self):
        """Handle clicks on the cancel run button."""
        self.main_window.on_cancel_run_button_clicked()

    def create_conversation_thread(self, threads_client : ConversationThreadClient, is_scheduled_task=False, timeout: float=None):
        try:
            start_time = time.time()
            unique_thread_name = threads_client.create_conversation_thread(timeout=timeout)
            end_time = time.time()
            logger.debug(f"Total time taken to create a new conversation thread: {end_time - start_time} seconds")
            new_item = QListWidgetItem(unique_thread_name)
            self.threadList.addItem(new_item)
            thread_tooltip_text = f"You can add/remove files by right-clicking this item."
            new_item.setToolTip(thread_tooltip_text)

            if not is_scheduled_task:
                self.main_window.conversation_view.conversationView.clear()
            return unique_thread_name
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while creating a new thread: {e}")

    def select_conversation_thread_by_item(self, selected_item):
        unique_thread_name = selected_item.text()
        self._select_thread(unique_thread_name)

    def select_conversation_thread_by_name(self, unique_thread_name):
        self._select_thread(unique_thread_name)

    def toggle_mic(self):
        self.is_listening = not self.is_listening
        if self.is_listening:
            is_started = self.main_window.on_listening_started()
            if not is_started:
                self.is_listening = False
                return
            self.toggle_mic_button.setIcon(self.mic_on_icon)
            logger.info("Microphone is now active.")
        else:
            self.toggle_mic_button.setIcon(self.mic_off_icon)
            self.main_window.on_listening_stopped()
            logger.info("Microphone is now inactive.")

    def _select_threadlist_item(self, unique_thread_name):
        # Select the thread item in the sidebar
        for index in range(self.threadList.count()):
            if self.threadList.item(index).text() == unique_thread_name:
                self.threadList.setCurrentRow(index)
                break

    def _select_thread(self, unique_thread_name):
        # Select the thread item in the sidebar
        self._select_threadlist_item(unique_thread_name)
        try:
            threads_client = ConversationThreadClient.get_instance(self._ai_client_type)
            #TODO separate threads per ai_client_type in the json file
            threads_client.set_current_conversation_thread(unique_thread_name)
            self.main_window.conversation_view.conversationView.clear()
            # Retrieve the messages for the selected thread
            conversation = threads_client.retrieve_conversation(unique_thread_name, timeout=self.main_window.connection_timeout)
            if conversation.messages is not None:
                self.main_window.conversation_view.append_messages(conversation.messages)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while selecting the thread: {e}")

    def on_selected_thread_delete(self, thread_name):
        try:
            # Get current scroll position and selected row
            current_scroll_position = self.threadList.verticalScrollBar().value()
            current_row = self.threadList.currentRow()

            # Remove the selected thread from the assistant manager
            threads_client = ConversationThreadClient.get_instance(self._ai_client_type)
            threads_client.delete_conversation_thread(thread_name)
            threads_client.save_conversation_threads()
            
            # Clear and reload the thread list
            self.threadList.clear()
            threads = threads_client.get_conversation_threads()
            self.threadList.load_threads_with_attachments(threads)
            
            # Restore the scroll position
            self.threadList.verticalScrollBar().setValue(current_scroll_position)
            
            # Restore the selected row
            if current_row >= self.threadList.count():
                current_row = self.threadList.count() - 1
            self.threadList.setCurrentRow(current_row)
            
            # Clear the selection in the sidebar
            self.threadList.clearSelection()
            
            # Clear the conversation area
            self.main_window.conversation_view.conversationView.clear()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while deleting the thread: {e}")