# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from azure.ai.assistant.management.assistant_config_manager import AssistantConfigManager
from azure.ai.assistant.management.message import ConversationMessage
from azure.ai.assistant.management.logger_module import logger

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QMessageBox
from PySide6.QtGui import QFont, QTextCursor,QDesktopServices, QMouseEvent, QGuiApplication, QPalette, QImage
from PySide6.QtCore import Qt, QUrl, QMimeData, QIODevice, QBuffer
from bs4 import BeautifulSoup

import html, os, re, subprocess, sys, tempfile
import base64, random, time
from typing import List
from collections import defaultdict
import threading
from enum import Enum


class AssistantStreamingState(Enum):
    NOT_STREAMING = 0
    STREAMING = 1


class ConversationInputView(QTextEdit):
    PLACEHOLDER_TEXT = "Message Assistant..."

    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window  # reference to the main window
        self.setInitialPlaceholderText()

        # A list to keep track of image attachments (file paths) pasted in this text editor
        self.pasted_attachments = []
        # A dictionary to map file_path -> the HTML snippet inserted for that image
        self.pasted_images_html = {}

    def setInitialPlaceholderText(self):
        self.setText(self.PLACEHOLDER_TEXT)

    def focusInEvent(self, event):
        # Clear the placeholder text on first focus and do not set it again
        if self.toPlainText() == self.PLACEHOLDER_TEXT:
            self.clear()
        super().focusInEvent(event)

    def keyPressEvent(self, event):
        # Clear the placeholder text on first key press and do not set it again
        if self.toPlainText() == self.PLACEHOLDER_TEXT and not event.text().isspace():
            self.clear()

        cursor = self.textCursor()
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # Save the HTML before
            html_before = self.toHtml()

            # Let the parent handle the actual deletion
            super().keyPressEvent(event)

            # Compare the HTML after
            html_after = self.toHtml()
            self.check_for_deleted_images(html_before, html_after)

        # Detect Enter/Return (no modifiers) to send the message
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            user_text = self.toPlainText()
            # Gather the pasted image file paths
            pasted_images = list(self.pasted_attachments)
            # Clear them out locally
            self.pasted_attachments.clear()

            self.main_window.on_user_input_complete(user_text, pasted_image_file_paths=pasted_images)

            self.clear()
        else:
            super().keyPressEvent(event)

    def get_and_clear_pasted_attachments(self):
        images = list(self.pasted_attachments)  # make a copy
        self.pasted_attachments.clear()
        return images

    def insertFromMimeData(self, mimeData: QMimeData):
        IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp')

        if mimeData.hasImage():
            image = QImage(mimeData.imageData())
            if not image.isNull():
                logger.debug("Inserting image from clipboard...")
                temp_dir = tempfile.gettempdir()
                file_name = self.generate_unique_filename("pasted_image.png")
                temp_path = os.path.join(temp_dir, file_name)
                image.save(temp_path)
                self.add_image_thumbnail(image, temp_path)
            else:
                logger.warning("Pasted image data was null.")
        elif mimeData.hasUrls():
            for url in mimeData.urls():
                if url.isLocalFile():
                    local_path = url.toLocalFile()
                    ext = os.path.splitext(local_path)[1].lower()
                    if ext in IMAGE_EXTENSIONS:
                        image = QImage(local_path)
                        if not image.isNull():
                            temp_dir = tempfile.gettempdir()
                            file_name = self.generate_unique_filename(os.path.basename(local_path))
                            temp_path = os.path.join(temp_dir, file_name)
                            image.save(temp_path)
                            self.add_image_thumbnail(image, temp_path)
                        else:
                            logger.warning(f"Could not load image from {local_path}")
                    else:
                        logger.info(f"Unsupported file type pasted: {local_path}")
                        super().insertFromMimeData(mimeData)
                else:
                    super().insertFromMimeData(mimeData)
        elif mimeData.hasText():
            # Plain text fallback
            super().insertFromMimeData(mimeData)
        else:
            super().insertFromMimeData(mimeData)

    def generate_unique_filename(self, base_name):
        name, ext = os.path.splitext(base_name)
        unique_name = f"{name}_{int(time.time())}_{random.randint(1000, 9999)}{ext}"
        return unique_name

    def add_image_thumbnail(self, image: QImage, file_path: str):
        image_thumbnail = image.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        image_thumbnail.save(buffer, "PNG")
        base64_data = buffer.data().toBase64().data().decode()
        html = f'<img src="data:image/png;base64,{base64_data}" alt="{file_path}" />'
        
        cursor = self.textCursor()
        cursor.insertHtml(html)
        self.pasted_images_html[file_path] = html
        if file_path not in self.pasted_attachments:
            self.pasted_attachments.append(file_path)

    def check_for_deleted_images(self, html_before: str, html_after: str):
        soup_before = BeautifulSoup(html_before, 'html.parser')
        soup_after = BeautifulSoup(html_after, 'html.parser')

        file_paths_before = {img.get('alt', '') for img in soup_before.find_all('img')}
        file_paths_after = {img.get('alt', '') for img in soup_after.find_all('img')}

        # Identify which images are missing
        missing_file_paths = file_paths_before - file_paths_after
        if missing_file_paths:
            logger.debug(f"User removed images: {missing_file_paths}")

        for file_path in missing_file_paths:
            if file_path in self.pasted_images_html:
                del self.pasted_images_html[file_path]
            if file_path in self.pasted_attachments:
                self.pasted_attachments.remove(file_path)

    def mouseReleaseEvent(self, event):
        cursor = self.cursorForPosition(event.pos())
        anchor = cursor.charFormat().anchorHref()

        if anchor:
            QDesktopServices.openUrl(QUrl(anchor))

        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)


class ClickableTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def mousePressEvent(self, event: QMouseEvent):
        cursor = self.cursorForPosition(event.pos())
        pos = cursor.position()
        text = self.toPlainText()

        text_to_url_map = self.parent.get_text_to_url_map()
        cursor.select(QTextCursor.BlockUnderCursor)  # Select the entire line (block) of text
        line_text = cursor.selectedText()

        # Check if the click is on a link in this line
        if line_text.strip() in text_to_url_map.keys():
            # get the path from map
            file_path = text_to_url_map[line_text.strip()]["path"]
            self.open_file(file_path)

        # Handle regular HTTP URLs
        for url, start, end in self.find_urls(text):
            if start <= pos <= end:
                QDesktopServices.openUrl(QUrl(url))
                return

        super().mousePressEvent(event)

    def open_file(self, file_path):
        if sys.platform.startswith('linux'):
            subprocess.call(["xdg-open", file_path])
        elif sys.platform.startswith('win32'):
            os.startfile(file_path)
        elif sys.platform.startswith('darwin'):
            subprocess.call(["open", file_path])

    def find_urls(self, text):
        url_pattern = r'\b(https?://[^\s)]+)'
        for match in re.finditer(url_pattern, text):
            yield (match.group(1), match.start(1), match.end(1))


class ConversationView(QWidget):
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window  # Store a reference to the main window
        self.assistant_config_manager = AssistantConfigManager.get_instance()
        self.init_ui()
        self.text_to_url_map = {}
        self.streaming_buffer = defaultdict(list)
        self.stream_snapshot = defaultdict(str)
        self.is_assistant_streaming = defaultdict(lambda: AssistantStreamingState.NOT_STREAMING)
        self._lock = threading.RLock()
        
        # TODO make this better configurable. To have the output folder for each assistant is good, however
        # if assistant gets destroyed at some point, the output folder cannot be accessed from assistant config
        # anymore. So maybe it could be better to have a global output folder and then subfolders for each 
        # assistant names
        self.file_path = 'output'
        # Create the output directory if it doesn't exist
        os.makedirs(self.file_path, exist_ok=True)

    def init_ui(self):
        self.layout = QVBoxLayout(self)

        self.conversationView = ClickableTextEdit(self)
        self.conversationView.setReadOnly(True)
        self.conversationView.setFont(QFont("Arial", 11))
        self.conversationView.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)

        self.inputField = ConversationInputView(self, self.main_window)
        self.inputField.setAcceptRichText(False)  # Accept only plain text
        self.inputField.setFixedHeight(100)  # Set an initial height
        self.inputField.setFont(QFont("Arial", 11))

        self.layout.addWidget(self.conversationView)
        self.layout.addWidget(self.inputField)

        self.conversationView.setStyleSheet("""
            QTextEdit {
                border: 1px solid #c0c0c0; /* Adjusted to have a 1px solid border */
                border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;
                border-radius: 4px;
                padding: 1px; /* Adds padding inside the QTextEdit widget */
            }
            .code-block {
                background-color: #eeeeee;
                font-family: "Courier New", monospace;
                border: 1px solid #cccccc; /* Thin border for code blocks */
                white-space: pre-wrap;
                display: block; /* Ensures that the block is on its own line */
                margin: 2px 0; /* Adds a small margin above and below the code block */
                outline: 1px solid #cccccc; /* Add an outline to ensure visibility */
            }
            .text-block {
                background-color: white;
                font-family: Arial;
                white-space: pre-wrap;
                display: block; /* Ensures that the block is on its own line */
                margin: 2px 0; /* Adds a small margin above and below the text block */
            }
        """)

        self.inputField.setStyleSheet(
            "QTextEdit {"
            "  border-style: solid;"
            "  border-width: 1px;"
            "  border-color: #a0a0a0 #ffffff #ffffff #a0a0a0;"  # Light on top and left, dark on bottom and right
            "  padding: 1px;"
            "}"
        )

    def get_text_to_url_map(self):
        return self.text_to_url_map

    def is_dark_mode(self):
        app = QGuiApplication.instance()
        if app is not None:
            # Get the default window background color from the application palette
            windowBackgroundColor = app.palette().color(QPalette.ColorRole.Window)
            # Calculate the lightness (value between 0 for black and 255 for white)
            lightness = windowBackgroundColor.lightness()
            # Assuming dark mode if the lightness is below a certain threshold
            # Here, 127 is used as a threshold, considering the scale is from 0 to 255
            return lightness < 127
        return False

    def append_conversation_messages(self, messages: List[ConversationMessage]):
        logger.info(f"Appending full conversation: {len(messages)} messages to the conversation view")
        self.text_to_url_map = {}
        for message in reversed(messages):
            self.append_conversation_message(message, full_messages_append=True)

    def append_conversation_message(self, message: ConversationMessage, full_messages_append=False):
        # Handle text message content
        if message.text_message:
            text_message = message.text_message
            # Determine the color based on the role and the theme
            if self.is_dark_mode():
                # Colors for dark mode
                color = 'blue' if message.sender == "user" else '#D3D3D3'
            else:
                # Colors for light mode
                color = 'blue' if message.sender == "user" else 'black'

            # Append the formatted text message
            self.append_message(message.sender, text_message.content, color=color, full_messages_append=full_messages_append)

        # Handle file message content
        if len(message.file_messages) > 0:
            for file_message in message.file_messages:
                # Synchronously retrieve and process the file
                file_path = file_message.retrieve_file(self.file_path)
                if file_path:
                    self.append_message(message.sender, f"File saved: {file_path}", color='green', full_messages_append=full_messages_append)

        # Handle image message content
        if len(message.image_messages) > 0:
            for image_message in message.image_messages:
                # Synchronously retrieve and process the image
                image_path = image_message.retrieve_image(self.file_path)
                if image_path:
                    self.append_image(image_path)

    def convert_image_to_base64(self, image_path):
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return encoded_string

    def append_image(self, image_path):
        base64_image = self.convert_image_to_base64(image_path)
        # Move cursor to the end for each insertion
        self.conversationView.moveCursor(QTextCursor.End)

        image_html = f"<img src='data:image/png;base64,{base64_image}' alt='Image' style='width:100px; height:auto;'>"
        self.conversationView.insertHtml(image_html)
        self.conversationView.insertHtml("<br><br>")

        self.scroll_to_bottom()

    def append_message(self, sender, message, color='black', full_messages_append=False):

        # Insert sender's name in bold
        html_content = f"<b style='color:{color};'>{sender}:</b> "

        with self._lock:
            if self.is_any_assistant_streaming() and sender == "user" and not full_messages_append:
                logger.info(f"Append USER MESSAGE while assistant is streaming, clear and save streaming content")
                self.clear_and_save_assistant_streaming()
            elif self.is_any_assistant_streaming() and sender != "user":
                logger.info(f"Clear ASSISTANT: {sender} streaming content, full_messages_append: {full_messages_append}")
                self.clear_assistant_streaming(sender)

            # Generate HTML content based on message segments
            for is_code, text in self.parse_message(message):
                if is_code:
                    escaped_code = html.escape(text).replace('\n', '<br>')
                    formatted_code = f"<pre class='code-block'>{escaped_code}</pre>"
                    html_content += formatted_code
                else:
                    text = self.format_file_links(text)
                    text = self.format_urls(text)
                    formatted_text = f"<span class='text-block' style='white-space: pre-wrap;'>{text}</span>"
                    html_content += formatted_text
                html_content += "<br>"
            html_content += "<br>"

            # Insert the complete HTML content in one go
            self.conversationView.moveCursor(QTextCursor.End)
            self.conversationView.insertHtml(html_content)
            self.scroll_to_bottom()

            if self.is_any_assistant_streaming() and sender == "user" and not full_messages_append:
                self.restore_assistant_streaming()

    def append_message_chunk(self, sender, message_chunk, is_start_of_message):
        with self._lock:
            # Move cursor to the end for each insertion
            self.conversationView.moveCursor(QTextCursor.End)
            if is_start_of_message:  # If a new message, insert the assistant's name in bold and black
                self.conversationView.insertHtml(f"<b style='color:black;'>{html.escape(sender)}:</b> ")
        
            escaped_text = html.escape(message_chunk)
            formatted_text = f"<span class='text-block' style='white-space: pre-wrap;'>{escaped_text}</span>"
            self.conversationView.insertHtml(formatted_text)

            self.is_assistant_streaming[sender] = AssistantStreamingState.STREAMING
            self.streaming_buffer[sender].append(message_chunk)

            self.scroll_to_bottom()

    def clear_assistant_streaming(self, assistant_name):
        with self._lock:
            self.is_assistant_streaming[assistant_name] = AssistantStreamingState.NOT_STREAMING
            self.stream_snapshot[assistant_name] = ""
            self.streaming_buffer[assistant_name].clear()

    def is_any_assistant_streaming(self):
        with self._lock:
            return any(state == AssistantStreamingState.STREAMING for state in self.is_assistant_streaming.values())

    def restore_assistant_streaming(self):
        for assistant_name in self.is_assistant_streaming.keys():
            if self.stream_snapshot[assistant_name]:
                logger.info(f"Restoring streamed content for ASSISTANT: {assistant_name}")
                logger.info(f"Restored stream snapshot: {self.stream_snapshot[assistant_name]}")
                self.conversationView.moveCursor(QTextCursor.End)
                self.conversationView.insertHtml(f"<b style='color:black;'>{html.escape(assistant_name)}:</b> ")
                self.conversationView.insertHtml(self.stream_snapshot[assistant_name])
                del self.stream_snapshot[assistant_name]
                self.is_assistant_streaming[assistant_name] = AssistantStreamingState.STREAMING

    def clear_and_save_assistant_streaming(self):
        for assistant_name in self.is_assistant_streaming.keys():
            if self.is_assistant_streaming[assistant_name] == AssistantStreamingState.STREAMING:
                logger.info(f"Clearing and saving streamed content for ASSISTANT: {assistant_name}")
                current_streamed_content = "".join(self.streaming_buffer[assistant_name])
                self.stream_snapshot[assistant_name] = current_streamed_content
                self.clear_selected_text_from_conversation(assistant_name=assistant_name, selected_text=current_streamed_content)
                logger.info(f"Saved stream snapshot: {self.stream_snapshot[assistant_name]}")
                self.streaming_buffer[assistant_name].clear()

    def clear_selected_text_from_conversation(self, assistant_name, selected_text):
        # Get the QTextEdit's current content
        current_text = self.conversationView.toPlainText()
        # Only proceed if the text ends with the selected_text
        if current_text.endswith(selected_text):
            # Create a QTextCursor associated with the QTextEdit
            cursor = self.conversationView.textCursor()
            # Calculate the position where selected_text starts, including the assistant's name and -2 for the colon and space
            start_position = cursor.position() - len(selected_text) - len(assistant_name) - 2
            # Select the text from start_position to the end of the document
            cursor.setPosition(start_position, QTextCursor.MoveAnchor)
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            # Remove the selected text
            cursor.removeSelectedText()
            # Set the modified text cursor back to the QTextEdit
            self.conversationView.setTextCursor(cursor)

    def format_urls(self, text):
        # Enhanced URL pattern that excludes punctuation at the end.
        url_pattern = re.compile(
            r'(\bhttps?://'               # Start with http:// or https://
            r'[-A-Z0-9+&@#/%=~_|$?!:.,]*' # Followed by the domain part and allowable characters in a URL.
            r'[-A-Z0-9+&@#/%=~_|$]'       # URL must finish with an allowable character to avoid punctuation at the end.
            r')', re.IGNORECASE)           # Make the regex case-insensitive.
        
        # Function to add HTML anchor tag around URLs.
        def replace_with_link(match):
            url = match.group(0)
            return f'<a href="{url}" style="color:blue; text-decoration: underline;">{url}</a>'

        # Substitute URLs in the text with HTML anchor tags.
        return url_pattern.sub(replace_with_link, text)

    def format_file_links(self, text):
        # Pattern to find citations in the form [Download text]( [index])
        citation_link_pattern = r'\[([^\]]+)\]\(\s*\[(\d+)\]\s*\)'
        # Dictionary to store file paths indexed by the citation index
        citation_to_filename = {}

        # First, extract all file citations like "[0] finance_sector_revenue_chart.png"
        file_citations = re.findall(r'\[(\d+)\]\s*(.+)', text)
        for index, filename in file_citations:
            citation_to_filename[index] = filename

        # Function to replace citation links with clickable HTML links
        def replace_with_clickable_text(match):
            link_text = match.group(1)
            citation_index = match.group(2)
            file_name = citation_to_filename.get(citation_index)

            if file_name:
                local_file_path = os.path.normpath(os.path.join(self.file_path, file_name))

                if link_text in self.text_to_url_map:
                    link_text = f"{link_text} {len(self.text_to_url_map) + 1}"
                
                # Store the file path
                self.text_to_url_map[link_text] = {"path": local_file_path}

                # Return the HTML link and the local file path in separate inline-block divs
                return (f'<div style="display: inline-block;"><a href="{local_file_path}" style="color:green; text-decoration: underline;" download="{file_name}">{link_text}</a></div>'
                        f'<div style="display: inline-block; color:gray;">{local_file_path}</div>')

        # Replace links in the original text
        updated_text = re.sub(citation_link_pattern, replace_with_clickable_text, text)

        # Remove the original citation lines
        updated_text = re.sub(r'\[\d+\]\s*[^ ]+\.png', '', updated_text)

        return updated_text

    def parse_message(self, message):
        """Parse the message into a list of (is_code, text) tuples."""
        segments = []
        # Split the message on code block delimiters
        parts = message.split("```")

        # Iterate over the parts and determine if they are code blocks
        for i, part in enumerate(parts):
            is_code = i % 2 != 0  # Code blocks are at odd indices
            if is_code:
                # Attempt to find a language identifier at the beginning of the code block
                lines = part.split('\n', 1)
                if len(lines) > 1:  # Check if there's more than one line
                    language, code = lines
                    language = language.strip()  # This is your language identifier, e.g., 'java'
                    segments.append((is_code, code.strip('\n')))  # Append without the language line
                else:
                    # No language line present, just append the code
                    segments.append((is_code, part.strip('\n')))
            else:
                segments.append((is_code, part))
        return segments

    def scroll_to_bottom(self):
        scrollbar = self.conversationView.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self.conversationView.update()