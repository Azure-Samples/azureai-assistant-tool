
## Azure OpenAI Service Configuration in Azure Portal

### Azure OpenAI Service API key, endpoint and model deployment version

To successfully make a call against the Azure OpenAI service, you'll need the following:

**- ENDPOINT:** This value can be found in the Keys and Endpoint section when examining your resource from the Azure portal. Alternatively, you can find the value in Azure OpenAI Studio > Playground > View code. An example endpoint is: https://docs-test-001.openai.azure.com/.

**- API-KEY:** This value can be found in the Keys and Endpoint section when examining your resource from the Azure portal. You can use either KEY1 or KEY2.

**- MODEL DEPLOYMENT-NAME:** This value will correspond to the custom name you chose for your deployment when you deployed a model. This value can be found under Resource Management > Model Deployments in the Azure portal or alternatively under Management > Deployments in Azure OpenAI Studio.

Next, go to your resource in the [Azure portal](https://ms.portal.azure.com/#home). The Keys and Endpoint can be found in the Resource Management section (see image below). Copy your endpoint and access key as you'll need both for authenticating your API calls. You can use either KEY1 or KEY2. Always having two keys allows you to securely rotate and regenerate keys without causing a service disruption.
![portal keys and endpoint](https://github.com/Azure-Samples/azureai-assistant-tool/assets/118226126/b4ddbbba-1b91-4525-b05d-b9673dd6e143)


## Environment Variables

The Azure AI Assistant Tool and SDK require the following environment variables to function properly. While these variables are automatically configured via Azure AI CLI commands, you have the option to set them manually using the instructions provided below.

#### Windows Users:

Use the `setx` command for permanent variables, or `set` for the current session:

```cmd
setx AZURE_OPENAI_API_KEY "Your Azure OpenAI Key"
setx AZURE_OPENAI_ENDPOINT "Your OpenAI Endpoint"
setx AZURE_OPENAI_API_VERSION "Azure OpenAI version"  # Optional, default is `2024-02-15-preview`
setx OPENAI_API_KEY "Your OpenAI Key"
```

#### Linux/Mac Users:

```bash
export AZURE_OPENAI_API_KEY="Your Azure OpenAI Key"
export AZURE_OPENAI_ENDPOINT="Your OpenAI Endpoint"
export AZURE_OPENAI_API_VERSION="Azure OpenAI version"  # Optional, default is `2024-02-15-preview`
export OPENAI_API_KEY="Your OpenAI Key"
```

**Optional**: Following environment variables are required for Cognitive Services Speech transcription and synthesis:

##### Windows:

```cmd
setx AZURE_AI_SPEECH_KEY "Your Speech Key"
setx AZURE_AI_SPEECH_REGION "Your Speech Region"
```

##### Linux/Mac:

```bash
export AZURE_AI_SPEECH_KEY="Your Speech Key"
export AZURE_AI_SPEECH_REGION="Your Speech Region"
```
