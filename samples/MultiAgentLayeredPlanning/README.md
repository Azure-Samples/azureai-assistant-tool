# Sample: Multi-Agent Code Task Orchestration

This sample demonstrates how to orchestrate multi-agent task execution using a conversation thread-based communication
between 2 agents for code programming and inspection and task planner agent working with user to create a plan
for the required SW coding tasks.

## Prerequisites

Please see the [Prerequisities] for details.

## Configure the sample

Sample consists of following agents and their roles:
- TaskPlannerAgent
  - Creates plan (tasks) using users input and knowledge about CodeProgrammerAgent and CodeInspectionAgent assistant instances to achieve the required SW engineering work.
  - Uses own conversation thread with user
- CodeProgrammerAgent
  - Configured to handle SW programming related tasks
  - Uses functions to access files for reading and writing
  - Uses shared conversation thread with CodeInspectionAgent
- CodeInspectionAgent
  - Configured to handle SW inspection related tasks
  - Uses functions to access files for reading
  - Uses shared conversation thread with CodeProgrammerAgent
- FileCreatorAgent
  - Configured to take CodeProgrammerAgent output as input and write code block contents to a file

### Configure the Agents

TaskPlannerAgent get the details about CodeProgrammerAgent and CodeInspectionAgent by file references in the yaml configuration.
NOTE: Check the file references paths are configured correctly for your environment, the file_references field in yaml config files 
require absolute path.
- IMPORTANT: If you are not seeing `CodeProgrammerAgent` or `CodeInspectionAgent` in the task list assistant provided, then it means your file
references are not correct in TaskPlannerAgent yaml configuration.

## Run the sample

```sh
python main.py
```

## Example run

```
C:\Git\forks\azureai-assistant-tool\samples\MultiAgentCodeOrchestration>python main.py

user: hello, implement basic cli application for chat between user and assistant using java programming language

TaskPlannerAgent: To create a basic CLI application for a chat between a user and an assistant using Java, we will need to perform the following tasks:

1. **Design the CLI Interface**: Define how the user will interact with the application through the command line. This includes parsing user input and displaying responses.

2. **Implement Chat Logic**: Create the logic that will handle the conversation between the user and the assistant. This could be a simple loop that takes user input and generates a response.

3. **Implement Assistant Responses**: Define a set of responses or a way to generate responses based on user input.

4. **Testing**: Ensure that the application works as expected, with the user being able to send messages and receive responses from the assistant.

5. **Review and Refinement**: Review the code to ensure it follows Java best practices and idiomatic styles, and refine it based on feedback.

Here's a plan to coordinate the assistants to complete this task:

[
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Design and implement a basic CLI application in Java that allows a user to chat with an assistant. The application should include a main loop that reads user input from the command line, processes it, and prints out a response. The responses can be predefined for simplicity. Ensure the application handles input and output correctly and includes basic error handling."
    },
    {
        "assistant": "CodeInspectionAgent",
        "task": "Review the Java CLI application code provided by the CodeProgrammerAgent. Ensure the code is complete, follows Java idiomatic styles, and includes proper documentation and error handling. Check that the application correctly parses user input, generates responses, and interacts with the user through the command line."
    },
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Refine the Java CLI application based on the feedback from the CodeInspectionAgent. Make sure all suggested improvements are implemented, and the application is fully functional and user-friendly."
    }
]

Before proceeding with this plan, I would like to confirm with you:

"Here's the plan based on your request to implement a basic CLI application for chat between a user and an assistant using Java. Would you like me to go ahead with this?"

user: yes, proceed

TaskPlannerAgent: Great! I'll proceed with the plan. Here it is again for your reference:

[
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Design and implement a basic CLI application in Java that allows a user to chat with an assistant. The application should include a main loop that reads user input from the command line, processes it, and prints out a response. The responses can be predefined for simplicity. Ensure the application handles input and output correctly and includes basic error handling."
    },
    {
        "assistant": "CodeInspectionAgent",
        "task": "Review the Java CLI application code provided by the CodeProgrammerAgent. Ensure the code is complete, follows Java idiomatic styles, and includes proper documentation and error handling. Check that the application correctly parses user input, generates responses, and interacts with the user through the command line."
    },
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Refine the Java CLI application based on the feedback from the CodeInspectionAgent. Make sure all suggested improvements are implemented, and the application is fully functional and user-friendly."
    }
]

The CodeProgrammerAgent will start by designing and implementing the Java CLI application. Once the initial implementation is complete, the CodeInspectionAgent will review the code for completeness, correctness, and quality. Finally, the CodeProgrammerAgent will refine the application based on the review feedback.

Let's begin the execution of the plan.

Task 1d9854f1-38de-4c22-a10a-aeacb8b8cf09 started with schedule ID: cb4d02bc-968a-4da6-96c0-02d5af5effc5

Task 1d9854f1-38de-4c22-a10a-aeacb8b8cf09 execute with schedule ID: cb4d02bc-968a-4da6-96c0-02d5af5effc5

CodeProgrammerAgent: starting the task with input: Design and implement a basic CLI application in Java that allows a user to chat with an assistant. The application should include a main loop that reads user input from the command line, processes it, and prints out a response. The responses can be predefined for simplicity. Ensure the application handles input and output correctly and includes basic error handling.

CodeProgrammerAgent: working on the task.....................................................................................
CodeProgrammerAgent: To design and implement a basic CLI (Command Line Interface) application in Java that simulates chatting with an assistant, we will follow these steps:

1. Create a Java class with a `main` method for the entry point of the application.
2. Inside the `main` method, implement a loop that will keep running until the user chooses to exit.
3. Read user input from the command line using a `Scanner` object.
4. Process the input and generate predefined responses based on the input.
5. Print out the response to the command line.
6. Implement basic error handling to ensure the application does not crash due to unexpected input.

Below is a simple Java application that satisfies the above requirements:

import java.util.Scanner;

public class ChatAssistant {

    private static final String EXIT_KEYWORD = "exit";

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in); // Create a Scanner object to read user input
        String input;

        System.out.println("Hello! I am your chat assistant. Type '" + EXIT_KEYWORD + "' to quit.");

        // Main loop
        while (true) {
            System.out.print("You: ");
            input = scanner.nextLine(); // Read user input

            // Check for exit condition
            if (input.trim().equalsIgnoreCase(EXIT_KEYWORD)) {
                System.out.println("Assistant: Goodbye!");
                break;
            }

            // Handle the input and generate a response
            String response = generateResponse(input);

            // Output the response
            System.out.println("Assistant: " + response);
        }

        scanner.close(); // Close the scanner
    }

    // Simple method to generate predefined responses
    private static String generateResponse(String input) {
        if (input == null || input.trim().isEmpty()) {
            return "Please say something, I'm getting bored!";
        } else if (input.trim().equalsIgnoreCase("hello")) {
            return "Hello there! How can I assist you today?";
        } else if (input.trim().equalsIgnoreCase("how are you")) {
            return "I'm a computer program, so I'm always operating at optimal efficiency!";
        } else {
            return "Sorry, I don't understand that. Can you try asking something else?";
        }
    }
}

To run this Java application:

1. Save the code to a file named `ChatAssistant.java`.
2. Open a command-line terminal or shell.
3. Navigate to the directory where you saved the file.
4. Compile the Java file using the command `javac ChatAssistant.java`.
5. Run the application using the command `java ChatAssistant`.

After starting the application, it will prompt you to type your input. You can chat with the assistant based on the predefined responses, and type `exit` when you wish to quit the application.

FileCreatorAgent: analyzing the CodeProgrammerAgent output for file creation

FileCreatorAgent: Function call create_file_with_specified_content with arguments {
  "file_name": "ChatAssistant",
  "output_directory": "output",
  "content": "import java.util.Scanner;\n\npublic class ChatAssistant {\n\n    private static final String EXIT_KEYWORD = \"exit\";\n\n    public static void main(String[] args) {\n        Scanner scanner = new Scanner(System.in); // Create a Scanner object to read user input\n        String input;\n        \n        System.out.println(\"Hello! I am your chat assistant. Type '\" + EXIT_KEYWORD + \"' to quit.\");\n        \n        // Main loop\n        while (true) {\n            System.out.print(\"You: \");\n            input = scanner.nextLine(); // Read user input\n\n            // Check for exit condition\n            if (input.trim().equalsIgnoreCase(EXIT_KEYWORD)) {\n                System.out.println(\"Assistant: Goodbye!\");\n                break;\n            }\n\n            // Handle the input and generate a response\n            String response = generateResponse(input);\n            \n            // Output the response\n            System.out.println(\"Assistant: \" + response);\n        }\n        \n        scanner.close(); // Close the scanner\n    }\n\n    // Simple method to generate predefined responses\n    private static String generateResponse(String input) {\n        if (input == null || input.trim().isEmpty()) {\n            return \"Please say something, I'm getting bored!\";\n        } else if (input.trim().equalsIgnoreCase(\"hello\")) {\n            return \"Hello there! How can I assist you today?\";\n        } else if (input.trim().equalsIgnoreCase(\"how are you\")) {\n            return \"I'm a computer program, so I'm always operating at optimal efficiency!\";\n        } else {\n            return \"Sorry, I don't understand that. Can you try asking something else?\";\n        }\n    }\n}\n",
  "file_extension": "java"
}, result OK.
FileCreatorAgent: The Java application code has been successfully written to a file named `ChatAssistant.java` in the `output` directory. You can find the file at the following path:

output/ChatAssistant.java

To run the application, follow the instructions provided in the text: compile it using `javac ChatAssistant.java` and then run it with `java ChatAssistant` from the command line in the directory where the file is located.

CodeInspectionAgent: starting the task with input: Review the Java CLI application code provided by the CodeProgrammerAgent. Ensure the code is complete, follows Java idiomatic styles, and includes proper documentation and error handling. Check that the application correctly parses user input, generates responses, and interacts with the user through the command line.

CodeInspectionAgent: working on the task..................................................................................................................................................................................
CodeInspectionAgent: The provided Java CLI application code by the CodeProgrammerAgent is complete in the sense that it can be compiled and run, providing a simple chat interaction with a user. However, there are a few improvements and best practices that can be applied to enhance the code.

Here are my observations and suggestions:

1. **Code Documentation**:
   - The class and methods are not documented. While the code is relatively simple and self-explanatory, it's a good practice to add JavaDoc comments to classes and methods, explaining their purpose.

2. **Use of Constants**:
   - The use of a constant for `EXIT_KEYWORD` is good since it avoids hardcoding the string multiple times.

3. **Error Handling**:
   - The application is simple and does not have much scope for errors that need to be handled. The `Scanner` object is used correctly, and no exceptions are expected from the operations performed.
   - One potential improvement could be to add handling for unexpected interruptions or I/O issues.

4. **Styling and Naming Conventions**:
   - Variable and method names follow Java naming conventions.
   - There's a proper use of `camelCase` for variable and method names.
   - The code is consistently indented, which is good for readability.

5. **User Input Parsing**:
   - The input is trimmed and compared case-insensitively, which is a good practice for a chat application where the format and casing of user entries can vary.
   - The handling for empty or whitespace-only inputs is a good touch for user experience.

6. **Program Exit**:
   - The program uses a `while (true)` loop with a break condition, which is acceptable. However, it could be refactored to instead test the exit condition in the `while` statement for better readability.

7. **Response Handling**:
   - The response handling is very basic and serves the example well. However, it might be improved by using a switch statement or a more sophisticated mechanism like a map of intents to responses if the application grows in complexity.

Here is the enhanced version of the `ChatAssistant` class with the suggested improvements:

import java.util.Scanner;

/**
 * A simple CLI chat assistant that responds to user input with predefined messages.
 */
public class ChatAssistant {

    private static final String EXIT_KEYWORD = "exit";

    /**
     * Entry point of the application.
     * @param args Command line arguments.
     */
    public static void main(String[] args) {
        try (Scanner scanner = new Scanner(System.in)) {
            System.out.println("Hello! I am your chat assistant. Type '" + EXIT_KEYWORD + "' to quit.");

            String input;
            while (true) {
                System.out.print("You: ");
                input = scanner.nextLine(); // Read user input

                if (input.trim().equalsIgnoreCase(EXIT_KEYWORD)) {
                    System.out.println("Assistant: Goodbye!");
                    break;
                }

                String response = generateResponse(input);
                System.out.println("Assistant: " + response);
            }
        } catch (Exception e) {
            System.err.println("An error occurred while reading input or processing the chat: " + e.getMessage());
        }
    }

    /**
     * Generates a response based on the user's input.
     * @param input The user input as a string.
     * @return A string representing the assistant's response.
     */
    private static String generateResponse(String input) {
        if (input == null || input.trim().isEmpty()) {
            return "Please say something, I'm getting bored!";
        } else {
            switch (input.trim().toLowerCase()) {
                case "hello":
                    return "Hello there! How can I assist you today?";
                case "how are you":
                    return "I'm a computer program, so I'm always operating at optimal efficiency!";
                default:
                    return "Sorry, I don't understand that. Can you try asking something else?";
            }
        }
    }
}

Changes made:
- Added JavaDoc comments to the class and methods.
- Used a try-with-resources statement with the `Scanner` object to ensure it closes properly.
- Switched to a switch-case structure for human-readable conditional logic which is more maintainable.
- Added basic exception handling in case unexpected issues arise with the `Scanner`, such as I/O exceptions.

This code maintains the functionality while improving maintainability and readability.

CodeProgrammerAgent: starting the task with input: Refine the Java CLI application based on the feedback from the CodeInspectionAgent. Make sure all suggested improvements are implemented, and the application is fully functional and user-friendly.

CodeProgrammerAgent: working on the task.......................................................................
CodeProgrammerAgent: Based on the feedback provided by the CodeInspectionAgent, I'll enhance the `ChatAssistant` Java application. This will include incorporating the suggested improvements to ensure that the application is fully functional and user-friendly.

Here is the refined version of the `ChatAssistant` class:

import java.util.Scanner;

/**
 * ChatAssistant is a simple CLI application that simulates a conversation
 * with a chat assistant by providing predefined responses to user inputs.
 */
public class ChatAssistant {

    private static final String EXIT_KEYWORD = "exit";

    /**
     * The main method serves as the entry point for the application.
     * It sets up a chat session and reads user input until the exit keyword is typed.
     *
     * @param args Command line arguments (not used in this application).
     */
    public static void main(String[] args) {
        try (Scanner scanner = new Scanner(System.in)) {
            System.out.println("Hello! I am your chat assistant. Type '" + EXIT_KEYWORD + "' to quit.");

            while (true) {
                System.out.print("You: ");
                String input = scanner.nextLine().trim(); // Read and trim user input

                if (input.equalsIgnoreCase(EXIT_KEYWORD)) {
                    break;
                }

                String response = generateResponse(input);
                System.out.println("Assistant: " + response);
            }

            System.out.println("Assistant: Goodbye!");
        } catch (Exception e) {
            System.err.println("An error occurred while reading input or processing the chat: " + e.getMessage());
        }
    }

    /**
     * Generates a response based on the user's input using predefined patterns.
     *
     * @param input The user's trimmed input as a string.
     * @return A string representing the assistant's response.
     */
    private static String generateResponse(String input) {
        if (input.isEmpty()) {
            return "Please say something, I'm getting bored!";
        }

        switch (input.toLowerCase()) {
            case "hello":
                return "Hello there! How can I assist you today?";
            case "how are you":
                return "I'm a computer program, so I'm always operating at optimal efficiency!";
            default:
                return "Sorry, I don't understand that. Can you try asking something else?";
        }
    }
}

Key Improvements:

- The `Scanner` usage has been enclosed in a try-with-resources block to ensure it is closed properly, without the need for an explicit `close()` call.
- The `input` string is now trimmed immediately after it is read from the user. This avoids repeated calls to `trim()` in other places in the code. The exit condition check is also simplified.
- I have used a `switch` statement in the `generateResponse` method, improving readability and scalability.
- JavaDoc comments have been added to the class and methods to explain their functionality.
- A simple error handling mechanism is implemented using a `try-catch` block to catch and report any potential `Exception`.

Now, the application is following the suggestions from the CodeInspectionAgent and includes the best practices in Java programming, such as proper error handling, readability, and maintainability.

To compile and run this application, you'd follow the same steps as mentioned in the initial solution: use `javac` to compile the Java file and then `java` to run the compiled program.

FileCreatorAgent: analyzing the CodeProgrammerAgent output for file creation

FileCreatorAgent: Function call create_file_with_specified_content with arguments {"file_name":"ChatAssistant","output_directory":"output","content":"import java.util.Scanner;\n\n/**\n * ChatAssistant is a simple CLI application that simulates a conversation\n * with a chat assistant by providing predefined responses to user inputs.\n */\npublic class ChatAssistant {\n\n    private static final String EXIT_KEYWORD = \"exit\";\n\n    /**\n     * The main method serves as the entry point for the application.\n     * It sets up a chat session and reads user input until the exit keyword is typed.\n     *\n     * @param args Command line arguments (not used in this application).\n     */\n    public static void main(String[] args) {\n        try (Scanner scanner = new Scanner(System.in)) {\n            System.out.println(\"Hello! I am your chat assistant. Type '\" + EXIT_KEYWORD + \"' to quit.\");\n\n            while (true) {\n                System.out.print(\"You: \");\n                String input = scanner.nextLine().trim(); // Read and trim user input\n                \n                if (input.equalsIgnoreCase(EXIT_KEYWORD)) {\n                    break;\n                }\n\n                String response = generateResponse(input);\n                System.out.println(\"Assistant: \" + response);\n            }\n\n            System.out.println(\"Assistant: Goodbye!\");\n        } catch (Exception e) {\n            System.err.println(\"An error occurred while reading input or processing the chat: \" + e.getMessage());\n        }\n    }\n\n    /**\n     * Generates a response based on the user's input using predefined patterns.\n     *\n     * @param input The user's trimmed input as a string.\n     * @return A string representing the assistant's response.\n     */\n    private static String generateResponse(String input) {\n        if (input.isEmpty()) {\n            return \"Please say something, I'm getting bored!\";\n        }\n\n        switch (input.toLowerCase()) {\n            case \"hello\":\n                return \"Hello there! How can I assist you today?\";\n            case \"how are you\":\n                return \"I'm a computer program, so I'm always operating at optimal efficiency!\";\n            default:\n                return \"Sorry, I don't understand that. Can you try asking something else?\";\n        }\n    }\n}\n","file_extension":"java"}, result OK.
FileCreatorAgent: The Java code for the `ChatAssistant` application has been successfully written to a file named `ChatAssistant.java` in the `output` directory. You can find the file at the following path:

output/ChatAssistant.java

Task 1d9854f1-38de-4c22-a10a-aeacb8b8cf09 completed with schedule ID: cb4d02bc-968a-4da6-96c0-02d5af5effc5. Result: Success

user:exit
Exiting chat.
```

[Prerequisities]: ../../README.md