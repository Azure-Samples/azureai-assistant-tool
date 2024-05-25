# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import json
import os
import yaml

from azure.ai.assistant.management.assistant_client import AssistantClient
from azure.ai.assistant.management.ai_client_factory import AIClientType
from azure.ai.assistant.management.conversation_thread_client import ConversationThreadClient

from pathlib import Path

from promptflow.core import AzureOpenAIModelConfiguration
from promptflow.evals.evaluators import RelevanceEvaluator

RESOURCES_PATH = Path(__file__).parent / 'resources' #path to resources folder
OUTPUT_PATH = Path(__file__).parent / 'output' #path to output folder
MODEL_ENV_VAR = os.environ.get('OPENAI_ASSISTANT_MODEL', 'gpt-4o') #deployment name
CLIENT_TYPE = os.environ.get('AI_CLIENT_TYPE', 'OPEN_AI')

PROMPTFLOW_CONFIG = AzureOpenAIModelConfiguration(
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
    azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", 'gpt-4o'),
)

def initialize_assistant_client():
    with open(str(RESOURCES_PATH / 'config/eval_file_search_assistant_assistant_config.yaml'), "r") as file:
        config = yaml.safe_load(file)
    client = AssistantClient.from_yaml(yaml.dump(config))
    return client

def evaluate_file_search_assistant_client_relevance():
    client = initialize_assistant_client()
    questions_store, responses_store, citations_store, scores_store = [], [], [], []

    #initialize thread
    thread_client = ConversationThreadClient.get_instance(AIClientType[CLIENT_TYPE])
    thread_name = thread_client.create_conversation_thread()

    #pass assistant questions and eval answers
    questions = str(RESOURCES_PATH / "assistant_test_dataset" / "questions.txt")
    evaluator = RelevanceEvaluator(PROMPTFLOW_CONFIG)
    with open(questions, 'r') as f:
        for line in f:
            if line.startswith("Question:"):
                #ask question
                question = line.split(":")[1].strip()
                thread_client.create_conversation_thread_message(question, thread_name)
                client.process_messages(thread_name)
                conversation = thread_client.retrieve_conversation(thread_name)

                #get response and citation files
                last_message = conversation.get_last_text_message(client.assistant_config.name)
                response = last_message.content.split("\n")[0].split("[0]")[0].strip()
                citations = []
                for citation in last_message.file_citations:
                    citations.append(str(RESOURCES_PATH / "assistant_test_dataset" /citation.file_name))
                
                #evaluate response
                eval_context = ""
                for citation in citations:
                    with open(citation, 'r') as f:
                        data = json.load(f)
                        eval_context += json.dumps(data) + "\n"
                if eval_context == "":
                    eval_context = "no context available"
                evaluation = evaluator(
                    question=question,
                    answer=response,
                    context=eval_context,
                )
                score = evaluation.get('gpt_relevance') > 0.0