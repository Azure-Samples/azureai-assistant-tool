# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.function_config import FunctionConfig
from azure.ai.assistant.management.exceptions import EngineError
from azure.ai.assistant.management.logger_module import logger

import json
import os, ast, re, sys
from pathlib import Path
from typing import Optional

# Template for a function spec
function_spec_template = {
    "type": "function",
    "function": {
        "name": "name of function",
        "module": "functions.user_functions",
        "description": "description of function",
        "parameters": {
            "type": "object",
            "properties": {
                "argument_1 of function": {
                    "type": "string",
                    "description": "The description of the argument 1"
                },
                # ... other arguments ...
            },
            "required": ["argument_1 of function", "..."]
        }
    }
}


class FunctionConfigManager:
    _instance = None
    """
    A class to manage function configurations.

    :param config_directory: The directory containing the function specifications.
    :type config_directory: str
    """
    def __init__(
            self, 
            config_folder : Optional[str] = None
    ) -> None:
        if config_folder is None:
            self._config_folder = self._default_config_path()
        else:
            self._config_folder = config_folder
        self.load_function_configs()
        self.load_function_error_specs()
        self.load_openapi_functions()

    @staticmethod
    def _default_config_path() -> str:
        home = os.path.expanduser("~")
        return os.path.join(home, ".config", 'azure-ai-assistant')

    @classmethod
    def get_instance(
        cls,
        config_folder : Optional[str] = None
    ) -> 'FunctionConfigManager':
        """
        Get the singleton instance of FunctionConfigManager.

        :param config_folder: The directory containing the function specifications.
        :type config_folder: str

        :return: The singleton instance of FunctionConfigManager.
        :rtype: FunctionConfigManager
        """
        if cls._instance is None:
            cls._instance = cls(config_folder)
        return cls._instance

    def load_function_configs(self) -> None:
        """
        Loads function specifications from the config directory.
        """
        logger.info(f"Loading function specifications from {self._config_folder}")

        # Clear the existing configs
        self._function_configs = {}

        # Scan the directory for JSON files
        for file in Path(self._config_folder).glob("*_function_specs.json"):
            self._load_function_spec(file)

    def _load_function_spec(self, file_path):
        logger.info(f"Loading function spec from {file_path}")
        try:
            with open(file_path, 'r') as file:
                config_list = json.load(file)
                for func_spec in config_list:
                    spec_type = func_spec.get("type", "")
                    if spec_type == "azure_function":
                        function_type = "azure"   
                    else:
                        # System or User
                        function_type = self._parse_function_type(file_path.name)
                    
                    if function_type not in self._function_configs:
                        self._function_configs[function_type] = []

                    self._function_configs[function_type].append(FunctionConfig(func_spec))
        except Exception as e:
            logger.error(f"Error loading specs from {file_path}: {e}")

    def load_function_error_specs(self) -> None:
        """
        Loads function error specifications from the config directory.
        """
        logger.info(f"Loading function error specifications from {self._config_folder}")

        # Clear the existing configs
        self._function_error_specs = {}

        # Load the error specs from function_error_specs.json
        file_path = Path(self._config_folder) / "function_error_specs.json"
        logger.info(f"Loading function error specs from {file_path}")
        try:
            with open(file_path, 'r') as file:
                self._function_error_specs = json.load(file)
        except FileNotFoundError:
            logger.error(f"The '{file_path}' file was not found.")

    def get_function_error_specs(self) -> dict:
        """
        Returns a dictionary of function error specifications.

        :return: A dictionary of function error specifications.
        :rtype: dict
        """
        return self._function_error_specs

    def get_error_message(self, error_key) -> str:
        """
        Returns the error message for the given error key.

        :param error_key: The error key.
        :type error_key: str

        :return: The error message.
        :rtype: str
        """
        return self._function_error_specs.get(error_key, "Unknown error")

    def get_error_keys(self) -> str:
        """
        Returns a list of all error keys.

        :return: A list of all error keys.
        :rtype: str
        """
        return str(list(self._function_error_specs.keys()))

    def save_function_error_specs(self, function_error_specs : dict) -> bool:
        """
        Saves function error specifications to the config directory.

        :param function_error_specs: The function error specifications to save.
        :type function_error_specs: dict

        :return: True if the function error specifications were saved, False otherwise.
        :rtype: bool
        """
        try:
            # Define path for error specs
            file_path = Path(self._config_folder) / "function_error_specs.json"

            # Write the error specs to the file
            with open(file_path, 'w') as file:
                json.dump(function_error_specs, file, indent=4)

            self.load_function_error_specs()
            return True

        except Exception as e:
            error_message = f"A runtime error occurred: {e} in save_function_error_specs"
            logger.error(error_message)
            raise EngineError(error_message)

    def _parse_function_type(self, file_path_name):
        function_type = 'system' if 'system_function_specs' in file_path_name else 'user'
        return function_type

    def get_function_configs(self) -> dict:
        """
        Returns a dictionary of function configurations.

        :return: A dictionary of function configurations.
        :rtype: dict
        """
        return self._function_configs

    def get_all_functions_data(self) -> list:
        """
        Returns a list of tuples of function type, spec, and code.

        :return: A list of tuples of function type, spec, and code.
        :rtype: list
        """
        all_functions_data = []

        for function_type, function_configs in self._function_configs.items():
            for function_config in function_configs:
                # Get the full specification of the function
                function_spec = function_config.get_full_spec()

                # Retrieve the function code
                if function_type == 'system':
                    function_code = None
                else:
                    function_code = self.get_user_function_code(function_config.name)

                # Append the tuple of function type, spec, and code
                all_functions_data.append((function_type, function_spec, function_code))

        return all_functions_data

    def get_user_function_code(self, function_name) -> str:
        """
        Returns the function code for a user function.

        :param function_name: The name of the function.
        :type function_name: str

        :return: The function code.
        :rtype: str
        """
        # Assuming all function implementations are in a single file 'user_functions.py'.
        user_functions_path = self.get_user_functions_path()
        code = ""
        if os.path.exists(user_functions_path):
            with open(user_functions_path, 'r') as file:
                lines = file.readlines()

            recording = False
            for line in lines:
                if line.startswith(f"# User function: {function_name}"):
                    recording = True
                    # Skip the function tag
                    continue
                elif line.startswith("# User function:") and recording:
                    break
                if recording:
                    code += line

        return code

    def get_user_functions_path(self) -> str:
        """
        Returns the path to the user functions Python file.

        :return: The path to the user functions Python file.
        :rtype: str
        """
        # Determine a writable runtime directory for user_functions.py
        if getattr(sys, 'frozen', False):
            # Running in a PyInstaller bundle
            base_path = os.path.join(os.path.expanduser("~"), 'AssistantStudioData')
            functions_dir = os.path.join(base_path, 'functions')
            user_functions_path = os.path.join(functions_dir, 'user_functions.py')

            # Add the parent directory of 'functions' to sys.path if not already there
            logger.info(f"functions_dir: {functions_dir}")
            logger.info(f"sys.path: {sys.path}")
            if functions_dir not in sys.path:
                logger.info(f"Adding {functions_dir} to sys.path")
                sys.path.insert(0, functions_dir)
        else:
            # Running in a normal Python environment
            user_functions_path = os.path.join('functions', 'user_functions.py')

        return user_functions_path

    def save_function_spec(self, new_spec: str) -> tuple:
        """
        Saves a new system or user function spec. If a function with the same name 
        and the same spec type already exists in the relevant file, it is updated; 
        otherwise, it is added as a new entry.

        1) Determine whether the spec is a 'system' function or a 'user' function.
        - "system" if type == "function" AND module starts with 
            "azure.ai.assistant.functions."
        - "user" if type == "function" or "azure_function" (and does not match
            the above criterion for system).
        2) Depending on whether it's system or user, we read either 
        system_function_specs.json or user_function_specs.json.
        3) We only overwrite an entry if the function name *and* the type matches.
        ("function" only overwrites "function", "azure_function" only overwrites 
        "azure_function".)
        4) Return (True, new_function_name).

        :param new_spec: The new function spec to save (JSON string).
        :type new_spec: str

        :return: A tuple of (success, new_function_name).
        :rtype: tuple
        """
        try:
            new_spec_dict = json.loads(new_spec)

            # Determine if it's system vs. user spec
            spec_type = new_spec_dict.get("type", "")
            if spec_type == "function" and "function" in new_spec_dict:
                module_name = new_spec_dict["function"].get("module", "")
                if module_name.startswith("azure.ai.assistant.functions."):
                    # system function
                    file_path = Path(self._config_folder) / "system_function_specs.json"
                else:
                    # user function
                    file_path = Path(self._config_folder) / "user_function_specs.json"
            elif spec_type == "azure_function" and "azure_function" in new_spec_dict:
                # user azure function
                file_path = Path(self._config_folder) / "user_function_specs.json"
            else:
                # If we reach here, we can't classify well, or the user has an unexpected spec
                error_message = f"Spec type '{spec_type}' not recognized or missing required blocks."
                logger.error(error_message)
                raise EngineError(error_message)

            # Extract the function name from the new spec
            new_function_name = self._get_function_name_from_spec(new_spec_dict)
            if not new_function_name:
                raise EngineError("The new spec does not contain a valid function name.")

            logger.info(
                f"save_function_spec: Determined target file as {file_path}, "
                f"type='{spec_type}', name='{new_function_name}'"
            )

            # Check if the function name already exists
            if file_path.exists():
                with open(file_path, 'r') as file:
                    specs = json.load(file)
            else:
                specs = []

            # Attempt to find an entry with the same function name AND the same 'type'
            updated = False
            for i, spec in enumerate(specs):
                existing_type = spec.get("type", "")
                existing_name = None

                if "function" in spec:
                    existing_name = spec["function"].get("name")
                elif "azure_function" in spec and "function" in spec["azure_function"]:
                    existing_name = spec["azure_function"]["function"].get("name")

                # Only update if both name and type match
                if (existing_name == new_function_name) and (existing_type == spec_type):
                    specs[i] = new_spec_dict
                    updated = True
                    logger.info(f"Updated existing '{spec_type}' spec: '{new_function_name}' in {file_path}")
                    break

            if not updated:
                logger.info(f"Adding new '{spec_type}' function spec: '{new_function_name}' to {file_path}")
                specs.append(new_spec_dict)

            # Write updated list of specs back to disk
            self._write_specs_to_file(specs, file_path)
            return True, new_function_name

        except json.JSONDecodeError:
            error_message = "Invalid JSON in the function spec."
            logger.error(error_message)
            raise EngineError(error_message)
        except Exception as e:
            error_message = f"A runtime error occurred: {e} in save_function_spec"
            logger.error(error_message)
            raise EngineError(error_message)

        except json.JSONDecodeError:
            error_message = "Invalid JSON in the function spec."
            logger.error(error_message)
            raise EngineError(error_message)
        except Exception as e:
            error_message = f"A runtime error occurred: {e} in save_function_spec"
            logger.error(error_message)
            raise EngineError(error_message)

    def delete_user_function(self, function_name : str) -> bool:
        """
        Deletes a user function.

        :param function_name: The name of the function to delete.
        :type function_name: str

        :return: True if the function was deleted, False otherwise.
        :rtype: bool
        """
        try:
            # Define path for user specs
            user_file_path = Path(self._config_folder) / "user_function_specs.json"

            # Delete the function from user specs
            if not self._delete_function_spec(function_name, user_file_path):
                return False

            # Delete the function implementation from the Python file
            if not self._delete_function_impl(function_name):
                return False

            return True

        except Exception as e:
            error_message = f"A runtime error occurred: {e} in delete_user_function"
            logger.error(error_message)
            raise EngineError(error_message)

    def _delete_function_impl(self, function_name):
        user_functions_path = self.get_user_functions_path()
        if not os.path.exists(user_functions_path):
            return False

        try:
            with open(user_functions_path, 'r') as file:
                lines = file.readlines()

            start_line, end_line = self._find_function_start_end_lines(lines, function_name)
            if start_line is None or end_line is None:
                return False  # Function not found in the file

            # Remove the function code from the file
            del lines[start_line:end_line]

            with open(user_functions_path, 'w') as file:
                file.writelines(lines)

            return True

        except Exception as e:
            error_message = f"Error deleting function implementation: {e}"
            logger.error(error_message)
            raise EngineError(error_message)

    def _delete_function_spec(self, function_name, file_path):
        try:
            if file_path.exists():
                with open(file_path, 'r') as file:
                    specs = json.load(file)

                for i, spec in enumerate(specs):
                    # Check 'function' or nested 'azure_function' -> 'function'
                    name_in_spec = None
                    if "function" in spec:
                        name_in_spec = spec["function"].get("name")
                    elif "azure_function" in spec and "function" in spec["azure_function"]:
                        name_in_spec = spec["azure_function"]["function"].get("name")

                    if name_in_spec == function_name:
                        specs.pop(i)  # Delete the spec
                        self._write_specs_to_file(specs, file_path)
                        return True

            return False
        except json.JSONDecodeError as e:
            error_message = f"JSON decode error: {e} in _delete_function_spec"
            logger.error(error_message)
            raise EngineError(error_message)
        except Exception as e:
            error_message = f"A runtime error occurred: {e} in _delete_function_spec"
            logger.error(error_message)
            raise EngineError(error_message)

    def _write_specs_to_file(self, specs, file_path):
        try:
            with open(file_path, 'w') as file:
                json.dump(specs, file, indent=4)
            logger.info(f"Successfully updated function spec in {file_path}")
        except Exception as e:
            error_message = f"Error writing to {file_path}: {e}"
            logger.error(error_message)
            raise EngineError(error_message)

    def save_function_impl(
            self, 
            code : str,
            existing_function_name : str,
            new_function_name : str
    ) -> str:
        """
        Saves a new function implementation or updates an existing one.

        :param code: The new function code to save.
        :type code: str
        :param existing_function_name: The name of the existing function to update.
        :type existing_function_name: str
        :param new_function_name: The new name of the function.
        :type new_function_name: str

        :return: The path to the file where the function was saved.
        :rtype: str
        """
        file_path = self.get_user_functions_path()
        logger.info(f"Saving function to {file_path}")
        header_comment = "# This file is auto-generated. Do not edit directly.\n"

        try:
            # Check if the code is syntactically correct
            ast.parse(code)

            # Ensure the directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Read the existing file
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    lines = file.readlines()
            else:
                lines = [header_comment]

            # Use the helper method to find the start and end lines
            start_line, end_line = self._find_function_start_end_lines(lines, existing_function_name)

            # Prepare the new function code
            new_function_code = [line + '\n' for line in code.split('\n') if line]
            # add a blank line after the function
            new_function_code.append('\n')

            if start_line is not None and end_line is not None:
                # Replace existing function
                lines[start_line] = f"# User function: {new_function_name}\n"  # Update the function tag if name changed
                lines[start_line + 1:end_line] = new_function_code
            else:
                # Add a new function with its tag
                new_function_with_tag = [f"# User function: {new_function_name}\n"] + new_function_code
                if lines and not lines[-1].endswith('\n'):
                    lines.append('\n')
                # Add a blank line before the function
                if lines and not lines[-1] == '\n':
                    lines.append('\n')
                lines.extend(new_function_with_tag)

            # Write back to the file
            with open(file_path, 'w') as file:
                file.writelines(lines)

            # Consolidate imports
            self._clean_format_file(file_path)
            return file_path

        except SyntaxError as syn_err:
            error_message = f"Syntax error in the provided function code: {syn_err} in save_function_impl"
            logger.error(error_message)
            raise EngineError(error_message)

        except Exception as e:
            error_message = f"A runtime error occurred: {e} in save_function_impl"
            logger.error(error_message)
            raise EngineError(error_message)

    def _find_function_start_end_lines(self, lines, function_name):
        start_line = None
        end_line = None
        tag = f"# User function: {function_name}"
        for i, line in enumerate(lines):
            if line.strip() == tag:
                start_line = i
                for j in range(i + 1, len(lines)):
                    if lines[j].strip().startswith("# User function:") and j != i:
                        end_line = j
                        break
                if end_line is None:
                    end_line = len(lines)
                break
        return start_line, end_line

    def _clean_format_file(self, file_path):
        try:
            with open(file_path, 'r') as file:
                lines = file.readlines()

            # Separate imports from other lines
            import_lines = [line for line in lines if line.strip().startswith('import') or line.strip().startswith('from')]
            other_lines = [line for line in lines if not (line.strip().startswith('import') or line.strip().startswith('from'))]

            # Deduplicate imports
            deduplicated_imports = list(set(import_lines))
            deduplicated_imports.sort()  # Optional: Sort the imports

            # Remove extra empty lines between methods
            cleaned_other_lines = self._remove_extra_empty_lines(other_lines)

            # Reassemble the file with imports at the top
            consolidated_lines = deduplicated_imports + ['\n'] + cleaned_other_lines

            # Write back to the file, ensuring no additional newlines are added
            with open(file_path, 'w') as file:
                for line in consolidated_lines:
                    file.write(line.rstrip('\n') + '\n')

        except Exception as e:
            error_message = f"Error writing to {file_path}: {e} in _clean_format_file"
            logger.error(error_message)
            raise EngineError(error_message)

    def _remove_extra_empty_lines(self, lines):
        cleaned_lines = []
        previous_line_empty = False
        for line in lines:
            is_empty = not line.strip()
            if is_empty and previous_line_empty:
                continue  # Skip extra empty lines
            cleaned_lines.append(line)
            previous_line_empty = is_empty
        return cleaned_lines

    def validate_function(self, spec : str, code : str = None) -> tuple:
        """
        Validates the given function spec against the template.
        Validates the given function name in the spec against the function name in the code.

        :param spec: The function spec to validate.
        :type spec: str
        :param code: The function code to validate the spec against.
        :type code: str

        :return: A tuple of (valid, message).
        :rtype: tuple
        """
        try:
            spec_dict = json.loads(spec)

            valid, msg = self._validate_dict(function_spec_template, spec_dict)
            if not valid:
                return False, msg

            # If code is not provided, only validate the spec
            if code is None:
                return True, "Valid spec"

            spec_function_name = self._get_function_name_from_spec(spec_dict)
            if not self._find_function_in_code(code, spec_function_name):
                return False, f"Function '{spec_function_name}' not found in generated code"

            return True, "Valid spec"

        except json.JSONDecodeError as e:
            error_message = f"Invalid JSON in the function spec: {e} in validate_function"
            logger.error(error_message)
            raise EngineError(error_message)

    def _validate_dict(self, template, spec):
        if not isinstance(spec, dict):
            return False, "Spec is not a dictionary"

        if 'type' not in spec:
            return False, "Missing main block: 'type'"

        required_function_keys = ['name', 'module', 'description', 'parameters']

        if 'function' in spec:
            function_block = spec['function']
            if not isinstance(function_block, dict):
                return False, "The 'function' block must be a dictionary"
            for key in required_function_keys:
                if key not in function_block:
                    return False, f"Missing key in 'function' block: {key}"
            return True, "Valid spec"

        if 'azure_function' in spec:
            azure_function_block = spec['azure_function']
            if not isinstance(azure_function_block, dict):
                return False, "The 'azure_function' block must be a dictionary"

            if 'function' not in azure_function_block:
                return False, "Missing 'function' block in 'azure_function'"

            function_block = azure_function_block['function']
            if not isinstance(function_block, dict):
                return False, "The 'azure_function' -> 'function' block must be a dictionary"
            for key in required_function_keys:
                if key not in function_block:
                    return False, f"Missing key in nested 'function' block: {key}"

            return True, "Valid spec"

        return False, "Missing main block: 'function' or 'azure_function'"

    def _get_function_name_from_spec(self, spec_dict):
        if "function" in spec_dict and isinstance(spec_dict["function"], dict):
            return spec_dict["function"].get("name", "")

        if ("azure_function" in spec_dict 
            and isinstance(spec_dict["azure_function"], dict) 
            and "function" in spec_dict["azure_function"]
            and isinstance(spec_dict["azure_function"]["function"], dict)):
            return spec_dict["azure_function"]["function"].get("name", "")

        return ""

    def _find_function_in_code(self, code, function_name):
        pattern = fr'def {re.escape(function_name)}\('
        match = re.search(pattern, code)
        return bool(match)

    def load_openapi_functions(self) -> None:
        """
        Loads OpenAPI definitions from "openapi_functions.json" into memory.
        Stores them in self._openapi_functions as a list of dicts, each like:
            {
               "type": "openapi",
               "openapi": {
                   "name": "...",
                   "description": "...",
                   "spec": {...}
               },
               "auth": {
                   "type": "anonymous|connection|managed_identity"
               }
            }
        """
        self._openapi_functions = []
        openapi_file_path = Path(self._config_folder) / "openapi_functions.json"
        if openapi_file_path.exists():
            try:
                with open(openapi_file_path, 'r') as f:
                    self._openapi_functions = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in '{openapi_file_path}'.")
            except Exception as e:
                logger.error(f"Error loading OpenAPI definitions: {e}")
        else:
            logger.info(f"No 'openapi_functions.json' found at {openapi_file_path}. Starting with empty list.")

    def get_all_openapi_functions(self) -> list:
        """
        Returns the list of all loaded OpenAPI definitions as raw dicts.
        """
        return self._openapi_functions

    def save_openapi_function(self, openapi_dict: dict) -> None:
        """
        Creates or updates an OpenAPI definition in "openapi_functions.json".
        If an entry with the same openapi['name'] exists, this updates it;
        otherwise, it appends a new entry.
        """
        if "openapi" not in openapi_dict:
            raise EngineError("Invalid OpenAPI definition: Missing 'openapi' block.")
        name_to_save = openapi_dict["openapi"].get("name")
        if not name_to_save:
            raise EngineError("Invalid OpenAPI definition: Missing 'openapi.name'.")

        updated = False
        for i, entry in enumerate(self._openapi_functions):
            existing_name = entry.get("openapi", {}).get("name")
            if existing_name == name_to_save:
                self._openapi_functions[i] = openapi_dict
                updated = True
                break
        if not updated:
            self._openapi_functions.append(openapi_dict)

        self._write_openapi_functions_to_file()

    def delete_openapi_function(self, name: str) -> bool:
        """
        Removes an OpenAPI function by name from self._openapi_functions.
        Returns True if found and removed, False if no matching entry exists.
        """
        found = False
        for i, entry in enumerate(self._openapi_functions):
            openapi_name = entry.get("openapi", {}).get("name")
            if openapi_name == name:
                del self._openapi_functions[i]
                found = True
                break

        if found:
            self._write_openapi_functions_to_file()

        return found

    def _write_openapi_functions_to_file(self) -> None:
        openapi_file_path = Path(self._config_folder) / "openapi_functions.json"
        try:
            with open(openapi_file_path, 'w') as f:
                json.dump(self._openapi_functions, f, indent=4)
            logger.info(f"Saved OpenAPI definitions to {openapi_file_path}")
        except Exception as e:
            logger.error(f"Could not write to {openapi_file_path}: {e}")
            raise EngineError(f"Could not save OpenAPI definitions: {e}")

    @staticmethod
    def get_function_spec_template() -> str:
        """
        Returns the template for a function spec.

        :return: The template for a function spec.
        :rtype: str
        """
        # Return the template as a formatted JSON string
        return json.dumps(function_spec_template, indent=4)
