
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


class UrlCitation:
    """
    A class representing a URL citation.

    :param url: The URL being cited.
    :type url: str
    :param title: An optional title or label for the URL.
    :type title: Optional[str]
    """
    def __init__(
            self,
            url: str,
            title: Optional[str] = None
    ) -> None:
        self._url = url
        # If no title is provided, use the URL as the fallback
        self._title = title or url

    @property
    def url(self) -> str:
        """
        Returns the cited URL.

        :return: The cited URL.
        :rtype: str
        """
        return self._url

    @property
    def title(self) -> str:
        """
        Returns the title (or fallback) of the cited URL.

        :return: The title for this citation.
        :rtype: str
        """
        return self._title


class TextMessage:
    """
    A class representing a text message.

    :param content: The content of the message.
    :type content: str
    :param file_citations: The list of file citations in the message.
    :type file_citations: Optional[List[FileCitation]]
    :param url_citations: The list of URL citations in the message.
    :type url_citations: Optional[List[UrlCitation]]
    """
    def __init__(
        self,
        content: str,
        file_citations: Optional[List[FileCitation]] = None,
        url_citations: Optional[List[UrlCitation]] = None
    ):
        self._content = content
        # Initialize citations to empty lists if None is provided
        self._file_citations = file_citations or []
        self._url_citations = url_citations or []

    @property
    def content(self) -> str:
        """
        Returns the content of the message.

        :return: The content of the message.
        :rtype: str
        """
        return self._content

    @content.setter
    def content(self, value: str):
        """
        Sets the content of the message.

        :param value: The content of the message.
        :type value: str
        """
        self._content = value

    @property
    def file_citations(self) -> List[FileCitation]:
        """
        Returns the list of file citations in the message.

        :return: The list of file citations in the message.
        :rtype: List[FileCitation]
        """
        return self._file_citations

    @property
    def url_citations(self) -> List[UrlCitation]:
        """
        Returns the list of URL citations in the message.

        :return: The list of URL citations in the message.
        :rtype: List[UrlCitation]
        """
        return self._url_citations