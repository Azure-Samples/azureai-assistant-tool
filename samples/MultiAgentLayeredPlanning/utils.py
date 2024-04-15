# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import re

def extract_json_code_block(text):
    """
    Extracts and returns the content of the first JSON code block found in the given text.
    If no JSON code block markers are found, returns the original input text.
    """
    pattern = r"```json\n([\s\S]*?)\n```"
    match = re.search(pattern, text)
    return match.group(1) if match else text


def requires_user_confirmation(assistant_response: str):
    """
    Checks if the response requires user confirmation.

    NOTE: This is a very simple implementation and may not cover all cases.
    Could be improved e.g. by using a ML model to detect the intent from the response and context.
    """
    # Remove text under json code block
    assistant_response = re.sub(r"```json\n([\s\S]*?)\n```", "", assistant_response)
    # if text contains question mark, return True
    return "?" in assistant_response
