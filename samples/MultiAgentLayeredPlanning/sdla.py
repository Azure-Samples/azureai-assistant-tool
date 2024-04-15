# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

class SWDevelopmentLeadAgent:
    def __init__(self, name, specialties, manager, conversation_client):
        self.name = name
        self.specialties = specialties
        self.manager = manager
        self.conversation_client = conversation_client
        self.engineers = []

    async def create_detailed_tasks(self, high_level_task):
        detailed_tasks = self.break_down_task(high_level_task)
        return detailed_tasks

    async def assign_tasks_to_engineers(self, tasks):
        for task in tasks:
            assigned_engineer = self.select_engineer_for_task(task)
            thread_name = await self.conversation_client.create_conversation_thread()
            await assigned_engineer.execute_task(task, thread_name)

    def select_engineer_for_task(self, task):
        return self.engineers[0]