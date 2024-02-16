# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import os
import json
import shutil

from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.management.function_config_manager import FunctionConfigManager
import datetime
from fuzzywuzzy import fuzz


def fetch_current_datetime():
    """
    Get the current time as a JSON string.

    :return: The current time in JSON format.
    :rtype: str
    """
    current_time = datetime.datetime.now()
    time_json = json.dumps({"current_time": current_time.strftime("%Y-%m-%d %H:%M:%S")})
    return time_json


def fetch_detailed_files_info_in_directory(directory):
    """
    Get information about files inside a given folder and all its subfolders, and return as a JSON string.

    :param directory: The path to the folder. Required.
    :type directory: str
    
    :return: A JSON string containing file information.
    :rtype: str
    """
    file_info_list = []
    function_config_manager = FunctionConfigManager()
    try:
        # Check if the input directory is valid and raise an error if it doesn't
        if not os.path.isdir(directory):
            error_message = function_config_manager.get_error_message('directory_not_found')
            logger.error(error_message)
            return json.dumps({"function_error": error_message})

        # Check if the folder exists
        if os.path.exists(directory):
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    file_path = os.path.join(root, filename)

                    if os.path.isfile(file_path):
                        file_info = {
                            "filename": filename,
                            "filepath": file_path,  # Including the file path for clarity
                            "size_bytes": os.path.getsize(file_path),
                            "file_type": os.path.splitext(filename)[-1].lstrip('.'),
                            "last_updated": datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
                        }
                        file_info_list.append(file_info)

        # Convert the list of dictionaries to a JSON string
        return json.dumps(file_info_list)
    except Exception as e:
        # Replace 'logger.error' with your logging method if needed
        logger.error(f"An error occurred when getting files information: {str(e)}")
        return json.dumps({"function_error": "An error occurred when getting files information, please check the input directory is valid by e.g. by using retrieving current directory structure"})


def list_files_from_directory(directory, file_extension):
    """
    Returns a list of files of a certain type from a specified directory or an empty JSON result if the content is not found. The search is non-recursive.

    :param directory: The path to the directory to search for files.
    :type directory: str
    :param file_extension: The type of files to list, e.g. '.txt'.
    :type file_extension: str
    :return: A JSON string containing the list of files and the file extension.
    :rtype: str
    
    """
    function_config_manager = FunctionConfigManager()
    try:
        # Check if the input directory is valid and raise an error if it doesn't
        if not os.path.isdir(directory):
            error_message = function_config_manager.get_error_message('directory_not_found')
            logger.error(error_message)
            return json.dumps({"function_error": error_message})

        file_list = []
        for filename in os.listdir(directory):
            if filename.endswith(file_extension):
                file_list.append(filename)
        return json.dumps({"file_list": file_list, "file_extension": file_extension})
    except Exception as e:
        logger.error(f"An error occurred during file listing: {str(e)}")
        return json.dumps({"function_error": "An error occurred during file listing"})


def copy_multiple_files_by_extension(input_directory, output_directory, file_extension):
    """
    Copies files of a certain type from an input directory to an output directory. Only files with the specified extension are copied.

    :param input_directory: The path to the input directory.
    :type input_directory: str
    :param output_directory: The path to the output directory.
    :type output_directory: str
    :param file_extension: The type of files to copy, e.g. '.txt'.
    :type file_extension: str

    :return: A JSON string confirming the copied files.
    :rtype: str
    """
    try:
        os.makedirs(output_directory, exist_ok=True)
        copied_files = []
        for filename in os.listdir(input_directory):
            if filename.endswith(file_extension):
                shutil.copy(os.path.join(input_directory, filename), 
                            os.path.join(output_directory, filename))
                copied_files.append(filename)
        return json.dumps({"copied_files": copied_files})
    except Exception as e:
        logger.error(f"An error occurred during file copying: {str(e)}")
        return json.dumps({"function_error": "An error occurred during file copying, please find where the file locates and check the input directory and file extension"})


def copy_specific_file_to_directory(input_directory, output_directory, file_name):
    """
    Copies a single file from an input directory to an output directory.

    :param input_directory: The path to the input directory.
    :type input_directory: str
    :param output_directory: The path to the output directory.
    :type output_directory: str
    :param file_name: The name of the file to copy.
    :type file_name: str

    :return: A JSON string confirming the copied file.
    :rtype: str
    """
    function_config_manager = FunctionConfigManager()
    try:
        # Check if the input directory is valid and raise an error if it doesn't
        if not os.path.isdir(input_directory):
            error_message = function_config_manager.get_error_message('directory_not_found')
            logger.error(error_message)
            return json.dumps({"function_error": error_message})
        
        os.makedirs(output_directory, exist_ok=True)
        shutil.copy(os.path.join(input_directory, file_name), 
                    os.path.join(output_directory, file_name))
        return json.dumps({"copied_file": file_name})
    except Exception as e:
        logger.error(f"An error occurred during file copying: {str(e)}")
        return json.dumps({"function_error": "An error occurred during file copying, please find where the file locates and check the input directory and file name"})


def create_file_with_specified_content(file_name, output_directory, content, file_extension=None):
    """
    Creates a new file with the provided content and optional file extension in the specified directory.

    :param file_name: The name of the file to create.
    :type file_name: str
    :param output_directory: The path to the directory where the file will be created.
    :type output_directory: str
    :param content: The content to write to the file.
    :type content: str
    :param file_extension: The file extension to use for the file, e.g. '.txt'. Optional.
    :type file_extension: str

    :return: A JSON string confirming the created file.
    :rtype: str
    """
    try:
        if file_extension:
            if not file_extension.startswith('.'):
                file_extension = '.' + file_extension

            if not file_name.endswith(file_extension):
                file_name += file_extension

        full_path = os.path.join(output_directory, file_name)
        logger.info(f"Creating file: {file_name} with content in directory: {output_directory}")
        os.makedirs(output_directory, exist_ok=True)
        with open(full_path, 'w') as file:
            file.write(content)
        return json.dumps({file_name: content})
    except Exception as e:
        logger.error(f"An error occurred during file creation: {str(e)}")
        return json.dumps({"function_error": "An error occurred during file creation"})


def retrieve_file_content_from_directory(input_directory, filename):
    """
    Retrieves the content of a specified file in a given directory. If the file or directory does not exist, a JSON error message is returned.

    :param input_directory: The directory to search for the file.
    :type input_directory: str
    :param filename: The name of the file to retrieve content from.
    :type filename: str

    :return: A JSON string containing the file name and its content, or an error message.
    :rtype: str
    """
    function_config_manager = FunctionConfigManager()
    try:
        # Check if the input directory is valid and raise an error if it doesn't
        if not os.path.isdir(input_directory):
            error_message = function_config_manager.get_error_message('directory_not_found')
            logger.error(error_message)
            return json.dumps({"function_error": error_message})

        # Construct file path
        file_path = os.path.join(input_directory, filename)

        # Open and read file content
        with open(file_path, 'r') as file:
            content = file.read()

        return json.dumps({filename: content})

    except FileNotFoundError:
        error_message = function_config_manager.get_error_message('file_not_found')
        logger.error(error_message)
        return json.dumps({"function_error": error_message})
    except Exception as e:
        error_message = function_config_manager.get_error_message('generic_error') + f" Error: {str(e)}"
        logger.error({error_message})
        return json.dumps({"function_error": error_message})


def get_content_from_matching_files(input_directory, file_extension):
    """
    Gets the content of all files matching with a specific file extension in a given directory.

    :param input_directory: The directory to search for the files.
    :type input_directory: str
    :param file_extension: The file extension to search for, e.g. '.txt'.
    :type file_extension: str

    :return: A JSON string containing the file names and their content, or an error message.
    :rtype: str
    """

    content_dict = {}  # Initialize an empty dictionary to store file content

    function_config_manager = FunctionConfigManager()
    try:
        # Check if the input directory is valid and raise an error if it doesn't
        if not os.path.isdir(input_directory):
            error_message = function_config_manager.get_error_message('directory_not_found')
            logger.error(error_message)
            return json.dumps({"function_error": error_message})
        
        # Iterate through all files in the specified directory
        for root, _, files in os.walk(input_directory):
            for file_name in files:
                # Check if the file has the specified file extension
                if file_name.endswith(file_extension):
                    file_path = os.path.join(root, file_name)
                    try:
                        # Read the content of the file
                        with open(file_path, "r") as file:
                            file_content = file.read()
                        # Store the content in the dictionary with the file name as the key
                        content_dict[file_name] = file_content
                    except Exception as e:
                        # Handle any errors that may occur during file reading
                        logger.error(f"Error reading file '{file_path}': {str(e)}")

    except Exception as e:
        # Handle any errors that may occur during the search
        error_message = function_config_manager.get_error_message('generic_error') + f" Error: {str(e)}"
        logger.error(error_message)
        return json.dumps({"function_error": error_message})

    # Convert the content dictionary to a JSON string
    json_result = json.dumps(content_dict, indent=4)
    return json_result


def find_all_folders_by_name_from_current_directory(folder_name):
    """
    Searches for folders matching a particular name pattern (contained within the folder's name), within the current directory.

    :param folder_name: The substring to search for within the folder names.
    :type folder_name: str

    :return: A JSON string with the list of matching folder paths or an error message.
    :rtype: str
    """
    function_config_manager = FunctionConfigManager()
    try:
        threshold=80
        # Get the current directory
        current_directory = os.getcwd()
        matching_folders = []

        # Walk through the directory and subdirectories
        for root, dirs, _ in os.walk(current_directory):
            for dir in dirs:
                # Use fuzzy matching to compare folder names
                if fuzz.ratio(folder_name.lower(), dir.lower()) >= threshold:
                    matching_folders.append(os.path.join(root, dir))

        if not matching_folders:
            # Return error as JSON string
            error_message = function_config_manager.get_error_message('no_matching_folders_found')
            return json.dumps({"function_error": error_message})

    except Exception as e:
        # Handle any errors that may occur during the search
        error_message = function_config_manager.get_error_message('no_matching_folders_found')
        return json.dumps({"function_error": error_message})

    # Return matching folders as JSON string
    return json.dumps(matching_folders)


def retrieve_current_directory_structure_subfolders():
    """
    Retrieves the structure of the current directory and its subdirectories. The function lists out all directories and subdirectories as a path to name mapping.

    :return: A JSON string with the directory structure or an error message.
    :rtype: str
    """
    function_config_manager = FunctionConfigManager()
    try:
        directory_structure = {}
        for root, dirs, _ in os.walk("."):
            dirs[:] = [d for d in dirs if not d.startswith('.')]  # Skip hidden directories
            for name in dirs:
                directory_structure[os.path.join(root, name)] = name
        return json.dumps({"directory_structure": directory_structure})
    except Exception as e:
        error_message = function_config_manager.get_error_message('generic_error') + f" Error: {str(e)}"
        logger.error(error_message)
        return json.dumps({"function_error": error_message})


def find_files_by_name_in_directory(directory, file_name_contains):
    """
    Searches for files matching a particular name pattern (contained within the file's name), within a specified directory.
    Uses fuzzy matching to determine if a file name is similar to the search term.

    :param directory: The directory to search in.
    :type directory: str
    :param file_name_contains: The substring to search for within the file names.
    :type file_name_contains: str

    :return: A JSON string with the list of matching file paths or an error message.
    :rtype: str
    """

    similarity_threshold=75

    # Initialize an empty list to store matching file paths
    matching_files = []

    function_config_manager = FunctionConfigManager()
    try:
        # Check if the input directory is valid and raise an error if it doesn't
        if not os.path.isdir(directory):
            error_message = function_config_manager.get_error_message('directory_not_found')
            logger.error(error_message)
            return json.dumps({"function_error": error_message})

        # Iterate through all files and directories in the specified directory
        for root, _, files in os.walk(directory):
            for file_name in files:
                # Use fuzz.ratio for fuzzy string matching
                similarity_score = fuzz.ratio(file_name.lower(), file_name_contains.lower())

                # Check if the similarity score meets the threshold
                if similarity_score >= similarity_threshold:
                    # If the file matches the criteria, add its path to the list
                    matching_files.append(os.path.join(root, file_name))

        # Check if any files were found
        if not matching_files:
            error_message = function_config_manager.get_error_message('no_matching_files_found')
            return json.dumps({"function_error": error_message})

    except Exception as e:
        # Handle any errors that may occur during the search
        error_message = function_config_manager.get_error_message('generic_error') + f" Error: {str(e)}"
        logger.error(error_message)
        return json.dumps({"function_error": error_message})

    # Convert the list of matching file paths to a JSON string
    return json.dumps(matching_files)


def find_files_by_extension_in_directory(directory, file_extension):
    """
    Searches for files with a particular extension within a specified directory.

    :param directory: The directory to search in.
    :type directory: str
    :param file_extension: The file extension to search for, e.g. '.txt'.
    :type file_extension: str

    :return: A JSON string with the list of matching file paths or an error message.
    :rtype: str
    """

    # Initialize an empty list to store matching file paths
    matching_files = []

    function_config_manager = FunctionConfigManager()
    try:
        # Check if the input directory is valid and raise an error if it doesn't
        if not os.path.isdir(directory):
            error_message = function_config_manager.get_error_message('directory_not_found')
            logger.error(error_message)
            return json.dumps({"function_error": error_message})

        # Iterate through all files and directories in the specified directory
        for root, _, files in os.walk(directory):
            for file_name in files:
                # Convert both the file name and search criteria to lowercase for case-insensitive comparison
                file_name_lower = file_name.lower()
                file_extension_lower = file_extension.lower()

                # Check if the file's extension matches the lowercase file_extension, if not, skip this file
                if not file_name_lower.endswith(file_extension_lower):
                    continue

                # If the file matches the criteria, add its path to the list
                matching_files.append(os.path.join(root, file_name))

    except Exception as e:
        error_message = function_config_manager.get_error_message('generic_error') + f" Error: {str(e)}"
        logger.error(error_message)
        return json.dumps({"function_error": error_message})

    # Convert the list of matching file paths to a JSON string
    return json.dumps(matching_files)