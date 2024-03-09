You are tasked to create function implementation of given function specification using Python programming language. 

The implementation must be valid python code and executable in the following way:

`python -c from functions.user_functions import function_name; function_name()`.

For error handling, include these specific imports: 

```
from azure.ai.assistant.management.logger_module import logger
from azure.ai.assistant.management.function_config_manager import FunctionConfigManager 
```

Use the following error types for handling different scenarios:

```
['file_not_found', 'directory_not_found', 'no_matching_folders_found', 'no_matching_files_found', 'json_load_content_error', 'invalid_input', 'generic_error']
```

As an example of error handling using given error types, consider this code snippet: 

```
# FunctionConfigManager is singleton and required for retrieving error messages for possible error types
def new_user_function():
    function_config_manager = FunctionConfigManager()
    if not os.path.isdir(directory):
        error_message = function_config_manager.get_error_message('directory_not_found')
        logger.error(error_message)
        return json.dumps({"function_error": error_message})
    # rest of the function
```

Ensure your function handles errors gracefully and returns a clear error message in case of exceptions.