# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import sys
import os
from azure.ai.assistant.management.logger_module import logger


def resource_path(relative_path):
    """ Get absolute path to resource, works for development and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        logger.info("Running in PyInstaller mode")
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        logger.info("Running in normal mode")
        base_path = os.path.abspath(".")

    path = os.path.join(base_path, relative_path)
    logger.info(f"Resource path: {path}")
    return path