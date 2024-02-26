# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

from PySide6.QtWidgets import QApplication

import sys

from gui.main_window import MainWindow


def main():
    # Create an instance of QApplication
    app = QApplication(sys.argv)

    # Initialize the main window with engine components
    main_window = MainWindow()

    # Show the main window
    main_window.show()

    # Execute the application's main loop
    sys.exit(app.exec())

if __name__ == '__main__':
    main()