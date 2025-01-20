# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import logging
import os


class BroadcasterLoggingHandler(logging.Handler):
    def __init__(self, broadcaster):
        super().__init__()
        self.broadcaster = broadcaster

    def emit(self, record):
        try:
            message = self.format(record)
            self.broadcaster.emit(message)
        except Exception:
            self.handleError(record)

def setup_logger() -> logging.Logger:
    """
    Sets up a logger named 'assistant_logger' with INFO level. The logger configuration for console logging
    is determined by the environment variable ASSISTANT_LOG_TO_CONSOLE. If ASSISTANT_LOG_TO_CONSOLE is not set or set to a value
    that does not equate to 'true', logging will default to file only. This version also includes the function
    name in the log messages.

    :return: The logger instance.
    :rtype: logging.Logger
    """

    realtime_ai_package_logger = logging.getLogger('realtime_ai')
    realtime_ai_package_logger.setLevel(logging.CRITICAL)

    logger = logging.getLogger('assistant_logger')
    logger.setLevel(logging.INFO)
    
    # Disable by default
    logger.disabled = True

    # Including function name in the log message format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')

    # Environment variable check for console logging
    log_to_console = os.getenv('ASSISTANT_LOG_TO_CONSOLE', 'false').lower() in ('true', '1', 't')

    log_to_file = os.getenv('ASSISTANT_LOG_TO_FILE', 'false').lower() in ('true', '1', 't')

    if log_to_file:
        logger.disabled = False
        # Set the file handler with UTF-8 encoding for file output
        file_handler = logging.FileHandler('assistant.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if log_to_console:
        logger.disabled = False
        # Set the stream handler for console output
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger

def add_broadcaster_to_logger(broadcaster) -> None:
    """
    Adds or updates the broadcaster in the global logger.

    :param broadcaster: An instance of LogBroadcaster to broadcast log messages.
    """
    global logger

    logger.disabled = False
    # Check if a BroadcasterLoggingHandler is already added and update it
    for handler in logger.handlers:
        if isinstance(handler, BroadcasterLoggingHandler):
            handler.broadcaster = broadcaster
            break
    else:  # If no BroadcasterLoggingHandler is found, add a new one
        broadcast_handler = BroadcasterLoggingHandler(broadcaster)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')
        broadcast_handler.setFormatter(formatter)
        logger.addHandler(broadcast_handler)

    # Function to add broadcaster to any logger
    def add_broadcaster_to_specific_logger(target_logger):
        # Check if a BroadcasterLoggingHandler is already added and update it
        for handler in target_logger.handlers:
            if isinstance(handler, BroadcasterLoggingHandler):
                handler.broadcaster = broadcaster
                return  # Exit if the broadcaster is already added
        
        # If no BroadcasterLoggingHandler is found, add a new one
        broadcast_handler = BroadcasterLoggingHandler(broadcaster)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')
        broadcast_handler.setFormatter(formatter)
        target_logger.addHandler(broadcast_handler)
    
    # Add broadcaster to the global logger
    add_broadcaster_to_specific_logger(logger)

    # Add broadcaster to the OpenAI logger
    openai_logger = logging.getLogger("openai")
    add_broadcaster_to_specific_logger(openai_logger)

# Example usage:
# To enable console logging, set the environment variable ASSISTANT_LOG_TO_CONSOLE=true before running the script.
# If ASSISTANT_LOG_TO_CONSOLE is not set or set to false, logging will default to file.

# Create the logger instance based on the environment variable
logger = setup_logger()