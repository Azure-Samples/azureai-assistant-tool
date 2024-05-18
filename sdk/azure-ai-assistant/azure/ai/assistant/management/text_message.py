
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from typing import List, Optional


class FileCitation:
    """
    A class representing a file citation.

    :param file_id: The ID of the file.
    :type file_id: str
    :param file_name: The name of the file.
    :type file_name: str
    """
    def __init__(
            self, 
            file_id : str,
            file_name : str
    ) -> None:
        self._file_id = file_id
        self._file_name = file_name

    @property
    def file_id(self) -> str:
        """
        Returns the ID of the file.

        :return: The ID of the file.
        :rtype: str
        """
        return self._file_id

    @property
    def file_name(self) -> str:
        """
        Returns the name of the file.

        :return: The name of the file.
        :rtype: str
        """
        return self._file_name


class TextMessage:
    def __init__(self, content: str, file_citations: Optional[List[FileCitation]] = None):
        self._content = content
        self._file_citations = file_citations

    @property
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value: str):
        self._content = value

    @property
    def file_citations(self) -> Optional[List[FileCitation]]:
        return self._file_citations