<h1 align="center"> 🤖🛠️Azure AI Assistants Tool </h1>

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)&ensp;
![Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)
![CrossPlatform](https://img.shields.io/badge/cross-platform-blue)
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
📤 Exporting the assistant configuration into simple CLI application

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
- Azure OpenAI Assistants is currently available in Sweden Central, East US 2, and Australia East. We are expanding our models and regional availability - see the [models guide](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models) for the latest model and regional availability for Assistants.

### Step 2: Install Python

Azure AI Assistant tool requires Python >= 3.8 on your system. You can download Python from [the official website](https://www.python.org/downloads/).
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

### Step 3: Build and install azure.ai.assistant Python library

We have included the `azure.ai.assistant` library currently within this repository as part of the alpha status of the project. 
The plan is to release library on PyPI for more convenience installation in future.

Build the wheel for `azure.ai.assistant` library using the following instructions, or use the wheel package provided under the repo's release tags directly.

- Ensure wheel is installed to build the library package. You can install it using the command: `pip install wheel`
- Go to the`sdk/azure-ai-assistant` folder
- Build the wheel using following command: `python setup.py sdist bdist_wheel`
- Go to generated `dist` folder
- Install the generated wheel using following command: `pip install --force-reinstall azure_ai_assistant-0.2.5a1-py3-none-any.whl`
  - This installation will pick the necessary dependencies for the library (openai, python-Levenshtein, fuzzywuzzy, Pillow, requests, azure-identity, azure-mgmt-cognitiveservices)

### Step 4: Install Python UI libraries

Install following specific libraries needed for the Azure AI Assistant Tool GUI

```
pip install PySide6
pip install azure-cognitiveservices-speech

```

### Step 5: Configure Azure resources using Azure AI CLI

#### Install Azure AI CLI

With Azure AI CLI you can create all resources needed for the Azure OpenAI assistants in your dev environment and configure the environment variables for the SDK and tool.

**On Ubuntu**, you can use this all-in-one installer command:
```
curl -sL https://aka.ms/InstallAzureAICLIDeb | sudo bash
```

**On Windows and MacOS**, follow the instructions [here](https://aka.ms/aistudio/docs/cli).

#### Create or connect to your Azure Resources

1. Run the `ai init` command.
```
ai init
```
2. You will be prompted to log in to Azure.
3. After logging in, you will be asked to select or create resources. 
- [Check the available regions and models for assistants](https://learn.microsoft.com/azure/ai-services/openai/concepts/models#assistants-preview).
4. Choose the option for a `New AI Project` and follow the prompts to create:
- An Azure AI resource using your subscription
- An Azure AI project
- Azure OpenAI Service model deployments
- You can skip the resources related to Embeddings, Search and Deployments as they are not required for assistants.
5. After you have created a model deployment for your resource, run `ai dev shell` command which opens a new shell with all required environment variables configured.
```
ai dev shell
```

For more information about Azure resources and configuration inside Azure Portal and detailed information about required environment variables, see [resources] page.

### Step 6: Launch the application

#### ⌨️ Command Line (CLI)

In the root of this repository, command:

```
python main.py
```

This command will start the Azure AI Assistant Tool and you can interact with it through its user interface which looks something like this:

![Ai-Assistant-Tool-screenshot](/assets/AzureAIAssistantTool2.png)

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
[resources]: ./RESOURCES.md
[new issue page]: https://github.com/Azure-Samples/azureai-assistant-tool/issues/new/choose