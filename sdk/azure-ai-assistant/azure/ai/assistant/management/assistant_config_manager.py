# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import json
import os
from typing import Optional
from azure.ai.assistant.management.assistant_config import AssistantConfig
from azure.ai.assistant.management.exceptions import ConfigError, DeleteConfigError, InvalidJSONError
from azure.ai.assistant.management.logger_module import logger


class AssistantConfigManager:
    _instance = None

    """
    A class to manage the creation, updating, deletion, and loading of assistant configurations from local files.

    :param config_folder: The folder path for storing configuration files. Optional, defaults to 'config'.
    :type config_folder: str
    """
    def __init__(
            self, 
            config_folder : str ='config'
    ) -> None:
        self._config_folder = config_folder
        self._last_modified_assistant_name = None
        self._configs: dict[str, AssistantConfig] = {}
        # Load all assistant configurations under the config folder
        self.load_configs()

    @classmethod
    def get_instance(
        cls, 
        config_folder : str ='config'
    ) -> 'AssistantConfigManager':
        """
        Gets the singleton instance of the AssistantConfigManager object.
        
        :param config_folder: The folder path for storing configuration files. Optional, defaults to 'config'.
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
        Updates an existing assistant local configuration.
        
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
            self._validate_json_config(new_config_data)
            name = self._save_config(name, new_config_data)
            self._last_modified_assistant_name = name
            return name
        except json.JSONDecodeError as e:
            raise InvalidJSONError(f"Invalid JSON format: {e}")
        except Exception as e:
            raise ConfigError(f"An unexpected error occurred: {e}")

    def delete_config(
            self, 
            name : str
    ) -> bool:
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

            # Construct the path to the configuration file and delete it
            config_filename = f"{name}_assistant_config.json"
            config_path = os.path.join(self._config_folder, config_filename)
            if os.path.exists(config_path):
                os.remove(config_path)
            return True

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
        Loads all assistant local configurations from json files.
        """
        config_files = []
        try:
            # Get the list of files in the config folder
            config_files = os.listdir(self._config_folder)
        except FileNotFoundError:
            logger.warning("No assistant configurations found in the config folder.")
            return

        for filename in config_files:
            if filename.endswith('_assistant_config.json'):
                file_path = os.path.join(self._config_folder, filename)
                try:
                    logger.info(f"Loading assistant configuration from '{file_path}'")
                    with open(file_path, 'r') as file:
                        config_data = json.load(file)
                        assistant_name = config_data.get('name')
                        if assistant_name:
                            logger.info(f"Loading assistant configuration for '{assistant_name}'")
                            assistant_config = AssistantConfig(assistant_name, config_data)
                            self._configs[assistant_name] = assistant_config

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in the assistant configuration file '{file_path}'.")
                    continue  # Skip this file and continue with the next

        if not self._configs:
            logger.warning("No valid assistant configurations found.")

        self._set_last_modified_assistant()

    def _set_last_modified_assistant(self):
        latest_mod_time = None
        latest_assistant_name = None

        for assistant_name, assistant_config in self._configs.items():
            file_path = os.path.join(self._config_folder, f"{assistant_name}_assistant_config.json")
            try:
                mod_time = os.path.getmtime(file_path)

                if not latest_mod_time or mod_time > latest_mod_time:
                    latest_mod_time = mod_time
                    latest_assistant_name = assistant_name

            except FileNotFoundError:
                logger.warning(f"Configuration file for '{assistant_name}' not found.")
                continue

        self._last_modified_assistant_name = latest_assistant_name

    def save_configs(self) -> None:
        """
        Saves all assistant local configurations to json files.
        """
        # Save all assistant configurations to files
        for assistant_name, assistant_config in self._configs.items():
            self._save_config(assistant_name, assistant_config._get_config_data())

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

    def _validate_json_config(self, config_data):
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

        # Check if selected functions is in config_data, it is valid list
        if 'selected_functions' in config_data and not isinstance(config_data['selected_functions'], list):
            raise ConfigError("Assistant 'selected_functions' must be a list in the configuration")
        # Check if knowledge files is in config_data, it is valid dictionary in dictionary
        if 'knowledge_files' in config_data and not isinstance(config_data['knowledge_files'], dict):
            raise ConfigError("Assistant 'knowledge_files' must be a dictionary in the configuration")

    def _save_config(self, assistant_name, config_data):
        if not assistant_name:
            raise ConfigError("Assistant name is required")

        if not config_data:
            raise ConfigError("Assistant configuration data is required")

        logger.info(f"Checking for updates in assistant configuration for '{assistant_name}'")

         # Use the name from the updated config data in case it was changed
        if config_data['name'] != assistant_name:
            logger.info(f"Assistant name changed from '{assistant_name}' to \"{config_data['name']}\"")
            # delete the old config file
            config_filename = f"{assistant_name}_assistant_config.json"
            config_path = os.path.join(self._config_folder, config_filename)
            if os.path.exists(config_path):
                try:
                    os.remove(config_path)
                except Exception as e:
                    logger.error(f"Error deleting file: {e}")
            # copy the old config to the new name in the in-memory dictionary
            self._configs[config_data['name']] = self._configs[assistant_name]
            # remove the old config from the in-memory dictionary
            self._configs.pop(assistant_name, None)
            # update the assistant name to the new name
            assistant_name = config_data['name']

        # Construct the path to the configuration file
        config_filename = f"{assistant_name}_assistant_config.json"
        config_path = os.path.join(self._config_folder, config_filename)

        # Update in-memory configs
        self._configs[assistant_name] = AssistantConfig(assistant_name, config_data)
        
        # Check if the configuration file exists and read its content
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as file:
                    existing_config_data = json.load(file)
                    if existing_config_data == config_data:
                        logger.info(f"No changes detected in configuration for '{assistant_name}'. Save skipped.")
                        return assistant_name
            except Exception as e:
                logger.error(f"Error reading file: {e}")

        # Proceed to save if there are changes or file doesn't exist
        logger.info(f"Saving updated configuration for '{assistant_name}'")

        # Create config folder if it doesn't exist
        if not os.path.exists(self._config_folder):
            try:
                os.makedirs(self._config_folder)
            except Exception as e:
                logger.error(f"Error creating config directory: {e}")
                raise ConfigError(f"Error creating config directory: {e}")

        try:
            with open(config_path, 'w') as file:
                json.dump(config_data, file, indent=4)
        except Exception as e:
            logger.error(f"Error writing to file: {e}")
            raise ConfigError(f"Error writing to file: {e}")

        return assistant_name

    @property
    def configs(self) -> dict:
        """
        Gets the dictionary of assistant configurations.

        :return: The dictionary of assistant configurations.
        :rtype: dict
        """
        return self._configs