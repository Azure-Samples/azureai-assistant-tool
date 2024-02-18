# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from PySide6.QtCore import Signal
from PySide6.QtCore import QObject


class StreamCapture(QObject):
    textEmitted = Signal(str)

    def write(self, text):
        self.textEmitted.emit(str(text))

    def flush(self):
        pass


class LogBroadcaster:
    def __init__(self):
        self._subscribers = []

    def subscribe(self, callback):
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def emit(self, message):
        for callback in self._subscribers:
            callback(message)