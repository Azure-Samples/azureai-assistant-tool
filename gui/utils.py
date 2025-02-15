# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# This software uses the PySide6 library, which is licensed under the GNU Lesser General Public License (LGPL).
# For more details on PySide6's license, see <https://www.qt.io/licensing>

import os
import sys
import re
from typing import Optional

from PySide6.QtWidgets import QMessageBox

from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.ai_client_factory import AIClientFactory
from azure.ai.assistant.management.ai_client_factory import AIClientType
from azure.ai.assistant.management.chat_assistant_client import ChatAssistantClient


def resource_path(relative_path):
    """ 
    Get absolute path to resource, works for development and for PyInstaller 
    """
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


def camel_to_snake(name):
    """
    Convert camel case to snake case
    """
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def init_system_assistant(instance, assistant_name: str):
    """
    Initialize the system assistant
    """
    # Fetch assistant config using assistant name
    assistant_config: AssistantConfig = instance.assistant_config_manager.get_config(assistant_name)
    
    try:
        ai_client_type: AIClientType = instance.system_client_type
        if ai_client_type is None:
            QMessageBox.warning(instance, "Warning", f"Selected system AI client is not initialized properly, system assistant {assistant_name} may not work as expected.")
            return
        else:
            # Update the ai_client_type in the assistant_config
            assistant_config.ai_client_type = ai_client_type

        if not assistant_config.model or assistant_config.model != instance.system_model:
            logger.warning(f"Model not found in the {assistant_name} assistant config, using the system assistant model.")
            assistant_config.model = instance.system_model

        if not assistant_config.model:
            error_message = f"Model not found in the {assistant_name} assistant config, and system assistant model is not set."
            QMessageBox.warning(instance, "Warning", error_message)
            return

        # Then, use it when setting the attribute:
        setattr(instance, camel_to_snake(assistant_name), ChatAssistantClient.from_config(assistant_config))

    except Exception as e:
        error_message = f"An error occurred while initializing the {assistant_name} assistant, check the system settings: {e}"
        QMessageBox.warning(instance, "Error", error_message)


def get_ai_client(ai_client_type: AIClientType) -> Optional[object]:
    """
    Returns an AI client instance for the given AIClientType, or None if unavailable.
    Logs an error if any exception occurs during creation.
    """
    client_factory = AIClientFactory.get_instance()

    client_map = {
        AIClientType.AZURE_OPEN_AI:           lambda: client_factory.get_client(AIClientType.AZURE_OPEN_AI),
        AIClientType.OPEN_AI:                 lambda: client_factory.get_client(AIClientType.OPEN_AI),
        AIClientType.OPEN_AI_REALTIME:        lambda: client_factory.get_client(AIClientType.OPEN_AI_REALTIME),
        AIClientType.AZURE_OPEN_AI_REALTIME:  lambda: client_factory.get_client(AIClientType.AZURE_OPEN_AI_REALTIME),
        AIClientType.AZURE_AI_AGENT:          lambda: client_factory.get_client(AIClientType.AZURE_AI_AGENT),
    }

    try:
        # Use a default of None if the type isn’t recognized
        return client_map.get(ai_client_type, lambda: None)()
    except Exception as e:
        logger.error(f"[get_ai_client] Error getting client for {ai_client_type.name}: {e}")
        return None