# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import logging
import os

def setup_logger() -> logging.Logger:
    """
    Sets up a logger named 'assistant_logger' with INFO level. The logger configuration for console logging
    is determined by the environment variable ASSISTANT_LOG_TO_CONSOLE. If ASSISTANT_LOG_TO_CONSOLE is not set or set to a value
    that does not equate to 'true', logging will default to file only. This version also includes the function
    name in the log messages.

    :return: The logger instance.
    :rtype: logging.Logger
    """
    logger = logging.getLogger('assistant_logger')
    logger.setLevel(logging.INFO)
    
    # Including function name in the log message format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')

    # Environment variable check for console logging
    log_to_console = os.getenv('ASSISTANT_LOG_TO_CONSOLE', 'false').lower() in ('true', '1', 't')

    # Default to file logging if ASSISTANT_LOG_TO_CONSOLE is not 'true'
    log_to_file = not log_to_console

    if log_to_file:
        # Set the file handler with UTF-8 encoding for file output
        file_handler = logging.FileHandler('assistant.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if log_to_console:
        # Set the stream handler for console output
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger

# Example usage:
# To enable console logging, set the environment variable ASSISTANT_LOG_TO_CONSOLE=true before running the script.
# If ASSISTANT_LOG_TO_CONSOLE is not set or set to false, logging will default to file.

# Create the logger instance based on the environment variable
logger = setup_logger()