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

    def __str__(self):
        return f"AttachmentTool: {self.type.name}"


class Attachment:
    def __init__(self, file_path: str, attachment_type: AttachmentType, tool: Optional[AttachmentTool] = None):
        if not file_path or not isinstance(file_path, str):
            raise ValueError("file_path must be a non-empty string")

        self.file_path = file_path
        self.attachment_type = attachment_type
        self.tool = tool
        self.file_name = os.path.basename(file_path)
        self.file_id = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Attachment':
        file_path = data["file_path"]
        attachment_type = AttachmentType(data["attachment_type"])
        tool = AttachmentTool.from_dict(data["tools"][0]) if data["tools"] else None
        attachment = cls(file_path=file_path, attachment_type=attachment_type, tool=tool)
        attachment.file_id = data.get("file_id")
        attachment.file_name = data.get("file_name", os.path.basename(file_path))
        return attachment

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_name": self.file_name,
            "file_id": self.file_id,
            "file_path": self.file_path,
            "attachment_type": self.attachment_type.value,
            "tools": [self.tool.to_dict()] if self.tool else []
        }

    def __str__(self):
        return f"Attachment: {self.file_name} ({self.attachment_type.name}) with tool: {self.tool}"

