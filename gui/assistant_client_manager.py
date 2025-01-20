# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from typing import Dict, Optional
from azure.ai.assistant.audio.realtime_audio import RealtimeAudio


class AssistantClientManager:
    _instance = None
    _clients = {}
    _audios: Dict[str, "RealtimeAudio"] = {}

    """
    A class to manage assistant clients.
    """
    def __init__(self) -> None:
        pass

    @classmethod
    def get_instance(cls) -> 'AssistantClientManager':
        """
        Get the singleton instance of the assistant client manager.

        :return: The singleton instance of the assistant client manager.
        :rtype: AssistantClientManager
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_client(
            self, 
            name : str,
            assistant_client, #: AssistantClient
            realtime_audio: Optional["RealtimeAudio"] = None
    ) -> None:
        """
        Register a new assistant client with the given name.

        :param name: The name of the assistant client.
        :type name: str
        :param assistant_client: The assistant client to register.
        :type assistant_client: AssistantClient
        :param realtime_audio: The RealtimeAudio instance associated with the assistant client.
        :type realtime_audio: RealtimeAudio, optional

        :return: None
        :rtype: None
        """
        self._clients[name] = assistant_client
        if realtime_audio:
            self._audios[name] = realtime_audio

    def remove_client(self, name : str) -> None:
        """
        Remove an assistant client with the given name.

        :param name: The name of the assistant client.
        :type name: str

        :return: None
        :rtype: None
        """
        if name in self._clients:
            del self._clients[name]
        if name in self._audios:
            del self._audios[name]
    
    def get_client(self, name : str):
        """
        Get an assistant client with the given name.

        :param name: The name of the assistant client.
        :type name: str

        :return: The assistant client with the given name.
        :rtype: AssistantClient
        """
        return self._clients.get(name)

    def get_audio(self, name: str) -> Optional["RealtimeAudio"]:
        """
        Get the RealtimeAudio instance associated with the given assistant client name.

        :param name: The name of the assistant client.
        :type name: str

        :return: The RealtimeAudio instance associated with the assistant client, or None if not found.
        :rtype: RealtimeAudio or None
        """
        return self._audios.get(name)

    def get_all_clients(self) -> list:
        """
        Get a list of all registered assistant clients.

        :return: A list of all registered assistant clients.
        :rtype: list
        """
        return list(self._clients.values())