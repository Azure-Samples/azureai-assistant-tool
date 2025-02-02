from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QTimer
from enum import Enum

from azure.ai.assistant.management.logger_module import logger


class ActivityStatus(Enum):
    PROCESSING = "Processing"
    PROCESSING_USER_INPUT = "UserInput"
    PROCESSING_SCHEDULED_TASK = "ScheduledTask"
    LISTENING_SPEECH = "ListeningSpeech"
    LISTENING_KEYWORD = "ListeningKeyword"  # Removed trailing comma to avoid tuple
    FUNCTION_EXECUTION = "FunctionExecution"


class StatusBar:
    def __init__(self, main_window):
        self.main_window = main_window
        self.setup_status_bar()
        # Now active_statuses is a dict mapping statuses to their call counts
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
        if ActivityStatus.PROCESSING in self.active_statuses:
            base_text = "Processing"
            self.processingLabel.setText(f"{base_text}{frames[self.processingDots]}")
        elif self.active_statuses:
            status_labels = {
                ActivityStatus.LISTENING_SPEECH: "Speech Input",
                ActivityStatus.LISTENING_KEYWORD: "Keyword Input",
                ActivityStatus.FUNCTION_EXECUTION: "Function Call",
                ActivityStatus.PROCESSING_USER_INPUT: "User Input",
                ActivityStatus.PROCESSING_SCHEDULED_TASK: "Scheduled Task"
            }
            # Gather active statuses that are present (keys with count > 0)
            active_labels = [
                status_labels.get(status, "") 
                for status in self.active_statuses.keys() 
                if status in status_labels
            ]
            # Join them with " | "
            status_message = " | ".join(filter(None, active_labels))
            base_text = f"Processing ({status_message})"
            self.processingLabel.setText(f"{base_text}{frames[self.processingDots]}")
        else:
            self.stop_animation()
        self.processingDots = (self.processingDots + 1) % 4

    def start_animation(self, status, interval=500):
        """
        Start the animation for a given status.
        If the same status is already active, increment its calling count.
        """
        # Increase the counter for the given status
        if status in self.active_statuses:
            self.active_statuses[status] += 1
        else:
            self.active_statuses[status] = 1

        if not self.animation_timer.isActive():
            self.animation_timer.setInterval(interval)
            self.animation_timer.start()
        # Update immediately.
        self.animate_processing_label()

    def stop_animation(self, status=None):
        """
        Stop the animation for a given status.
        If status is None, stop all animations.
        Decrement the counter for the given status and remove it only if the count reaches zero.
        """
        if status is not None:
            # If the status exists in our active_statuses, decrement its count.
            if status in self.active_statuses:
                self.active_statuses[status] -= 1
                if self.active_statuses[status] <= 0:
                    del self.active_statuses[status]
        else:
            # If no status is provided, clear everything.
            self.active_statuses.clear()

        if not self.active_statuses:
            self.animation_timer.stop()
            self.processingLabel.clear()

    def get_widget(self):
        """Returns the main widget of the status bar."""
        return self.processingLabel
