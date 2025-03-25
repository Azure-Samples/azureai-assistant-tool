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
    LISTENING_KEYWORD = "ListeningKeyword"
    FUNCTION_EXECUTION = "FunctionExecution"
    DELETING = "Deleting"


class StatusBar:

    def __init__(self, main_window):
        self.main_window = main_window
        self.setup_status_bar()
        # Now active_statuses is a dict mapping statuses to their call counts
        self.active_statuses = {}
        self.current_thread_name = None

    def setup_status_bar(self):
        self.processingLabel = QLabel("", self.main_window)
        self.processingLabel.setFont(QFont("Arial", 11))
        self.processingLabel.setAlignment(Qt.AlignRight)

        self.processingDots = 0
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate_processing_label)

    def animate_processing_label(self):
        frames = ["   ", ".  ", ".. ", "..."]
        
        if ActivityStatus.DELETING in self.active_statuses:
            base_text = f"Deleting {self.current_thread_name or ''}"
            self.processingLabel.setText(f"{base_text}{frames[self.processingDots]}")
            self.processingDots = (self.processingDots + 1) % 4
            return
        
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
            active_labels = [
                status_labels.get(status, "") 
                for status in self.active_statuses.keys() 
                if status in status_labels
            ]
            status_message = " | ".join(filter(None, active_labels))
            base_text = f"Processing ({status_message})"
            self.processingLabel.setText(f"{base_text}{frames[self.processingDots]}")
        else:
            # No active statuses
            self.stop_animation()
        
        self.processingDots = (self.processingDots + 1) % 4

    def start_animation(self, status, interval=500, thread_name=None):
        if status == ActivityStatus.DELETING and thread_name:
            self.current_thread_name = thread_name

        # Increase the counter for the given status
        if status in self.active_statuses:
            self.active_statuses[status] += 1
        else:
            self.active_statuses[status] = 1

        if not self.animation_timer.isActive():
            self.animation_timer.setInterval(interval)
            self.animation_timer.start()

        self.animate_processing_label()

    def stop_animation(self, status=None):
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
        return self.processingLabel
    
    def clear_all_statuses(self):
        self.active_statuses.clear()
        self.animation_timer.stop()
        self.processingLabel.clear()
        self.processingDots = 0
        self.current_thread_name = None
