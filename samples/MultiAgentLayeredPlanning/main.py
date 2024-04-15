# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from azure.ai.assistant.management.ai_client_factory import AsyncAIClientType
from azure.ai.assistant.management.async_conversation_thread_client import AsyncConversationThreadClient
from samples.MultiAgentLayeredPlanning.sema import SWEngineeringManagerAgent

from typing import Dict, List
import json, re
import asyncio


async def main():

    conversation_thread_client = AsyncConversationThreadClient.get_instance(AsyncAIClientType.AZURE_OPEN_AI)
    sema = SWEngineeringManagerAgent(conversation_thread_client)
    await sema.async_init()

    planner_thread = await conversation_thread_client.create_conversation_thread()

    while True:
        user_request = input("\nuser: ").strip()
        if user_request.lower() == 'exit':  # Allow the user to exit the chat
            print("Exiting chat.")
            break
        if not user_request:
            continue
        await conversation_thread_client.create_conversation_thread_message(user_request, planner_thread)
        await sema.process_messages(thread_name=planner_thread)

    await conversation_thread_client.close()

if __name__ == "__main__":
    asyncio.run(main())