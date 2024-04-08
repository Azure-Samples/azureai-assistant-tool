# Sample: Multi-Agent Task Orchestrator

This sample demonstrates how to orchestrate multi-agent task execution using a conversation thread-based approach.

## Prerequisites

Please see the [Prerequisities] for details.

## Configure the sample

Sample consists of following agents and their roles:
- TaskPlannerAgent
  - Creates plan (tasks) using CodeProgrammerAgent and CodeInspectionAgent to achieve the required SW engineering work.
  - The input TaskPlannerAgent uses is the user request and knowledge about available assistants
  - Uses own conversation thread with user
- CodeProgrammerAgent
  - Configured to handle SW programming related tasks
  - Uses shared conversation thread with CodeInspectionAgent
- CodeInspectionAgent
  - Configured to handle SW inspection related tasks
  - Uses shared conversation thread with CodeProgrammerAgent

### Configure the Agents

TaskPlannerAgent knows the details about CodeProgrammerAgent and CodeInspectionAgent by given instructions as file references.
NOTE: Check the file references paths are configured correctly in your environment, the file_references field in yaml requires absolute path.

## Run the sample

```sh
python main.py
```

## Example run

![Multi-Agent-screenshot](../../assets/MultiAgent.png)

[Prerequisities]: ../../README.md