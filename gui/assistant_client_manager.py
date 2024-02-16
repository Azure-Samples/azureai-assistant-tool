# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.


class AssistantClientManager:
    _instance = None
    _clients = {}

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
            assistant_client #: AssistantClient
    ) -> None:
        """
        Register a new assistant client with the given name.

        :param name: The name of the assistant client.
        :type name: str
        :param assistant_client: The assistant client to register.
        :type assistant_client: AssistantClient

        :return: None
        :rtype: None
        """
        self._clients[name] = assistant_client

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

    def get_client(self, name : str):
        """
        Get an assistant client with the given name.

        :param name: The name of the assistant client.
        :type name: str

        :return: The assistant client with the given name.
        :rtype: AssistantClient
        """
        return self._clients.get(name)

    def get_all_clients(self) -> list:
        """
        Get a list of all registered assistant clients.

        :return: A list of all registered assistant clients.
        :rtype: list
        """
        return list(self._clients.values())