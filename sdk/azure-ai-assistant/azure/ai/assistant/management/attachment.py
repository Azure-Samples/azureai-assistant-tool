# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from typing import Optional, List, Dict, Any
import os
from enum import Enum


class AttachmentType(Enum):
    IMAGE_FILE = 'image_file'
    DOCUMENT_FILE = 'document_file'


class AttachmentToolType(Enum):
    FILE_SEARCH = 'file_search'
    CODE_INTERPRETER = 'code_interpreter'


class AttachmentTool:
    """
    Represents a tool to add an attachment to.

    :param tool_type: The type of tool.
    :type tool_type: AttachmentToolType
    """
    def __init__(self, tool_type: AttachmentToolType):
        self.type = tool_type

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AttachmentTool':
        tool_type = AttachmentToolType(data["type"])
        return cls(tool_type=tool_type)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value
        }

    def __eq__(self, other):
        if isinstance(other, AttachmentTool):
            return self.type == other.type
        return False

    def __str__(self):
        return f"AttachmentTool: {self.type.name}"


class Attachment:
    """
    Represents an attachment to a message.

    :param file_path: The path to the file to attach.
    :type file_path: str
    :param attachment_type: The type of attachment.
    :type attachment_type: AttachmentType
    :param tool: The tool to add this file to.
    :type tool: Optional[AttachmentTool]
    """
    def __init__(self, file_path: str, attachment_type: AttachmentType, tool: Optional[AttachmentTool] = None):
        if not file_path or not isinstance(file_path, str):
            raise ValueError("file_path must be a non-empty string")

        self._file_path = file_path
        self._attachment_type = attachment_type
        self._tool = tool
        self._file_name = os.path.basename(file_path)
        self._file_id = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Attachment':
        """
        Create an Attachment instance from a dictionary.

        :param data: The dictionary containing the attachment data.
        :type data: Dict[str, Any]

        :return: The Attachment instance.
        :rtype: Attachment
        """
        file_path = data["file_path"]
        attachment_type = AttachmentType(data["attachment_type"])
        tool = AttachmentTool.from_dict(data["tools"][0]) if data["tools"] else None
        attachment = cls(file_path=file_path, attachment_type=attachment_type, tool=tool)
        attachment.file_id = data.get("file_id")
        attachment.file_name = data.get("file_name", os.path.basename(file_path))
        return attachment

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Attachment instance to a dictionary.

        :return: The dictionary containing the attachment data.
        :rtype: Dict[str, Any]
        """
        return {
            "file_name": self.file_name,
            "file_id": self.file_id,
            "file_path": self.file_path,
            "attachment_type": self.attachment_type.value,
            "tools": [self.tool.to_dict()] if self.tool else []
        }
    
    @property
    def file_id(self):
        """
        The ID of the file to attach to the message.

        :return: The ID of the file to attach to the message.
        :rtype: str
        """
        return self._file_id
    
    @file_id.setter
    def file_id(self, value):
        """
        Set the ID of the file to attach to the message.

        :param value: The ID of the file to attach to the message.
        :type value: str
        """
        if value is not None and not isinstance(value, str):
            raise ValueError("file_id must be a string or None")
        self._file_id = value

    @property
    def file_name(self):
        """
        The name of the file to attach to the message.

        :return: The name of the file to attach to the message.
        :rtype: str
        """
        return self._file_name
    
    @file_name.setter
    def file_name(self, value):
        """
        Set the name of the file to attach to the message.

        :param value: The name of the file to attach to the message.
        :type value: str
        """
        if not isinstance(value, str):
            raise ValueError("file_name must be a string")
        self._file_name = value

    @property
    def file_path(self):
        """
        The path to the file to attach.

        :return: The path to the file to attach.
        :rtype: str
        """
        return self._file_path
    
    @property
    def attachment_type(self):
        """
        The type of attachment.

        :return: The type of attachment.
        :rtype: AttachmentType
        """
        return self._attachment_type
    
    @property
    def tool(self):
        """
        The tool to add this file to.

        :return: The tool to add this file to.
        :rtype: Optional[AttachmentTool]
        """
        return self._tool

    def __eq__(self, other):
        if isinstance(other, Attachment):
            return (self.file_path == other.file_path and
                    self.attachment_type == other.attachment_type and
                    self.tool == other.tool)
        return False

    def __str__(self):
        return f"Attachment: {self.file_name} ({self.attachment_type.name}) with tool: {self.tool}"

