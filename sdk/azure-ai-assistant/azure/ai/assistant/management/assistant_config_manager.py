# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.exceptions import ConfigError, DeleteConfigError, InvalidJSONError
from azure.ai.assistant.management.logger_module import logger

import json, os, yaml
from typing import Optional


def _represent_literal_block(dumper, data):
    """Custom representer for handling multiline strings."""
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, _represent_literal_block)


class AssistantConfigManager:
    _instance = None

    """
    A class to manage the creation, updating, deletion, and loading of assistant configurations from local files.

    :param config_folder: The folder path for storing configuration files. Optional, defaults to config folder in the user's home directory.
    :type config_folder: str
    """
    def __init__(
            self, 
            config_folder : Optional[str] = None
    ) -> None:
        if config_folder is None:
            self._config_folder = self._default_config_path()
        else:
            self._config_folder = config_folder
        self._last_modified_assistant_name = None
        self._configs: dict[str, AssistantConfig] = {}
        # Load all assistant configurations under the config folder
        self.load_configs()

    @staticmethod
    def _default_config_path() -> str:
        home = os.path.expanduser("~")
        return os.path.join(home, ".config", 'azure-ai-assistant')

    @classmethod
    def get_instance(
        cls, 
        config_folder : Optional[str] = None

    ) -> 'AssistantConfigManager':
        """
        Gets the singleton instance of the AssistantConfigManager object.
        
        :param config_folder: The folder path for storing configuration files. Optional, defaults to config folder in the user's home directory.
        :type config_folder: str

        :return: The singleton instance of the AssistantConfigManager object.
        :rtype: AssistantConfigManager
        """
        if cls._instance is None:
            cls._instance = cls(config_folder)
        return cls._instance

    def update_config(
            self, 
            name : str,
            config_json : str
    ) -> str:
        """
        Updates an existing assistant local configuration in memory.

        :param name: The name of the configuration to update.
        :type name: str
        :param config_json: The JSON string containing the updated configuration data.
        :type config_json: str

        :return: The name of the updated configuration.
        :rtype: str
        """
        try:
            logger.info(f"Updating assistant configuration for '{name}' with data: {config_json}")
            new_config_data = json.loads(config_json)
            self._validate_config(new_config_data)
            
            # Update the configuration in memory without saving to a file
            self._configs[name] = AssistantConfig(new_config_data)
            self._last_modified_assistant_name = name

            return name
        except json.JSONDecodeError as e:
            raise InvalidJSONError(f"Invalid JSON format: {e}")
        except Exception as e:
            raise ConfigError(f"An unexpected error occurred: {e}")

    def delete_config(self, name: str) -> bool:
        """
        Deletes an existing assistant local configuration.
        
        :param name: The name of the configuration to delete.
        :type name: str

        :return: True if the configuration is deleted successfully, False otherwise.
        :rtype: bool
        """
        if name not in self._configs:
            logger.warning(f"No configuration found for '{name}'")
            return False

        try:
            # Delete the configuration from the in-memory dictionary
            del self._configs[name]

            # List of possible configuration file extensions
            config_extensions = ['.json', '.yaml', '.yml']
            deletion_successful = False

            # Iterate over each extension and attempt to delete the file if it exists
            for extension in config_extensions:
                config_path = os.path.join(self._config_folder, f"{name}_assistant_config{extension}")
                if os.path.exists(config_path):
                    os.remove(config_path)
                    deletion_successful = True
                    logger.info(f"Deleted configuration file: {config_path}")

            return deletion_successful

        except Exception as e:
            raise DeleteConfigError(f"An error occurred while deleting the configuration: {e}")

    def get_config(
            self, 
            name : str
    ) -> Optional[AssistantConfig]:
        """
        Gets an existing assistant local configuration.
        
        :param name: The name of the configuration to get.
        :type name: str

        :return: The AssistantConfig object for the given name, or None if the configuration does not exist.
        :rtype: Optional[AssistantConfig]
        """
        # Check if the configuration for the given name exists
        if name not in self._configs:
            logger.warning(f"No configuration found for '{name}'")
            return None

        # Return the AssistantConfig object for the given name
        return self._configs.get(name, None)

    def load_configs(self) -> None:
        """
        Loads all assistant local configurations from JSON and YAML (both .yaml and .yml) files using the load_config method.
        """
        try:
            config_files = os.listdir(self._config_folder)
        except FileNotFoundError:
            logger.warning(f"No assistant configurations found in the folder '{self._config_folder}'")
            return

        loaded_assistants = set()  # Track loaded assistant names to prevent duplicates
        # Identify base names to be processed
        for filename in config_files:
            if filename.endswith(('_assistant_config.json', '_assistant_config.yaml', '_assistant_config.yml')):
                base_name = filename.split('_assistant_config')[0]
                if base_name not in loaded_assistants:
                    self._load_config(base_name)
                    loaded_assistants.add(base_name)

        if not self._configs:
            logger.warning("No valid assistant configurations found.")

        self._set_last_modified_assistant()

    def _load_config(self, base_name: str) -> None:
        # Try loading JSON first, then YAML
        extensions = ['_assistant_config.json', '_assistant_config.yaml', '_assistant_config.yml']
        for ext in extensions:
            file_path = os.path.join(self._config_folder, base_name + ext)
            if os.path.exists(file_path):
                try:
                    logger.info(f"Loading assistant configuration from '{file_path}'")
                    if file_path.endswith('.json'):
                        with open(file_path, 'r') as file:
                            config_data = json.load(file)
                    else:  # For .yaml or .yml
                        with open(file_path, 'r') as file:
                            config_data = yaml.safe_load(file)

                    assistant_name = config_data.get('name')
                    if assistant_name:
                        logger.info(f"Loaded assistant configuration for '{assistant_name}'")
                        assistant_config = AssistantConfig(config_data)
                        self._configs[assistant_name] = assistant_config
                        return  # Stop after successfully loading one format to avoid duplicates
                except (json.JSONDecodeError, yaml.YAMLError) as e:
                    logger.warning(f"Invalid format in the assistant configuration file '{file_path}': {e}")

    def _set_last_modified_assistant(self):
        latest_mod_time = None
        latest_assistant_name = None

        for assistant_name, assistant_config in self._configs.items():
            file_path = os.path.join(self._config_folder, f"{assistant_name}_assistant_config.yaml")
            try:
                mod_time = os.path.getmtime(file_path)

                if not latest_mod_time or mod_time > latest_mod_time:
                    latest_mod_time = mod_time
                    latest_assistant_name = assistant_name

            except FileNotFoundError:
                logger.warning(f"Configuration file for '{assistant_name}' not found.")
                continue

        self._last_modified_assistant_name = latest_assistant_name

    def save_configs(
            self, 
            config_folder: Optional[str] = None
    ) -> None:
        """
        Saves all assistant local configurations to json files.

        :param config_folder: The folder path where the configuration files should be saved. Optional, defaults to the config folder.
        :type config_folder: str
        """
        # Save all assistant configurations to files
        for assistant_name, assistant_config in self._configs.items():
            self.save_config(assistant_name, config_folder or self._config_folder)

    def get_last_modified_assistant(self) -> str:
        """
        Gets the name of the assistant, which was modified most recently.
        This is used to select the current assistant when the application starts.

        :return: The name of the assistant, which was modified most recently.
        :rtype: str
        """
        return self._last_modified_assistant_name

    def get_all_assistant_names(self) -> list:
        """
        Gets the names of all assistants in local configuration.

        :return: A list of all assistant names.
        :rtype: list
        """
        # Return the names of all assistant configurations and where "assistant_role" is not "system"
        return [assistant_name for assistant_name, assistant_config in self._configs.items()]

    def get_assistant_names_by_client_type(
            self,
            ai_client_type : str,
            include_system_assistants : bool = False
    ) -> list:
        """
        Gets the names of all assistants based on the AI client type.

        :param ai_client_type: The AI client type to filter the assistant names.
        :type ai_client_type: str

        :return: A list of assistant names based on the AI client type.
        :rtype: list
        """
        # Return the names of all assistant configurations
        if include_system_assistants:
            return [assistant_name for assistant_name, assistant_config in self._configs.items() if assistant_config.ai_client_type == ai_client_type]
        else:
            return [assistant_name for assistant_name, assistant_config in self._configs.items() if (assistant_config.ai_client_type == ai_client_type and assistant_config.assistant_role != "system")]

    def get_assistant_name_by_assistant_id(
            self,
            assistant_id : str
    ) -> str:
        """
        Gets the name of the assistant with the given assistant ID.

        :param assistant_id: The assistant ID to search for.
        :type assistant_id: str

        :return: The name of the assistant configuration with the given assistant ID.
        :rtype: str
        """
        # Return the name of the assistant configuration with the given assistant ID
        for assistant_name, assistant_config in self._configs.items():
            if assistant_config.assistant_id == assistant_id:
                return assistant_name

    def _validate_config(self, config_data):
        if not isinstance(config_data, dict):
            raise ConfigError("Configuration data must be a dictionary")

        # Check for required fields, e.g., 'name'
        if 'name' not in config_data or not config_data['name']:
            raise ConfigError("Assistant 'name' is required in the configuration")
        if 'instructions' not in config_data or not config_data['instructions']:
            raise ConfigError("Assistant 'instructions' are required in the configuration")
        if 'model' not in config_data or not config_data['model']:
            raise ConfigError("Assistant 'model' is required in the configuration")
        if 'assistant_id' not in config_data:
            raise ConfigError("Assistant 'assistant_id' is required in the configuration")

        # Check if functions is in config_data, it is valid list
        if 'functions' in config_data and not isinstance(config_data['functions'], list):
            raise ConfigError("Assistant 'functions' must be a list in the configuration")
        # Check if tool resources is in config_data, it is valid dictionary in dictionary
        if 'tool_resources' in config_data and config_data.get('tool_resources') is not None and not isinstance(config_data['tool_resources'], dict):
            raise ConfigError("Assistant 'tool_resources' must be a dictionary in the configuration")

    def save_config(
            self, 
            name: str, 
            folder_path : Optional[str] = None
    ) -> None:
        """
        Saves the specified assistant configuration to a file in the given directory.

        :param name: The name of the assistant configuration to save.
        :type name: str
        :param folder_path: The directory path where the configuration file should be saved. Optional, defaults to the config folder.
        :type folder_path: str
        """
        if name not in self._configs:
            raise ConfigError(f"No configuration found for '{name}'")

        config_data = self._configs[name]._get_config_data()  # assuming AssistantConfig has a method to get its data
        config_filename = f"{name}_assistant_config.yaml"
        folder_path = folder_path or self._config_folder
        config_path = os.path.join(folder_path, config_filename)

        # Ensure the directory exists
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        # Save the configuration data in YAML format
        try:
            with open(config_path, 'w') as file:
                yaml.dump(config_data, file, sort_keys=False)
            logger.info(f"Configuration for '{name}' saved successfully at '{config_path}'")
        except Exception as e:
            logger.error(f"Error saving configuration file at '{config_path}': {e}")
            raise ConfigError(f"Error saving configuration file: {e}")

    @property
    def configs(self) -> dict:
        """
        Gets the dictionary of assistant configurations.

        :return: The dictionary of assistant configurations.
        :rtype: dict
        """
        return self._configs