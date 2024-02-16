# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QTimer
from enum import Enum
from azure.ai.assistant.management.logger_module import logger


class ActivityStatus(Enum):
    PROCESSING = "Processing"
    PROCESSING_USER_INPUT = "UserInput"
    PROCESSING_SCHEDULED_TASK = "ScheduledTask"
    LISTENING = "Listening"


class StatusBar:
    def __init__(self, main_window):
        self.main_window = main_window
        self.setup_status_bar()
        self.active_statuses = {}

    def setup_status_bar(self):
        self.processingLabel = QLabel("", self.main_window)
        self.processingLabel.setFont(QFont("Arial", 11))
        self.processingLabel.setAlignment(Qt.AlignRight)

        self.processingDots = 0
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate_processing_label)

    def animate_processing_label(self):
        frames = ["   ", ".  ", ".. ", "..."]
        if ActivityStatus.LISTENING in self.active_statuses:
            base_text = "Listening"
            self.processingLabel.setText(f"{base_text}{frames[self.processingDots]}")
        elif ActivityStatus.PROCESSING in self.active_statuses:
            base_text = "Processing"
            self.processingLabel.setText(f"{base_text}{frames[self.processingDots]}")
        elif self.active_statuses:
            status_labels = {
                ActivityStatus.PROCESSING_USER_INPUT: "User Input",
                ActivityStatus.PROCESSING_SCHEDULED_TASK: "Scheduled Task"
            }
            active_labels = [status_labels.get(status, "") for status in self.active_statuses.keys()]
            status_message = " | ".join(filter(None, active_labels))
            base_text = f"Processing ({status_message})"
            self.processingLabel.setText(f"{base_text}{frames[self.processingDots]}")
        else:
            self.stop_animation()
        self.processingDots = (self.processingDots + 1) % 4

    def start_animation(self, status, interval=500):
        self.active_statuses[status] = status
        if not self.animation_timer.isActive():
            self.animation_timer.setInterval(interval)
            self.animation_timer.start()
        self.animate_processing_label()

    def stop_animation(self, status=None):
        if status in self.active_statuses:
            del self.active_statuses[status]
        if not self.active_statuses:
            self.animation_timer.stop()
            self.processingLabel.clear()

    def get_widget(self):
        """ Returns the main widget of the status bar. """
        return self.processingLabel