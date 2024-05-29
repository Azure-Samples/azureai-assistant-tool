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
from promptflow.evals.evaluators import RelevanceEvaluator, SimilarityEvaluator

import pandas as pd

RESOURCES_PATH = Path(__file__).parent / 'resources' #path to resources folder
OUTPUT_PATH = Path(__file__).parent / 'output' #path to output folder
MODEL_ENV_VAR = os.environ.get('OPENAI_ASSISTANT_MODEL', 'gpt-4o') #deployment name
CLIENT_TYPE = os.environ.get('AI_CLIENT_TYPE', 'OPEN_AI')

PROMPTFLOW_CONFIG = AzureOpenAIModelConfiguration(
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
    azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", 'gpt-4o'),
)

def get_client_args(ai_client_type : str):
    try:
        client_args = {}
        if ai_client_type == "AZURE_OPEN_AI":
            if os.getenv("AZURE_OPENAI_API_KEY"):
                # Authenticate using an Azure OpenAI API key
                # This is generally discouraged, but is provided for developers
                # that want to develop locally inside the Docker container.
                print("Using Azure OpenAI with key")
                client_args["api_key"] = os.getenv("AZURE_OPENAI_API_KEY")
            else:
                # Authenticate using the default Azure credential chain
                # See https://docs.microsoft.com/azure/developer/python/azure-sdk-authenticate#defaultazurecredential
                # This will *not* work inside a Docker container.
                print("Using Azure OpenAI with default credential")
                default_credential = azure.identity.aio.DefaultAzureCredential(
                    exclude_shared_token_cache_credential=True
                )
                client_args["azure_ad_token_provider"] = azure.identity.aio.get_bearer_token_provider(
                    default_credential, "https://cognitiveservices.azure.com/.default"
                )
        elif ai_client_type == "OPEN_AI":
            # Authenticate using an OpenAI API key
            if os.getenv("OPENAI_API_KEY"):
                print("Using OpenAI with key")
                client_args["api_key"] = os.getenv("OPENAI_API_KEY")
            else:
                raise Exception("OpenAI API key not found.")
        return client_args
    except Exception as e:
        print(f"An error occurred: {e}")
        return {}

def initialize_assistant_client():
    with open(str(RESOURCES_PATH / 'config/eval_file_search_assistant_assistant_config.yaml'), "r") as f:
        config = yaml.safe_load(f)
    client_args = get_client_args(config["ai_client_type"])
    client = AssistantClient.from_yaml(yaml.dump(config), **client_args)
    return client

def evaluate_file_search_assistant_client(run_relevance: bool, run_similarity: bool):
    #initialize
    client = initialize_assistant_client()
    thread_client = ConversationThreadClient.get_instance(AIClientType[CLIENT_TYPE])
    thread_name = thread_client.create_conversation_thread()
    results = {
        "question": [],
        "ground truth": [],
        "response": [],
        "citation": [],
    }

    #pass assistant questions and get responses
    questions = str(RESOURCES_PATH / "assistant_test_dataset" / "questions.txt")
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
                    citations.append(citation.file_name)

                #store results
                results["question"].append(question)
                results["response"].append(response)
                results["citation"].append(citations)

            elif line.startswith("Expected Answer:"):
                answer = line.split(":")[1].strip()
                results["ground truth"].append(answer)
        
        #run necessary evals
        if run_relevance:
            print("running relevance evals")
            results["relevance_scores"] = run_relevance_evals(results.get("question"), results.get("response"), results.get("citation"))
        if run_similarity:
            print("running similarity evals")
            results["similarity_scores"] = run_similarity_evals(results.get("question"), results.get("response"), results.get("ground truth"))

    return results

def run_relevance_evals(questions: list, answers: list, citations: list):
    scores = []
    evaluator = RelevanceEvaluator(PROMPTFLOW_CONFIG)

    for i in range(len(questions)):
        evaluation_context = ""
        for citation in citations[i]:
            with open(str(RESOURCES_PATH / "assistant_test_dataset" / citation), 'r') as f:
                data = json.load(f)
                evaluation_context += json.dumps(data) + "\n"
        if evaluation_context == "":
            evaluation_context = "no context available"

        evaluation = evaluator(
            question=questions[i],
            answer=answers[i],
            context=evaluation_context,
        )
        scores.append(evaluation.get('gpt_relevance'))
    return scores

def run_similarity_evals(questions: list, answers: list, ground_truths: list):
    scores = []
    evaluator = SimilarityEvaluator(PROMPTFLOW_CONFIG)

    for i in range(len(questions)):
        evaluation = evaluator(
            question=questions[i],
            answer=answers[i],
            ground_truth=ground_truths[i],
        )
        scores.append(evaluation.get('gpt_similarity'))
    return scores

def display_results(results):
    df = pd.DataFrame(results)
    df.to_csv(str(OUTPUT_PATH / "report.csv"), index=False)

def main():
    results = evaluate_file_search_assistant_client(True, True)
    display_results(results)

if __name__ == "__main__":
    main()  