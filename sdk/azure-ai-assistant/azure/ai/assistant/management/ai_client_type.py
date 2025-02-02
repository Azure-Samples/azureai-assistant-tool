# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from enum import Enum, auto


class AIClientType(Enum):
    """
    An enum for the different types of AI clients.
    """
    AZURE_OPEN_AI = auto()
    """Azure OpenAI client"""
    OPEN_AI = auto()
    """OpenAI client"""
    AZURE_OPEN_AI_REALTIME = auto()
    """Azure OpenAI client used with Realtime API"""
    OPEN_AI_REALTIME = auto()
    """OpenAI client used with Realtime API"""
    AZURE_AI_AGENT = auto()
    """Azure AI Agents client"""


class AsyncAIClientType(Enum):
    """
    An enum for the different types of AI clients.
    """
    AZURE_OPEN_AI = auto()
    """Azure OpenAI async client"""
    OPEN_AI = auto()
    """OpenAI async client"""
    AZURE_OPEN_AI_REALTIME = auto()
    """Azure OpenAI async client used with Realtime API"""
    OPEN_AI_REALTIME = auto()
    """OpenAI async client used with Realtime API"""
    AZURE_AI_AGENT = auto()
    """Azure AI Agents async client"""
