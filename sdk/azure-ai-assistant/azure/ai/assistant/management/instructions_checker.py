# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

from openai import OpenAI
from azure.ai.assistant.management.logger_module import logger
import json, os


class InstructionsChecker:
    """
    A class to check instructions against guidelines.

    :param client: The OpenAI client.
    :type client: OpenAI
    :param model: The model to use for checking the instructions.
    :type model: str
    :param config_folder: The folder containing the configuration files.
    :type config_folder: str
    """
    def __init__(
            self, 
            client : OpenAI, 
            model : str, 
            config_folder="config"
    ) -> None:
        self._client = client
        self._model = model
        self._config_folder = config_folder
        self._filename = "assistant_instructions_guidelines.json"
        self._filepath = os.path.join(self._config_folder, self._filename)
        self._guideline = self._load_guidelines(self._filepath)
        logger.info("InstructionsChecker, guidelines: " + str(self._guideline))

    def _load_guidelines(self, file_path):
        default_guidelines = {
            "1": "Instructions are always a numbered list",
            "2": "Instructions are very clear and provide specific information for the assistant",
            "3": "Instructions do not leave room for misunderstandings"
        }
        if file_path:
            logger.info("Loading guidelines from file: " + file_path)
            try:
                with open(file_path, 'r') as file:
                    return json.load(file)
            except Exception as e:
                logger.error(f"Error reading guidelines file: {e}")
                return default_guidelines
        else:
            return default_guidelines

    def _format_system_message(self):
        content = "The following are the guidelines that given instructions should follow:\n"
        for key, guideline in self._guideline.items():
            content += f" {key}. {guideline}\n"
        content += "Your role is to check the instructions against the above guidelines and provide improvements. Return always improved instructions as a numbered list back.\n"
        return [{"role": "system", "content": content}]

    def check_instructions(
            self, 
            instructions_text
    ) -> str:
        """
        Check the given instructions against guidelines and return improved instructions.

        :param instructions_text: The instructions to check.
        :type instructions_text: str

        :return: The improved instructions.
        :rtype: str
        """
        try:
            messages = self._format_system_message()
            logger.info("Please modify instructions against guideline you have been given and return them back: \n" + instructions_text)
            request = "INSTRUCTIONS: \n" + instructions_text
            messages.append({"role": "user", "content": request})
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages
            )
            instructions_result = response.choices[0].message.content
            instructions_result = instructions_result.replace('"', '')
            logger.info("InstructionsChecker, response: " + instructions_result)
            return instructions_result
        except Exception as e:
            logger.error("Error: " + str(e))
            return instructions_text