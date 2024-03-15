# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QLabel, QPushButton, QComboBox, QTextEdit, QHBoxLayout, QListWidget, QListWidgetItem, QCheckBox
from PySide6.QtCore import Signal, Slot, Qt, QObject, QThread, Qt, QMetaObject, Q_ARG, QTimer

import logging, threading

from azure.ai.assistant.management.logger_module import logger


class LogMessageProcessor(QObject):
    updateUI = Signal(str)  # Signal to send processed log messages to the UI thread

    def __init__(self):
        super().__init__()
        self.messageBuffer = []
        self.thread_lock = threading.Lock()
        self.bufferTimer = QTimer(self)
        self.bufferTimer.timeout.connect(self.flushBuffer)
        self.timer_interval = 1000  # Default timer interval in milliseconds

    def startTimer(self):
        # Safe method to start the timer from the correct thread
        self.bufferTimer.start(self.timer_interval)

    def stopTimer(self):
        # Safe method to stop the timer
        self.bufferTimer.stop()

    def setTimerInterval(self, interval):
        self.timer_interval = interval

    @Slot(str)
    def processMessage(self, message):
        with self.thread_lock:
            self.messageBuffer.append(message)
            if not self.bufferTimer.isActive():
                # Use QMetaObject.invokeMethod to safely start the timer from the correct thread
                QMetaObject.invokeMethod(self.bufferTimer, "start", Qt.AutoConnection, Q_ARG(int, self.timer_interval))

    def flushBuffer(self):
        with self.thread_lock:
            if self.messageBuffer:
                for message in self.messageBuffer:
                    self.updateUI.emit(message)
                self.messageBuffer.clear()


class DebugViewDialog(QDialog):

    def __init__(self, broadcaster, parent=None):
        super(DebugViewDialog, self).__init__(parent)
        self.setWindowTitle("Debug View")
        self.resize(800, 800)
        self.broadcaster = broadcaster
        # Store log messages
        self.logMessages = []

        mainLayout = QVBoxLayout()  # Top level layout is now vertical

        # Filter LineEdit at the top
        self.filterLineEdit = QLineEdit()
        self.filterLineEdit.setPlaceholderText("Add new filter (e.g., 'ERROR') and press Enter")
        self.filterLineEdit.textChanged.connect(self.apply_filter)
        self.filterLineEdit.returnPressed.connect(self.add_filter_word)
        mainLayout.addWidget(self.filterLineEdit)

        # Horizontal layout for filter list and log view
        contentLayout = QHBoxLayout()

        # Filter List Section
        filterListLayout = QVBoxLayout()
        self.filterList = QListWidget()
        self.filterList.setFixedWidth(200)
        self.filterList.itemChanged.connect(self.apply_filter)
        filterListLayout.addWidget(QLabel("Filters:"))
        filterListLayout.addWidget(self.filterList)

        # Log View Section
        logViewLayout = QVBoxLayout()
        self.textEdit = QTextEdit()
        self.textEdit.setReadOnly(True)
        self.textEdit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #c0c0c0; /* Adjusted to have a 1px solid border */
                border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;
                border-radius: 4px;
                padding: 1px; /* Adds padding inside the QTextEdit widget */
            }
        """)
        logViewLayout.addWidget(QLabel("Log:"))
        logViewLayout.addWidget(self.textEdit)

        # Optional: Add other controls like log level selection and clear button to the logViewLayout
        controlLayout = QHBoxLayout()
        self.logLevelComboBox = QComboBox()
        self.clearButton = QPushButton("Clear")
        self.clearButton.setAutoDefault(False)
        self.clearButton.setDefault(False)
        self.clearButton.clicked.connect(self.clear_log_window)
        controlLayout.addWidget(QLabel("Log Level:"))
        controlLayout.addWidget(self.logLevelComboBox)
        controlLayout.addWidget(self.clearButton)
        logViewLayout.addLayout(controlLayout)
        # Add checkbox for enabling openai logging
        openaiLoggingCheckBox = QCheckBox("Enable OpenAI logging")
        openaiLoggingCheckBox.stateChanged.connect(self.toggle_openai_logging)
        logViewLayout.addWidget(openaiLoggingCheckBox)

        # Populate log level combo box
        for level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
            self.logLevelComboBox.addItem(level, getattr(logging, level))
        self.logLevelComboBox.currentIndexChanged.connect(self.change_log_level)
        self.change_log_level(0)  # Set default log level

        # Combine filter list and log view sections into the content layout
        contentLayout.addLayout(filterListLayout, 1)  # Filter list section
        contentLayout.addLayout(logViewLayout, 3)  # Log view section

        # Add the content layout below the filter QLineEdit
        mainLayout.addLayout(contentLayout)

        self.setLayout(mainLayout)

        # Initialize the LogMessageProcessor in a separate thread
        self.setupProcessorThread()

        self.broadcaster.subscribe(self.queue_append_text)

    def setupProcessorThread(self):
        # Initialize or reinitialize the LogMessageProcessor and its thread
        if hasattr(self, 'processorThread') and self.processorThread.isRunning():
            return  # The thread is already running, no need to set up again
        
        self.processorThread = QThread()
        self.logProcessor = LogMessageProcessor()
        self.logProcessor.moveToThread(self.processorThread)
        self.processorThread.started.connect(self.logProcessor.startTimer)
        self.processorThread.finished.connect(self.logProcessor.stopTimer)
        self.logProcessor.updateUI.connect(self.append_text_slot)
        self.processorThread.start()

    def append_text_slot(self, message):
        if self.is_filter_selected():
            # Filter based on selected items in the list box
            selected_filters = [self.filterList.item(i).text().lower() for i in range(self.filterList.count()) if self.filterList.item(i).checkState() == Qt.CheckState.Checked]

            # Re-add messages that match any of the selected filters
            if any(filter_word in message.lower() for filter_word in selected_filters):
                self.textEdit.append(message)
        else:
            self.textEdit.append(message)
        # Store the message
        self.logMessages.append(message)

    def queue_append_text(self, message):
        QMetaObject.invokeMethod(self.logProcessor, 'processMessage', Qt.QueuedConnection, Q_ARG(str, message))

    def toggle_openai_logging(self, state):
        level = self.logLevelComboBox.itemData(self.logLevelComboBox.currentIndex())
        openai_logger = logging.getLogger("openai")
        if state == Qt.CheckState.Checked.value:
            openai_logger.setLevel(level)
        else:
            openai_logger.setLevel(0)

    def change_log_level(self, index):
        level = self.logLevelComboBox.itemData(index)
        logger.setLevel(level)

    def clear_log_window(self):
        self.textEdit.clear()
        self.logMessages.clear()

    def is_filter_selected(self):
        # Check if any filter is selected
        is_any_filter_selected = any(self.filterList.item(i).checkState() == Qt.CheckState.Checked for i in range(self.filterList.count()))
        return is_any_filter_selected

    def apply_filter(self):
        # Clear the textEdit widget
        self.textEdit.clear()

        if self.is_filter_selected():
            # Filter based on selected items in the list box
            selected_filters = [self.filterList.item(i).text().lower() for i in range(self.filterList.count()) if self.filterList.item(i).checkState() == Qt.CheckState.Checked]

            # Re-add messages that match any of the selected filters
            for message in self.logMessages:
                if any(filter_word in message.lower() for filter_word in selected_filters):
                    self.textEdit.append(message)
        else:
            # Get the current filter text
            filter_text = self.filterLineEdit.text().lower()
            # Re-add messages that match the filter
            for message in self.logMessages:
                if filter_text in message.lower():
                    self.textEdit.append(message)

    def add_filter_word(self):
        # Get the text from QLineEdit
        filter_word = self.filterLineEdit.text()
        if not filter_word:
            return

        # Create a new QListWidgetItem
        item = QListWidgetItem(filter_word)
        #item.setFlags(item.flags() | Qt.ItemIsUserCheckable)  # Make the item checkable
        item.setCheckState(Qt.CheckState.Unchecked)  # Set the item to be checked by default

        # Add the item to the list
        self.filterList.addItem(item)

        # Apply the current filter with the new filter word added
        self.apply_filter()

    def showEvent(self, event):
        # Ensure the processor thread is set up and running when dialog is shown
        self.setupProcessorThread()
        super().showEvent(event)

    def closeEvent(self, event):
        # Properly handle the thread's closure
        self.processorThread.quit()
        self.processorThread.wait()
        super().closeEvent(event)