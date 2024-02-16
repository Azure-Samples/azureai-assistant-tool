# Azure AI Assistant Client Library

## Build
- `python setup.py sdist bdist_wheel`

## Installation
- Install azure-ai-assistant package with all dependencies
  - `pip install /path/to/azure_ai_assistant-x.x.x-py3-none-any.whl`
- For development, install without dependencies
  - `pip install --force-reinstall --no-deps /path/to/azure_ai_assistant-x.x.x-py3-none-any.whl`
- For development, install in edit mode
  - `pip install -e . `
    - Need to be verified

## Management Module
- This contains middleware components for assistants configuration and execution management.

## Functions Module
- Currently following functions have been implemented with specifications (in config folder)
- File Functions
  - `fetch_current_datetime`: Get the current time as a JSON string.
  - `fetch_detailed_files_info_in_directory`: Get information about files inside a given folder and return as a JSON string.
  - `list_files_from_directory`: Returns a list of files of a certain type from a specified directory.
  - `copy_multiple_files_by_extension`: Copies files of a certain type from an input directory to an output directory.
  - `copy_specific_file_to_directory`: Copies a single file from an input directory to an output directory.
  - `create_file_with_specified_content`: Creates a new file with the provided content in the specified directory, with an optional file extension.
  - `retrieve_file_content_from_directory`: Retrieves the content of a specified file in a given directory.
  - `get_content_from_matching_files`: Gets the content of all files matching with a specific file extension in a given directory.
  - `retrieve_current_directory_structure`: Retrieves the structure of the current directory and its subdirectories.
  - `find_files_by_name_in_directory`: Searches for files matching specific criteria by name in a directory and its sub-directories (case-insensitive).
  - `find_files_by_extension_in_directory`: Searches for files matching specific criteria by file extension in a directory and its sub-directories (case-insensitive).

- GitHub Functions
  - `fetch_new_github_issues`: Fetches new issues from a specified GitHub repository since a given date, returning the issue number and title.

  - `get_github_issue_body_by_number`:Retrieves the content body of a specific issue from a GitHub repository using its issue number.

  - `fetch_closed_github_issues`: Fetches closed issues from a specified GitHub repository, returning their issue number and title.

  - `get_github_issue_body_with_comments`: Retrieves the body of a specific issue from a GitHub repository along with all its comments.

## Dependencies
- openai
- python-Levenshtein
- fuzzywuzzy
- azure-cognitiveservices-speech

## Setup keys
1. Set the OpenAI key
  - Windows: 
    - setx OPENAI_API_KEY "Your OpenAI Key"
  - Linux/Mac:
    - export OPENAI_API_KEY="Your OpenAI Key"

2. Set Cognitive Services Speech key (if you want to use speech input)
  - Windows: 
    - setx SPEECH_KEY "Your Speech Key"
    - setx SPEECH_REGION "Your Speech Region"
  - Linux/Mac: 
    - export SPEECH_KEY="Your Speech Key"
    - export SPEECH_REGION="Your Speech Region"

3. If you use GitHub functions, better to set the PAT (to avoid hitting rate limits)
  - Windows:
    - setx GITHUB_TOKEN "Your GitHub Personal Access Token"