<h1 align="center"> 🤖🛠️Azure AI Assistants Tool </h1>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)&ensp;
![Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)
![CrossPlatform](https://img.shields.io/badge/cross-platform-blue)
<br>
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
</div>
<div align="center">
⚡Develop stateful copilot applications powered by Azure OpenAI Assistants at lightening speed⚡
</div>
<br>

  **Azure AI Assistants tool** is an experimental Python application and middleware designed to simplify the development, experimentation, testing, and debugging of Assistants created with **Azure OpenAI Assistants (Preview)** _(see below)_. Use this powerful, easy-to-setup low-code / no code playground tool to quickly experiment and build AI Assistants within your application with Azure OpenAI Assistants API.

> [!IMPORTANT]
> **The Azure AI Assistant Tool is currently in Alpha**. This early stage of development means the project is actively evolving, with significant updates and improvements expected. Users should anticipate changes as we work towards refining features, enhancing functionality, and expanding capabilities. We welcome feedback and contributions during this phase to help shape the future of the tool.


## 🧱 What is Assistants from Azure OpenAI service?

🌟**Assistants**, a new API from Azure OpenAI Service, is a stateful evolution of the Chat Completions API. Assistants makes it easier for developers to create applications with sophisticated copilot-like experiences in their applications and enable developer access to powerful tools like Code Interpreter and Retrieval. Assistants is built on the same capabilities that power OpenAI’s GPT product and offers unparalleled flexibility for creating a wide range of copilot-like applications. Copilots created with Assistants can sift through data, suggest solutions, and automate tasks and use cases span a wide range: AI-powered product recommender, sales analyst app, coding assistant, employee Q&A chatbot, and more.

**Features** include:

💬 Inbuilt thread and memory management <br>
📊 Advanced Data Analysis, create data visualizations and solving complex code and math problems with **Code Interpreter**<br>
🚀 Build your own tools or call external tools and APIs with **Function Calling**<br>
📚 Retrieval Augmented Generation with **Retrieval** tool (coming soon to Azure OpenAI Assistants)<br>
🎤📢 Speech transcription and synthesis using Azure CognitiveServices Speech SDK<br>
📤💾 Exporting the assistant configuration into simple CLI application

**Learn more** about Assistants on Azure OpenAI Service:  

  📹 Watch a [short video](https://www.youtube.com/watch?v=CMXtAe5DhXc&embeds_referring_euri=https%3A%2F%2Ftechcommunity.microsoft.com%2F&source_ve_path=OTY3MTQ&feature=emb_imp_woyt) about Azure OpenAI Assistants  
  📖 Read the [launch announcement](https://techcommunity.microsoft.com/t5/ai-azure-ai-services-blog/azure-openai-service-announces-assistants-api-new-models-for/ba-p/4049940)  
  📌 Get familiar with the [Assistants API Quickstart](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/assistant)  


## 🚀 How does this Tool help?

✔️ **Enhance Developer Productivity:** Streamline the assistant development process with Azure OpenAI Assistans through built-in middleware libraries and tools that making it easy to integrate AI capabilities into your copilot applications

✔️ **Enable rapid prototyping:** Create amazing demos with AOAI Assistants and develop end-to-end assistant solutions with a robust set of features, including built-in system functions, dynamic generation of user functions specification and implementation, assistant task creation and scheduling, and much more. 

✔️**Optimize your copilot development workflow:** Get a reliable and scalable framework to test new Copilot use cases and dynamic AI applications with Assistants API without the need to build out manual tooling and configurations



## 💥 Highlights

- **Easy Configuration**: Set up your assistant with the model, custom instructions, files, and tools
- **Tool Integration**: Incorporate knowledge retrieval, code interpreters, and built-in system and dynamic user functions to enhance assistant skills and capabilities.
- **Dynamic User Functions**: Quickly create and apply user-defined functions to assistants.
- **Task Management**: Efficiently manage and schedule tasks, including batch and multi-step operations, for parallel execution.


## ✨ Quick Start

### Step 1: Complete Azure prerequisities

- Create an Azure Subscription for [free](https://azure.microsoft.com/en-us/free/ai-services/), if you don't have one already
- [Apply for access](https://aka.ms/oai/access) to Azure OpenAI Service in this Azure Subscription. Azure OpenAI Service is currently a limited access service so access is granted through an application process. Most applications are processed within a day of applying.
- Azure OpenAI Assistants is currently available in Sweden Central, East US 2, and Australia East. We are expanding our models and regional availability - see the [models guide](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models) for the latest model and regional availabaility for Assistants.
- Create an Azure OpenAI resource on [Azure Portal](https://ms.portal.azure.com) with one of the Assistants supported models from the models guide page deployed in that region

### Step 2: Install Python 3.8 or newer version
Azure AI Assistant tool requires Python > = 3.8 on your system. You can download Python from [the official website](https://www.python.org/downloads/).

### Step 3: Install PySide6 Dependency
This tool depends on the PySide6 libraries for its graphical user interface. Since PySide6 is dynamically linked, install PySide6 installed on your system.

### Step 4: Build and install azure.ai.assistant Python library

We have included the `azure.ai.assistant` library is included within this tool's repository as part of this tool's alpha status, as it has not yet been released on PyPI. 
Build the wheel using the following instructions, or use the wheel package provided under releases directly.

- Ensure wheel is installed to build the library package. You can install it using the command: `pip install wheel`
- Visit the`sdk/azure-ai-assistant` folder and ensure wheel is installed: `pip install wheel` (or pip3 e.g. in Mac)
- Build the wheel using following command: `python setup.py sdist bdist_wheel`
- Go to generated `dist` folder
- Install the generated wheel using following command: `pip install --force-reinstall --no-deps azure_ai_assistant-0.2.5a1-py3-none-any.whl`

### Step 5: Install dependencies

#### ⌨️ Command Line (CLI)

Create virtual environment (not mandatory but recommended) for Python, see [instructions](https://docs.python.org/3/library/venv.html).

```
# Install specific libraries needed for the Azure AI Assistant tool
pip install PySide6 
pip install openai
pip install python-Levenshtein
pip install fuzzywuzzy
pip install Pillow
pip install azure-cognitiveservices-speech

# Install the latest release of the tool
# Find the latest .whl file under the release tags in this repo and download and save in the main ai-assistant-studio folder
pip install --force-reinstall --no-deps azure_ai_assistant-0.2.5a1-py3-none-any.whl
```

### Step 5: Find and copy your Azure OpenAI Service APIkey, endpoint and model deployment version
To successfully make a call against the Azure OpenAI service, you'll need the following:

**- ENDPOINT:**	This value can be found in the Keys and Endpoint section when examining your resource from the Azure portal. Alternatively, you can find the value in Azure OpenAI Studio > Playground > View code. An example endpoint is: https://docs-test-001.openai.azure.com/.

**- API-KEY:**	This value can be found in the Keys and Endpoint section when examining your resource from the Azure portal. You can use either KEY1 or KEY2.

**- DEPLOYMENT-NAME:**	This value will correspond to the custom name you chose for your deployment when you deployed a model. This value can be found under Resource Management > Model Deployments in the Azure portal or alternatively under Management > Deployments in Azure OpenAI Studio.

Next, go to your resource in the [Azure portal](https://ms.portal.azure.com/#home). The Keys and Endpoint can be found in the Resource Management section (see image below). Copy your endpoint and access key as you'll need both for authenticating your API calls. You can use either KEY1 or KEY2. Always having two keys allows you to securely rotate and regenerate keys without causing a service disruption.
![portal keys and endpoint](https://github.com/Azure-Samples/azureai-assistant-tool/assets/118226126/b4ddbbba-1b91-4525-b05d-b9673dd6e143)

### Step 5: Setup Environment Variables
Create and assign persistent environment variables for your key and endpoint.

#### ⌨️ Command Line (CLI)
1. Set the Azure OpenAI Service key, endpoint. Version is optional and default currently is `2024-02-15-preview` for assistants.

**Windows:**
```
setx AZURE_OPENAI_API_KEY "Your Azure OpenAI Key"
setx AZURE_OPENAI_ENDPOINT "Your OpenAI Endpoint"
setx AZURE_OPENAI_API_VERSION "Azure OpenAI version"
setx OPENAI_API_KEY "Your OpenAI Key"
```

**Linux/Mac**
```
export AZURE_OPENAI_API_KEY="Your Azure OpenAI Key"
export AZURE_OPENAI_ENDPOINT="Your OpenAI Endpoint"
export AZURE_OPENAI_API_VERSION="Azure OpenAI version"
export OPENAI_API_KEY="Your OpenAI Key"
```

2. Set Cognitive Services Speech key (if you want to use speech input & output)

**Windows:**
```
setx SPEECH_KEY "Your Speech Key"
setx SPEECH_REGION "Your Speech Region"
```

**Linux/Mac**
``` 
export SPEECH_KEY="Your Speech Key"
export SPEECH_REGION="Your Speech Region"
```

### Step 5: Launch the application

#### ⌨️ Command Line (CLI)
```
# assume you are in the root of this repository
# Use python or python3 based on your environment

python main.py

```
This will start the Azure AI Assistant Tool and you can interact with it through its user interface which looks something like this:

![Ai-Assistant-Tool-screenshot](https://github.com/Azure-Samples/azureai-assistant-tool/assets/118226126/41a5506e-e8fd-4633-8e00-d533577f8290)

## 📖 License
The Azure AI Assistant Tool is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

### 📣 Notice Regarding PySide6
The Azure AI Assistant Tool uses PySide6, which is licensed under the GNU Lesser General Public License (LGPL).
By using PySide6, you are able to modify and redistribute the library under the same license.
For more information on PySide6's license, please visit [Qt Licensing](https://www.qt.io/licensing/).
