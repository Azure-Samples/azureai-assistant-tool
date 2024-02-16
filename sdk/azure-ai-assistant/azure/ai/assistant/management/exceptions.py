# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

class EngineError(Exception):
    """Base class for all exceptions in the engine module."""
    pass

class ConfigError(EngineError):
    """General exception for configuration-related errors."""
    pass

class InvalidJSONError(ConfigError):
    """Exception raised for errors in JSON format."""
    pass

class DuplicateConfigError(ConfigError):
    """Exception raised for duplicate configuration entries."""
    pass

class UpdateConfigError(ConfigError):
    """Exception raised during configuration update errors."""
    pass

class DeleteConfigError(ConfigError):
    """Exception raised when deletion of configuration fails."""
    pass
