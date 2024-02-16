# Project Name

The Azure AI Assistant Tool is experimental Python application and middleware designed to simplify the development, experimentation, testing, and debugging of OpenAI assistants. It's a flexible solution/playground for anyone looking to quickly experiment and build AI assistants.

# Project Targets

Enhance Developer Productivity: Streamline the assistant development process by offering built-in middleware libraries and tools that simplify the use of Azure OpenAI assistants, making it easier for developers to integrate AI capabilities into their applications.

Foster Innovation: Enable rapid experimentation and innovation by providing a robust set of features such as built-in system functions, dynamic generation of user functions specification and implementation, assistant task creation and scheduling, which allow developers to explore new use cases and optimize AI workflows efficiently.

Improve Reliability and Scalability: Provide a reliable and scalable framework for building and testing AI applications, ensuring that developers can easily scale their solutions to meet user demand without compromising on performance.

# Project Status: Alpha

The Azure AI Assistant Tool is currently in Alpha status. This early stage of development means the project is actively evolving, with significant updates and improvements expected. Users should anticipate changes as we work towards refining features, enhancing functionality, and expanding capabilities. We welcome feedback and contributions during this phase to help shape the future of the tool.

## Features

- Easy Configuration: Set up assistant instructions, models, files, and tools.
- Tool Integration: Incorporate knowledge retrieval, code interpreters, and built-in system and dynamic user functions to enhance assistant skills and capabilities.
- Dynamic User Functions: Quickly create and apply user-defined functions to assistants.
- Task Management: Efficiently manage and schedule tasks, including batch and multi-step operations, for parallel execution.

## Installation & Setup

### Prerequisites
Before installing Application Name, you need to have Python installed on your system (Python 3.8 or newer is recommended). 
You can download Python from [the official website](https://www.python.org/downloads/).

#### PySide6 Dependency
This application depends on the PySide6 libraries for its graphical user interface. PySide6 is dynamically linked, meaning you need to have PySide6 installed on your system to run Application Name.

### Install azure.ai.assistant Python library
- Go under `sdk/azure-ai-assistant` folder
- Make sure wheel is installed: `pip install wheel` (or pip3 e.g. in Mac)
- Build the wheel using following command: `python setup.py sdist bdist_wheel`
- Go to generated `dist` folder
- Install the generated wheel using following command: `pip install --force-reinstall --no-deps azure_ai_assistant-0.2.3a1-py3-none-any.whl`

### Install dependencies
- pip install PySide6 (or use pip3 e.g. in Mac)
- pip install openai
- pip install python-Levenshtein
- pip install fuzzywuzzy
- pip install Pillow
- pip install azure-cognitiveservices-speech
  - This is required for microphone functionality
- pip install --force-reinstall --no-deps azure_ai_assistant-0.2.3a1-py3-none-any.whl
  - azure_ai_assistant-0.2.3a1-py3-none-any.whl can be found under the release tags in repo currently

### Setup Environment Variables
1. Set the OpenAI key and endpoint and version (optional)
  - Windows: 
    - setx OPENAI_API_KEY "Your OpenAI Key"
    - setx AZURE_OPENAI_API_KEY "Your Azure OpenAI Key"
    - setx AZURE_OPENAI_ENDPOINT "Your OpenAI Endpoint"
    - setx AZURE_OPENAI_API_VERSION "Azure OpenAI version"
  - Linux/Mac:
    - export OPENAI_API_KEY="Your OpenAI Key"
    - export AZURE_OPENAI_API_KEY="Your Azure OpenAI Key"
    - export AZURE_OPENAI_ENDPOINT="Your OpenAI Endpoint"
    - export AZURE_OPENAI_API_VERSION="Azure OpenAI version"

2. Set Cognitive Services Speech key (if you want to use speech input)
  - Windows: 
    - setx SPEECH_KEY "Your Speech Key"
    - setx SPEECH_REGION "Your Speech Region"
  - Linux/Mac: 
    - export SPEECH_KEY="Your Speech Key"
    - export SPEECH_REGION="Your Speech Region"

## Launch the application

- Run the following command in root of this repository
  - `python main.py` (or python3 depends on your environment)

## License
Application Name is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

### Notice Regarding PySide6
The Azure AI Assistant Tool uses PySide6, which is licensed under the GNU Lesser General Public License (LGPL). 
By using PySide6, you are able to modify and redistribute the library under the same license. 
For more information on PySide6's license, please visit [Qt Licensing](https://www.qt.io/licensing/).
