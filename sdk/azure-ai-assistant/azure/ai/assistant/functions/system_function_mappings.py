# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

# Import the file functions
from azure.ai.assistant.functions.file_functions import (
    fetch_current_datetime,
    fetch_detailed_files_info_in_directory,
    list_files_from_directory,
    copy_multiple_files_by_extension,
    copy_specific_file_to_directory,
    create_file_with_specified_content,
    retrieve_file_content_from_directory,
    get_content_from_matching_files,
    find_all_folders_by_name_from_current_directory,
    retrieve_current_directory_structure_subfolders,
    find_files_by_name_in_directory,
    find_files_by_extension_in_directory,
)

from azure.ai.assistant.functions.llm_functions import (
    get_openai_chat_completion,
    get_azure_openai_chat_completion,
)

# Statically defined system functions for fast reference
system_functions = {
    "fetch_current_datetime": fetch_current_datetime,
    "fetch_detailed_files_info_in_directory": fetch_detailed_files_info_in_directory,
    "list_files_from_directory": list_files_from_directory,
    "copy_multiple_files_by_extension": copy_multiple_files_by_extension,
    "copy_specific_file_to_directory": copy_specific_file_to_directory,
    "create_file_with_specified_content": create_file_with_specified_content,
    "retrieve_file_content_from_directory": retrieve_file_content_from_directory,
    "get_content_from_matching_files": get_content_from_matching_files,
    "find_all_folders_by_name_from_current_directory": find_all_folders_by_name_from_current_directory,
    "retrieve_current_directory_structure_subfolders": retrieve_current_directory_structure_subfolders,
    "find_files_by_name_in_directory": find_files_by_name_in_directory,
    "find_files_by_extension_in_directory": find_files_by_extension_in_directory,
    "get_openai_chat_completion": get_openai_chat_completion,
    "get_azure_openai_chat_completion": get_azure_openai_chat_completion,
}