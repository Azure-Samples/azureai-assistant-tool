# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtCore import QObject, Signal

from gui.status_bar import ActivityStatus

class AppendConversationSignal(QObject):
    update_signal = Signal(str, str, str)

class UserInputSignal(QObject):
    update_signal = Signal(str)

class UserInputSendSignal(QObject):
    send_signal = Signal(str)

class SpeechSynthesisCompleteSignal(QObject):
    complete_signal = Signal()

class ConversationViewClear(QObject):
    update_signal = Signal()

class ConversationAppendMessageSignal(QObject):
    append_signal = Signal(object)

class ConversationAppendMessagesSignal(QObject):
    append_signal = Signal(list)

class ConversationAppendImageSignal(QObject):
    append_signal = Signal(str)

class ConversationAppendChunkSignal(QObject):
    append_signal = Signal(str, str, bool)

class StartStatusAnimationSignal(QObject):
    start_signal = Signal(ActivityStatus)

class StopStatusAnimationSignal(QObject):
    stop_signal = Signal(ActivityStatus)

class StartProcessingSignal(QObject):
    start_signal = Signal(str, bool)

class StopProcessingSignal(QObject):
    stop_signal = Signal(str, bool)

class UpdateConversationTitleSignal(QObject):
    update_signal = Signal(str, str)

class DiagnosticStartRunSignal(QObject):
    # Define a signal that carries assistant name, run identifier, run start time and user input
    start_signal = Signal(str, str, str, str)

class DiagnosticAddFunctionCallSignal(QObject):
    # Define a signal that carries assistant name, function name, arguments and function response
    call_signal = Signal(str, str, str, str, str)

class DiagnosticEndRunSignal(QObject):
    # Define a signal that carries assistant name, run end time and assistant messages
    end_signal = Signal(str, str, str, str)

class ErrorSignal(QObject):
    # Define a signal that carries error message
    error_signal = Signal(str)
