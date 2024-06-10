# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.ai_client_factory import AIClientType
from azure.ai.assistant.management.attachment import Attachment
from azure.ai.assistant.management.logger_module import logger

import json, os
from typing import Optional, List


class ConversationThreadConfig:
    """
    A class to manage conversation threads.

    :param ai_client_type: The type of AI client to use.
    :type ai_client_type: AIClientType
    :param config_file: The path to the configuration file.
    :type config_file: str
    """
    def __init__(
            self, 
            ai_client_type: AIClientType,
            config_folder : Optional[str] = None,
    ) -> None:
        self._ai_client_type = ai_client_type.name
        if config_folder:
            self._config_file = os.path.join(config_folder, 'threads.json')
        else:
            self._config_file = None
        self._config_data = {}
        self._current_thread_id = None
        self._threads = []
        # Initialize the list of threads
        self.get_all_threads()

    def add_thread(self, thread_id, thread_name) -> None:
        """
        Add a new thread, ensuring the thread name is unique.
        
        :param thread_id: The ID of the thread.
        :type thread_id: str
        :param thread_name: The name of the thread.
        :type thread_name: str
        """
        unique_thread_name = self._generate_unique_thread_name(thread_name)
        if not any(thread['thread_id'] == thread_id for thread in self._threads):
            self._threads.append({'thread_id': thread_id, 'thread_name': unique_thread_name})

    def remove_thread_by_name(self, thread_name) -> None:
        """
        Remove a thread by its name.
        
        :param thread_name: The name of the thread.
        :type thread_name: str
        """
        thread_id_to_remove = None
        for thread in self._threads:
            if thread['thread_name'] == thread_name:
                thread_id_to_remove = thread['thread_id']
                break

        if thread_id_to_remove:
            self._threads = [thread for thread in self._threads if thread['thread_id'] != thread_id_to_remove]

            if self._current_thread_id == thread_id_to_remove:
                self._current_thread_id = None

    def remove_thread_by_id(self, thread_id) -> None:
        """
        Remove a thread by its ID.
        
        :param thread_id: The ID of the thread.
        :type thread_id: str
        """
        self._threads = [thread for thread in self._threads if thread['thread_id'] != thread_id]

        # Update current_thread_id if it was the thread being removed
        if self._current_thread_id == thread_id:
            self._current_thread_id = None

    def set_current_thread_by_name(self, thread_name) -> None:
        """
        Set the current thread by its name.
        
        :param thread_name: The name of the thread.
        :type thread_name: str
        """
        for thread in self._threads:
            if thread['thread_name'] == thread_name:
                self._current_thread_id = thread['thread_id']
                break

    def set_current_thread_by_id(self, thread_id) -> None:
        """
        Set the current thread by its ID.
        
        :param thread_id: The ID of the thread.
        :type thread_id: str
        """
        if any(thread['thread_id'] == thread_id for thread in self._threads):
            self._current_thread_id = thread_id

    def update_thread_name(self, thread_id, new_thread_name) -> None:
        """
        Update the name of a thread ensuring the new name is unique.
        
        :param thread_id: The ID of the thread.
        :type thread_id: str
        :param new_thread_name: The new name of the thread.
        :type new_thread_name: str
        """
        unique_thread_name = self._generate_unique_thread_name(new_thread_name)
        for thread in self._threads:
            if thread['thread_id'] == thread_id:
                thread['thread_name'] = unique_thread_name
                break

    def _generate_unique_thread_name(self, desired_name) -> str:
        if not any(thread['thread_name'] == desired_name for thread in self._threads):
            return desired_name

        i = 1
        while any(thread['thread_name'] == f"{desired_name} {i}" for thread in self._threads):
            i += 1
        return f"{desired_name} {i}"

    def get_thread_id_by_name(self, thread_name) -> str:
        """
        Get the thread ID for a given thread name.
        
        :param thread_name: The name of the thread.
        :type thread_name: str

        :return: The ID of the thread.
        :rtype: str
        """
        for thread in self._threads:
            if thread['thread_name'] == thread_name:
                return thread['thread_id']
        return None

    def get_thread_name_by_id(self, thread_id) -> str:
        """
        Get the name of a thread by its ID.
        
        :param thread_id: The ID of the thread.
        :type thread_id: str

        :return: The name of the thread.
        :rtype: str
        """
        for thread in self._threads:
            if thread['thread_id'] == thread_id:
                return thread['thread_name']
        return None

    def get_current_thread_id(self) -> str:
        """
        Get the current thread ID.
        
        :return: The ID of the current thread.
        :rtype: str
        """
        return self._current_thread_id

    def get_all_thread_names(self) -> list:
        """
        Get a list of all thread names.

        :return: A list of all thread names.
        :rtype: list
        """
        return [thread['thread_name'] for thread in self._threads]

    def get_all_thread_ids(self) -> list:
        """
        Get a list of all thread ids.
        
        :return: A list of all thread ids.
        :rtype: list
        """
        return [thread['thread_id'] for thread in self._threads]

    def get_all_threads(self) -> list:
        """
        Get a list of all threads for the specific ai_client_type.
        
        :return: A list of all threads.
        :rtype: list
        """
        # create config file if it doesn't exist
        if self._config_file is None:
            return []

        try:
            with open(self._config_file, 'r') as f:
                pass
        except FileNotFoundError:
            self.save_to_json()

        # Load threads from the config file
        with open(self._config_file, 'r') as f:
            self._config_data = json.load(f)

        # Fetching threads for the specific ai_client_type
        ai_client_type_data = self._config_data.get(self._ai_client_type, {})
        self._threads = ai_client_type_data.get('threads', [])

        return self._threads

    def add_attachments_to_thread(self, thread_id: str, attachments: List[Attachment]) -> None:
        """
        Add attachments to a specific thread. Each attachment is an instance of Attachment.
        
        :param thread_id: The ID of the thread.
        :type thread_id: str
        :param attachments: A list of Attachment instances to add to the thread.
        :type attachments: list
        """
        for thread in self._threads:
            if thread['thread_id'] == thread_id:
                if 'attachments' not in thread:
                    thread['attachments'] = []

                # Add new attachments that are not already in the list
                existing_file_ids = [att['file_id'] for att in thread['attachments']]
                for new_attachment in attachments:
                    if new_attachment.file_id not in existing_file_ids:
                        thread['attachments'].append(new_attachment.to_dict())
                break

    def remove_attachment_from_thread(self, thread_id: str, file_id_to_remove: str) -> None:
        """
        Remove a specific attachment from a thread by its file_id.
        
        :param thread_id: The ID of the thread.
        :type thread_id: str
        :param file_id_to_remove: The file_id of the attachment to remove.
        :type file_id_to_remove: str
        """
        for thread in self._threads:
            if thread['thread_id'] == thread_id:
                thread['attachments'] = [att for att in thread.get('attachments', []) if att['file_id'] != file_id_to_remove]
                break

    def remove_attachments_from_thread(self, thread_id: str, file_ids_to_remove: List[str]) -> None:
        """
        Remove specific attachments from a thread by their file_id.
        
        :param thread_id: The ID of the thread.
        :type thread_id: str
        :param file_ids_to_remove: A list of file_ids to remove from the thread.
        :type file_ids_to_remove: list
        """
        for thread in self._threads:
            if thread['thread_id'] == thread_id:
                thread['attachments'] = [att for att in thread.get('attachments', []) if att['file_id'] not in file_ids_to_remove]
                break

    def get_attachments_of_thread(self, thread_id: str) -> List[Attachment]:
        """
        Get the list of attachments associated with a specific thread.
        
        :param thread_id: The ID of the thread.
        :type thread_id: str

        :return: A list of Attachment instances.
        :rtype: list
        """
        for thread in self._threads:
            if thread['thread_id'] == thread_id:
                return [Attachment.from_dict(att) for att in thread.get('attachments', [])]
        return []

    def set_attachments_of_thread(self, thread_id: str, attachments: List[Attachment]) -> None:
        """
        Set the attachments for a specific thread.
        
        :param thread_id: The ID of the thread.
        :type thread_id: str
        :param attachments: A list of Attachment instances to set for the thread.
        :type attachments: list
        """
        for thread in self._threads:
            if thread['thread_id'] == thread_id:
                thread['attachments'] = [att.to_dict() for att in attachments]
                break

    def update_attachment_in_thread(self, thread_id: str, attachment: Attachment) -> None:
        """
        Update an attachment in a specific thread.
        
        :param thread_id: The ID of the thread.
        :type thread_id: str
        :param attachment: The Attachment instance to update.
        :type attachment: Attachment
        """
        for thread in self._threads:
            if thread['thread_id'] == thread_id:
                for i, att in enumerate(thread.get('attachments', [])):
                    if att['file_id'] == attachment.file_id:
                        thread['attachments'][i] = attachment.to_dict()
                        break
                break

    def _get_config_data(self):
        # Initialize a structure for threads categorized by ai_client_type
        if self._ai_client_type not in self._config_data:
            self._config_data[self._ai_client_type] = {"threads": []}

        # Add threads to the appropriate ai_client_type category
        self._config_data[self._ai_client_type]["threads"] = self._threads

        return self._config_data

    def save_to_json(self) -> None:
        """
        Save the configuration for the specific ai_client_type to a JSON file.
        """
        if self._config_file is None:
            return

        # Ensure the directory exists
        os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
        
        # Read the existing configuration
        logger.info(f"Saving conversation thread configuration to {self._config_file}")
        try:
            with open(self._config_file, 'r') as f:
                existing_config = json.load(f)
        except FileNotFoundError:
            logger.info(f"Existing configuration file not found. Creating new file at {self._config_file}")
            existing_config = {}

        # Update the configuration data for the specific ai_client_type
        config_data = self._get_config_data()
        existing_config[self._ai_client_type] = config_data[self._ai_client_type]

        # Write the updated configuration back to the file
        with open(self._config_file, 'w') as f:
            json.dump(existing_config, f, indent=4)