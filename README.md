<h1 align="center"> 🤖🛠️Azure AI Assistants Tool </h1>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)&ensp;
![Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)&ensp;
![CrossPlatform](https://img.shields.io/badge/cross-platform-blue)
</div>
<div align="center">
⚡Develop AI agents powered by Azure OpenAI Assistants, Chat Completion and Realtime APIs at lightning speed⚡
</div>
<br>

## Table of Contents

- 🤖🛠️ Azure AI Assistants Tool
- 🆕 Latest News
- 🧱 What is Assistants from Azure OpenAI Service?
- 🚀 How does this Tool help?
- 🔊🎤 OpenAI Realtime Support (Experimental)
- ✨ Quick Start: Getting Started with the Tool
- 📖 License
- Contributing
- Code of Conduct
- Getting Help

## 🤖🛠️ Azure AI Assistants tool 
Azure AI Assistants tool is an experimental Python application and middleware designed to simplify the development, experimentation, testing, and debugging of AI agents created with Azure OpenAI Assistants, Chat Completion and/or Realtime API based technologies. Use this powerful, easy-to-setup low-code playground tool to quickly experiment and build AI agents within your application.

> [!IMPORTANT]
> **The Azure AI Assistant Tool is experimental**, created to support your product ideation and experimentation using AI agents. As the tool evolves, expect significant updates and improvements. We welcome feedback and contributions to help shape its future.

## 🆕 Latest News

- **January 20, 2025:** Released 0.5.1 version of the tool containing **o1 Model Support** which allows to use o1 models with ChatAssistant (with limited completion settings) and **OpenAI Realtime Support**, with real-time audio interaction capabilities. The Azure Cognitive Services for speech input and output has been removed from the tool, however Azure Speech SDK is still used within OpenAI Realtime for keyword based detection. For more detailed information, refer to the OpenAI Realtime Support section below.


## 🧱 What is Assistants from Azure OpenAI Service?

🌟**Assistants**, API from Azure OpenAI Service, is a stateful evolution of the Chat Completions API. Assistants makes it easier for developers to create applications with sophisticated copilot-like experiences in their applications and enable developer access to powerful tools like Code Interpreter and File Search. Assistants is built on the same capabilities that power OpenAI’s GPT product and offers unparalleled flexibility for creating a wide range of copilot-like applications. Copilots created with Assistants can sift through data, suggest solutions, and automate tasks and use cases span a wide range: AI-powered product recommender, sales analyst app, coding assistant, employee Q&A chatbot, and more.

**Features** include:

- Inbuilt thread and memory management <br>
- Advanced Data Analysis, create data visualizations and solving complex code and math problems with **Code Interpreter**<br>
- Retrieval Augmented Generation with **File Search** tool<br>
- Build your own tools or call external tools and APIs with **Function Calling**<br>

**Learn more** about Assistants on Azure OpenAI Service:

  - Watch a [short video](https://www.youtube.com/watch?v=CMXtAe5DhXc&embeds_referring_euri=https%3A%2F%2Ftechcommunity.microsoft.com%2F&source_ve_path=OTY3MTQ&feature=emb_imp_woyt) about Azure OpenAI Assistants
  - Read the [launch announcement](https://techcommunity.microsoft.com/t5/ai-azure-ai-services-blog/azure-openai-service-announces-assistants-api-new-models-for/ba-p/4049940)
  - Get familiar with the [Assistants API Quickstart](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/assistant)


## 🚀 How Does This Tool Help?

- **Enable Rapid AI Agent Prototyping:** Rapidly create AI agent prototypes using OpenAI's technologies, Assistants, Chat Completion, and Realtime APIs. This includes user-friendly configurability of different agents, built-in system functions, specific tool configurations, and LLM configurations.

- **Enhance Developer Productivity:** Streamline the agent development process through built-in middleware libraries and tools, utilizing tools in prompt engineering to automate your coding tasks and integrate AI capabilities into your copilot applications more effectively.


## 🔊🎤 OpenAI Realtime Support (Experimental)

This section covers the Realtime capabilities for AI agent prototyping with OpenAI's Realtime APIs, focusing on speech and text input/output through real-time WebSocket communication.

Please note that these capabilities are offered as an experimental feature. They are intended primarily for exploration, demos, or proof-of-concept usage. 
We do not recommend using these features in production or business-critical applications until further notice.

### Key Features

- **Real-time Audio Interaction**: Use the Realtime API with speech input using predefined and integrated keyword `Computer` to trigger the conversation.
  - Using keyword can be helpful to optimize cost and reliability of your application. To create your own keywords, visit [Creating the Custom Keyword](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/custom-keyword-basics?pivots=programming-language-python). Currently only 1 keyword is supported.
- **Real-time Text Interaction**: Use the Realtime API with text input. The agent can respond back with audio or text.
- **Local Voice Activity Detection**: Efficiently manage audio data by detecting speech activities by using local voice activity detection.
- **Function Calling**: Customize the realtime agent with your own functions which runs asynchronously in the background.
- **Configurable AI Options**: Fine-tune realtime agent responses and behaviors with different options in Realtime API.

### Demo Video

Check out the demo video to see the OpenAI Realtime Support in action!

https://github.com/user-attachments/assets/b0c80b34-b825-4442-a80c-93f314909a92

### Resources

- [Realtime AI GitHub Repository](https://github.com/jhakulin/realtime-ai)
- [OpenAI Realtime WebSocket API Documentation](https://platform.openai.com/docs/guides/realtime)
- [Azure Speech Services Documentation](https://azure.microsoft.com/en-us/services/cognitive-services/speech-services/)


## ✨ Quick Start: Getting Started with the Tool

### Step 1: Complete Azure prerequisities

- Create an Azure Subscription for [free](https://azure.microsoft.com/en-us/free/ai-services/), if you don't have one already
- [Apply for access](https://aka.ms/oai/access) to Azure OpenAI Service in this Azure Subscription. Azure OpenAI Service is currently a limited access service so access is granted through an application process. Most applications are processed within a day of applying.
- Azure OpenAI Assistants is currently available in Sweden Central, East US 2, and Australia East. We are expanding our models and regional availability - see the [models guide](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models) for the latest model and regional availability for Assistants.
- Create an Azure OpenAI resource on [Azure Portal](https://ms.portal.azure.com) with one of the Assistants supported models from the models guide page deployed in that region

### Step 2: Install Python

The Azure AI Assistant tool requires Python >= 3.8 on your system. You can download Python from [the official website](https://www.python.org/downloads/).
Latest stable Python version is recommended.

Create a new Python virtual environment. Virtual environment is recommended for safe install the SDK packages:
 * On MacOS and Linux run:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```
* On Windows run:
   ```
   py -3 -m venv .venv
   .venv\scripts\activate
   ```

### Step 3: Install the tool and dependencies

Run the following command in your terminal to install all the necessary dependencies as specified in the requirements.txt file.

```
pip install -r requirements.txt
```

### Step 4: Build and install azure.ai.assistant Python library (Optional)

We have included the `azure.ai.assistant` library currently within this repository as part of the alpha status of the project. 
The plan is to release library on PyPI for more convenience installation in future.

Build the wheel for `azure.ai.assistant` library using the following instructions, or use the wheel package provided under the repo's release tags directly.

- Python wheel and setuptools packages are required to build the library package. You can install them using the commands: `pip install wheel`and `pip install setuptools`
- Go to the`sdk/azure-ai-assistant` folder
- Build the wheel using following command: `python setup.py sdist bdist_wheel`
- Go to generated `dist` folder
- Install the generated wheel using following command: `pip install --force-reinstall azure_ai_assistant-0.x.xa1-py3-none-any.whl`
  - This installation will pick the necessary dependencies for the library (openai, python-Levenshtein, fuzzywuzzy, Pillow, requests)


### Step 5: Find and copy your Azure OpenAI Service APIkey, endpoint and model deployment version

To successfully make a call against the Azure OpenAI Service, you'll need the following:

**- ENDPOINT:**	This value can be found in the Keys and Endpoint section when examining your resource from the Azure portal. Alternatively, you can find the value in Azure OpenAI Studio > Playground > View code. An example endpoint is: https://docs-test-001.openai.azure.com/.

**- API-KEY:**	This value can be found in the Keys and Endpoint section when examining your resource from the Azure portal. You can use either KEY1 or KEY2.

**- MODEL DEPLOYMENT-NAME:**	This value will correspond to the custom name you chose for your deployment when you deployed a model. This value can be found under Resource Management > Model Deployments in the Azure portal or alternatively under Management > Deployments in Azure OpenAI Studio.

Next, go to your resource in the [Azure portal](https://ms.portal.azure.com/#home). The Keys and Endpoint can be found in the Resource Management section (see image below). Copy your endpoint and access key as you'll need both for authenticating your API calls. You can use either KEY1 or KEY2. Always having two keys allows you to securely rotate and regenerate keys without causing a service disruption.
![portal keys and endpoint](https://github.com/Azure-Samples/azureai-assistant-tool/assets/118226126/b4ddbbba-1b91-4525-b05d-b9673dd6e143)

### Step 6: Setup Environment Variables

Create and assign persistent environment variables for your key and endpoint.

#### ⌨️ Command Line (CLI)

1. Set the Azure OpenAI Service key, endpoint. Version is optional and default currently is `2024-05-01-preview` for assistants.

**Windows:**
Use setx or set command depending on your preference.

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

### Step 7: Launch the application

#### ⌨️ Command Line (CLI)

In the root of this repository, command:

```
python main.py
```

This command will start the Azure AI Assistant Tool and you can interact with it through its user interface which looks something like this:

![Ai-Assistant-Tool-screenshot](/assets/AzureAIAssistantTool2.png)

### Tool In Action - Add Functions To Your Assistant

![Ai-Assistant-Tool-Functions-screenshot](/assets/AssistantToolMultiFunctions.png)

## 📖 License
The Azure AI Assistant Tool is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

### 📣 Notice Regarding PySide6
The Azure AI Assistant Tool uses PySide6, which is licensed under the GNU Lesser General Public License (LGPL).
By using PySide6, you are able to modify and redistribute the library under the same license.
For more information on PySide6's license, please visit [Qt Licensing](https://www.qt.io/licensing/).

## Contributing

We welcome contributions and suggestions! Please see the [contributing guidelines] for details.

## Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). Please see the [code of conduct](CODE_OF_CONDUCT.md) for details.

## Getting Help

### Issues

If you find a bug in the source code or a mistake in the documentation, feel free to [submit bug report][new issue page].
Or even better you could submit a pull request with a fix.

### Feature Requests

If there's an feature that you'd like to see added, feel free to file a [Feature Request][new issue page].

If you'd like to implement it yourself, please refer to our [contributing guidelines].

[contributing guidelines]: ./CONTRIBUTING.md
[new issue page]: https://github.com/Azure-Samples/azureai-assistant-tool/issues/new/choose
