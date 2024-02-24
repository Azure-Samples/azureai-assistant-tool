# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QTextEdit, QMessageBox

import json


class DirectivesDialog(QDialog):
    def __init__(self, title, parent=None, guidelinesFilePath=None):
        super().__init__(parent)
        self.title = title
        self.guidelinesFilePath = guidelinesFilePath
        self.initUI()
        self.loadGuidelines()

    def initUI(self):
        self.setWindowTitle(self.title)
        self.resize(600, 400)
        layout = QVBoxLayout()

        # QTextEdit for entering instructions guidelines
        self.guidelinesEdit = QTextEdit()
        #self.guidelinesEdit.setFont(QFont("Arial", 14))  # Set font and size
        layout.addWidget(self.guidelinesEdit)

        # 'Retrieve Latest Guidelines' button
        retrieveGuidelinesButton = QPushButton('Retrieve Latest Guidelines')
        retrieveGuidelinesButton.clicked.connect(self.loadGuidelines)
        layout.addWidget(retrieveGuidelinesButton)

        # 'Save Guidelines' button
        saveGuidelinesButton = QPushButton('Save Guidelines')
        saveGuidelinesButton.clicked.connect(self.saveGuidelines)
        layout.addWidget(saveGuidelinesButton)

        self.setLayout(layout)

    def loadGuidelines(self):
        try:
            with open(self.guidelinesFilePath, 'r') as file:
                guidelines = json.load(file)
                formatted_guidelines = "\n".join([f"{key}. {value}" for key, value in guidelines.items()])
                self.guidelinesEdit.setPlainText(formatted_guidelines)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while reading the guidelines: {e}")

    def saveGuidelines(self):
        try:
            guidelines_text = self.guidelinesEdit.toPlainText()
            guidelines = {line.split('. ')[0]: '. '.join(line.split('. ')[1:]) 
                          for line in guidelines_text.split('\n') if line}
            with open(self.guidelinesFilePath, 'w') as file:
                json.dump(guidelines, file, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred while saving the guidelines: {e}")