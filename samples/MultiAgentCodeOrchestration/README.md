# Sample: Multi-Agent Code Task Orchestration

This sample demonstrates how to orchestrate multi-agent task execution using a conversation thread-based communication
between multiple agents for code programming, inspection, planning, file creation, and decision-making based on user interactions.

## Prerequisites

Please see the [Prerequisities] for details.

## Configure the sample

Sample consists of the following agents and their roles:

### UserAgent
  - **Role**: Guides the user to make decisions and ensures the correct agent handles user requests.
  - Manages the interaction between `TaskPlannerAgent` and `TaskExecutionAgent`.
  - Decides whether `TaskPlannerAgent` should create or improve a plan, or if `TaskExecutionAgent` should execute the plan.
  - Provides help if the user request is not related to planning or execution.

### TaskPlannerAgent
  - **Role**: Creates a plan (tasks) using user input and knowledge about `CodeProgrammerAgent` and `CodeInspectionAgent` assistant instances to achieve the required software engineering work.
  - Uses its own conversation thread with the user.

### TaskExecutionAgent
  - **Role**: Schedules and executes the plan created by `TaskPlannerAgent`.
  - Processes messages to carry out the planned tasks and coordinates with other agents as necessary.

### CodeProgrammerAgent
  - **Role**: Handles software programming related tasks.
  - Uses functions to access files for reading and writing.
  - Uses a shared conversation thread with `CodeInspectionAgent`.

### CodeInspectionAgent
  - **Role**: Handles software inspection related tasks.
  - Uses functions to access files for reading.
  - Uses a shared conversation thread with `CodeProgrammerAgent`.

### FileCreatorAgent
  - **Role**: Takes `CodeProgrammerAgent` output as input and writes the code block contents to a file.

## Configure the Agents

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


  {
      "action": "create_plan",
      "details": "Creating a plan for a basic CLI application for chat between user and assistant using Java programming language."
  }

Here's the plan based on your request. Would you like me to go ahead with this?

[
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Create a basic CLI application in Java that allows a user to chat with an assistant. The application should include the following features:\n1. A main class to run the application.\n2. A method to read user input from the command line.\n3. A method to simulate assistant responses.\n4. A loop to continue the chat until the user types 'exit'.\n5. Proper error handling and input validation."
    },
    {
        "assistant": "CodeInspectionAgent",
        "task": "Review the Java CLI application created by the CodeProgrammerAgent. Ensure that the code adheres to idiomatic Java programming styles, industry best practices, and fulfills the specified requirements. Check for completeness, documentation, coding standards, and error handling."
    },
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Implement any feedback provided by the CodeInspectionAgent to improve the Java CLI application."
    }
]

user: proceed


  {
      "action": "execute_plan",
      "details": "Proceeding to execute the plan for creating a basic CLI application for chat between user and assistant using Java programming language."
  }

Here's the execution plan in the correct format:

[
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Create a basic CLI application in Java that allows a user to chat with an assistant. The application should include the following features:\n1. A main class to run the application.\n2. A method to read user input from the command line.\n3. A method to simulate assistant responses.\n4. A loop to continue the chat until the user types 'exit'.\n5. Proper error handling and input validation."
    },
    {
        "assistant": "CodeInspectionAgent",
        "task": "Review the Java CLI application created by the CodeProgrammerAgent. Ensure that the code adheres to idiomatic Java programming styles, industry best practices, and fulfills the specified requirements. Check for completeness, documentation, coding standards, and error handling."
    },
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Implement any feedback provided by the CodeInspectionAgent to improve the Java CLI application."
    }
]

Task 754bd369-eda4-4e33-b9b7-026dacad0726 started with schedule ID: 4de8812e-85f3-4df3-869a-c859c117496f

Task 754bd369-eda4-4e33-b9b7-026dacad0726 execute with schedule ID: 4de8812e-85f3-4df3-869a-c859c117496f

CodeProgrammerAgent: starting the task with input: Create a basic CLI application in Java that allows a user to chat with an assistant. The application should include the following features:
1. A main class to run the application.
2. A method to read user input from the command line.
3. A method to simulate assistant responses.
4. A loop to continue the chat until the user types 'exit'.
5. Proper error handling and input validation.

CodeProgrammerAgent: working on the task...........
Here is a basic CLI application in Java that allows a user to chat with an assistant. The application includes the specified features.

### ChatAssistant.java

import java.util.Scanner;

public class ChatAssistant {

    public static void main(String[] args) {
        ChatAssistant assistant = new ChatAssistant();
        assistant.startChat();
    }

    public void startChat() {
        Scanner scanner = new Scanner(System.in);
        String userInput;

        System.out.println("Welcome to ChatAssistant! Type 'exit' to end the chat.");

        while (true) {
            System.out.print("You: ");
            userInput = readUserInput(scanner);

            // Exit condition
            if ("exit".equalsIgnoreCase(userInput)) {
                System.out.println("ChatAssistant: Goodbye!");
                break;
            }

            // Generate and print assistant response
            String response = generateAssistantResponse(userInput);
            System.out.println("ChatAssistant: " + response);
        }
    }

    private String readUserInput(Scanner scanner) {
        String input = "";
        try {
            input = scanner.nextLine();
            if (input.trim().isEmpty()) {
                throw new IllegalArgumentException("Input cannot be empty. Please enter a valid message.");
            }
        } catch (IllegalArgumentException e) {
            System.out.println("Error: " + e.getMessage());
            System.out.print("You: ");
            return readUserInput(scanner);
        }
        return input;
    }

    private String generateAssistantResponse(String userInput) {
        // Simple simulation of assistant responses with some placeholder logic
        if (userInput.equalsIgnoreCase("hi") || userInput.equalsIgnoreCase("hello")) {
            return "Hello! How can I assist you today?";
        } else if (userInput.equalsIgnoreCase("how are you")) {
            return "I'm just a program, but I'm here to help you!";
        } else {
            return "Tell me more...";
        }
    }
}

### Explanation:

1. **Main Class and Entry Point (`ChatAssistant`)**: The `main` method is the entry point for the application, creating an instance of `ChatAssistant` and starting the chat.

2. **Reading User Input (`readUserInput` method)**: This method reads input from the user via the command line. It includes error handling to ensure that the user input is not empty.

3. **Generating Assistant Responses (`generateAssistantResponse` method)**: This method simulates the assistant's responses based on the user's input. Here, simple placeholder logic is used to generate responses.

4. **Chat Loop (`startChat` method)**: This method contains a loop that continues to prompt the user for input until the user types 'exit'. Within the loop, it reads the user's input, generates a response, and prints it.

5. **Error Handling and Input Validation**: Within the `readUserInput` method, input validation is performed to check for empty input, and appropriate error messages are displayed.

Compile and run the program using a Java compiler, and it will prompt the user for inputs, simulating a chat assistant.

### How to Run
1. Save the code to a file named `ChatAssistant.java`.
2. Open a terminal or command prompt.
3. Navigate to the directory containing `ChatAssistant.java`.
4. Compile the program: `javac ChatAssistant.java`
5. Run the program: `java ChatAssistant`

You can now chat with the assistant by typing in the terminal. The conversation continues until you type 'exit'.

FileCreatorAgent: starting the task

FileCreatorAgent: Function call create_file_with_specified_content with arguments {"file_name": "ChatAssistant", "output_directory": "output", "content": "import java.util.Scanner;\n\npublic class ChatAssistant {\n\n    public static void main(String[] args) {\n        ChatAssistant assistant = new ChatAssistant();\n        assistant.startChat();\n    }\n\n    public void startChat() {\n        Scanner scanner = new Scanner(System.in);\n        String userInput;\n        \n        System.out.println(\"Welcome to ChatAssistant! Type 'exit' to end the chat.\");\n\n        while (true) {\n            System.out.print(\"You: \");\n            userInput = readUserInput(scanner);\n            \n            // Exit condition\n            if (\"exit\".equalsIgnoreCase(userInput)) {\n                System.out.println(\"ChatAssistant: Goodbye!\");\n                break;\n            }\n\n            // Generate and print assistant response\n            String response = generateAssistantResponse(userInput);\n            System.out.println(\"ChatAssistant: \" + response);\n        }\n    }\n\n    private String readUserInput(Scanner scanner) {\n        String input = \"\";\n        try {\n            input = scanner.nextLine();\n            if (input.trim().isEmpty()) {\n                throw new IllegalArgumentException(\"Input cannot be empty. Please enter a valid message.\");\n            }\n        } catch (IllegalArgumentException e) {\n            System.out.println(\"Error: \" + e.getMessage());\n            System.out.print(\"You: \");\n            return readUserInput(scanner);\n        }\n        return input;\n    }\n\n    private String generateAssistantResponse(String userInput) {\n        // Simple simulation of assistant responses with some placeholder logic\n        if (userInput.equalsIgnoreCase(\"hi\") || userInput.equalsIgnoreCase(\"hello\")) {\n            return \"Hello! How can I assist you today?\";\n        } else if (userInput.equalsIgnoreCase(\"how are you\")) {\n            return \"I'm just a program, but I'm here to help you!\";\n        } else {\n            return \"Tell me more...\";\n        }\n    }\n}", "file_extension": "java"}, result OK.
FileCreatorAgent: The file `ChatAssistant.java` has been created successfully and saved in the `output` directory.

You can now compile and run the program using the following steps:

1. Open a terminal or command prompt.
2. Navigate to the `output` directory:
   cd output
3. Compile the program:
   javac ChatAssistant.java
4. Run the program:
   java ChatAssistant

You can now chat with the assistant by typing in the terminal. The conversation continues until you type 'exit'.

CodeInspectionAgent: starting the task with input: Review the Java CLI application created by the CodeProgrammerAgent. Ensure that the code adheres to idiomatic Java programming styles, industry best practices, and fulfills the specified requirements. Check for completeness, documentation, coding standards, and error handling.

CodeInspectionAgent: working on the task.....................
Let's review the Java CLI application created by the CodeProgrammerAgent based on the specified requirements:

### Code Review

#### Completeness Check:
- **Main Class:** The main class `ChatAssistant` is correctly implemented to run the application.
- **User Input:** The method `readUserInput` reads user input from the command line.
- **Assistant Responses:** The method `generateAssistantResponse` simulates assistant responses.
- **Chat Loop:** The loop in `startChat` continues until the user types 'exit'.
- **Error Handling:** The code includes error handling for empty input.

The implementation appears to be complete and fulfills the specified requirements.

#### Documentation Review:
- **Comments:** The code lacks comments that explain the purpose of functions, classes, and significant code blocks. Adding comments would improve readability and maintainability.
- **Docstrings:** Java typically uses Javadoc comments for method documentation, which are missing.

#### Coding Standards and Style:
- **Naming Conventions:** The naming conventions are consistent with Java standards (e.g., camelCase for methods and camelCase for variables).
- **Structuring:** The code is well-structured with appropriate method separation.
- **Readability:** The code is readable but could be enhanced with more comments.

#### Error Handling and Validation:
- **Error Handling:** The `readUserInput` method includes error handling for empty input by using an `IllegalArgumentException`. However, the recursive call within the catch block could lead to a stack overflow if the user repeatedly inputs empty strings. An iterative approach (using a loop) would be safer.
- **Validation:** Basic validation for empty input is implemented. Further validation could include trimming whitespace universally.

### Updated Code with Enhancements

I've made the following enhancements:
- Added comments for better understanding.
- Used Javadoc comments for method documentation.
- Modified error handling in `readUserInput` to use a loop instead of recursion.

import java.util.Scanner;

/**
 * Main class for the ChatAssistant CLI application.
 * This application allows a user to chat with an assistant until they type 'exit'.
 */
public class ChatAssistant {

    public static void main(String[] args) {
        ChatAssistant assistant = new ChatAssistant();
        assistant.startChat();
    }

    /**
     * Starts the chat session with the assistant.
     * Continuously reads user input and generates assistant responses until 'exit' is input.
     */
    public void startChat() {
        Scanner scanner = new Scanner(System.in);
        String userInput;

        System.out.println("Welcome to ChatAssistant! Type 'exit' to end the chat.");

        while (true) {
            System.out.print("You: ");
            userInput = readUserInput(scanner);

            // Exit condition
            if ("exit".equalsIgnoreCase(userInput)) {
                System.out.println("ChatAssistant: Goodbye!");
                break;
            }

            // Generate and print assistant response
            String response = generateAssistantResponse(userInput);
            System.out.println("ChatAssistant: " + response);
        }
    }

    /**
     * Reads user input from the command line.
     * Validates to ensure the input is not empty.
     *
     * @param scanner Scanner object to read input from the command line.
     * @return Validated user input string.
     */
    private String readUserInput(Scanner scanner) {
        String input = "";
        while (true) {
            input = scanner.nextLine().trim();
            if (input.isEmpty()) {
                System.out.println("Error: Input cannot be empty. Please enter a valid message.");
                System.out.print("You: ");
            } else {
                break;
            }
        }
        return input;
    }

    /**
     * Generates a simulated response from the assistant based on the user input.
     *
     * @param userInput Input string from the user.
     * @return Response string from the assistant.
     */
    private String generateAssistantResponse(String userInput) {
        // Simple simulation of assistant responses with some placeholder logic
        if (userInput.equalsIgnoreCase("hi") || userInput.equalsIgnoreCase("hello")) {
            return "Hello! How can I assist you today?";
        } else if (userInput.equalsIgnoreCase("how are you")) {
            return "I'm just a program, but I'm here to help you!";
        } else {
            return "Tell me more...";
        }
    }
}

### Summary of Enhancements:
- **Documentation:** Added Javadoc comments for all methods and a class-level comment.
- **Error Handling:** Replaced recursion with a loop in `readUserInput` for better error handling.
- **Validation:** Ensured universal whitespace trimming in user input validation.

With these enhancements, the code now adheres better to idiomatic Java practices, is fully documented, and includes improved error handling.

CodeProgrammerAgent: starting the task with input: Implement any feedback provided by the CodeInspectionAgent to improve the Java CLI application.

CodeProgrammerAgent: working on the task...................
Below is the improved Java CLI application based on the feedback provided by the CodeInspectionAgent:

### ChatAssistant.java

import java.util.Scanner;

/**
 * Main class for the ChatAssistant CLI application.
 * This application allows a user to chat with an assistant until they type 'exit'.
 */
public class ChatAssistant {

    public static void main(String[] args) {
        ChatAssistant assistant = new ChatAssistant();
        assistant.startChat();
    }

    /**
     * Starts the chat session with the assistant.
     * Continuously reads user input and generates assistant responses until 'exit' is input.
     */
    public void startChat() {
        Scanner scanner = new Scanner(System.in);
        String userInput;

        System.out.println("Welcome to ChatAssistant! Type 'exit' to end the chat.");

        while (true) {
            System.out.print("You: ");
            userInput = readUserInput(scanner);

            // Exit condition
            if ("exit".equalsIgnoreCase(userInput)) {
                System.out.println("ChatAssistant: Goodbye!");
                break;
            }

            // Generate and print assistant response
            String response = generateAssistantResponse(userInput);
            System.out.println("ChatAssistant: " + response);
        }

        // Close the scanner when done
        scanner.close();
    }

    /**
     * Reads user input from the command line.
     * Validates to ensure the input is not empty.
     *
     * @param scanner Scanner object to read input from the command line.
     * @return Validated user input string.
     */
    private String readUserInput(Scanner scanner) {
        String input = "";
        while (true) {
            input = scanner.nextLine().trim();
            if (input.isEmpty()) {
                System.out.println("Error: Input cannot be empty. Please enter a valid message.");
                System.out.print("You: ");
            } else {
                break;
            }
        }
        return input;
    }

    /**
     * Generates a simulated response from the assistant based on the user input.
     *
     * @param userInput Input string from the user.
     * @return Response string from the assistant.
     */
    private String generateAssistantResponse(String userInput) {
        // Simple simulation of assistant responses with some placeholder logic
        if (userInput.equalsIgnoreCase("hi") || userInput.equalsIgnoreCase("hello")) {
            return "Hello! How can I assist you today?";
        } else if (userInput.equalsIgnoreCase("how are you")) {
            return "I'm just a program, but I'm here to help you!";
        } else {
            return "Tell me more...";
        }
    }
}

### Summary of Improvements:
1. **Documentation**: Added Javadoc comments for all methods and a class-level comment to improve understanding and maintainability.
2. **Error Handling**: Replaced recursion in the error handling of `readUserInput` with a while loop to prevent potential stack overflow.
3. **Validation**: Ensured universal whitespace trimming in user input validation.
4. **Resource Management**: Closed the `Scanner` object at the end of the `startChat` method to prevent resource leaks.

### How to Run
1. Save the code to a file named `ChatAssistant.java`.
2. Open a terminal or command prompt.
3. Navigate to the directory containing `ChatAssistant.java`.
4. Compile the program: `javac ChatAssistant.java`.
5. Run the program: `java ChatAssistant`.

You can now interact with the assistant, and the chat will continue until you type 'exit'. The updated application adheres to idiomatic Java programming styles, industry best practices, and includes comprehensive documentation and error handling.

FileCreatorAgent: starting the task

FileCreatorAgent: Function call create_file_with_specified_content with arguments {"file_name": "ChatAssistant.java", "output_directory": "output", "content": "import java.util.Scanner;\n\n/**\n * Main class for the ChatAssistant CLI application.\n * This application allows a user to chat with an assistant until they type 'exit'.\n */\npublic class ChatAssistant {\n\n    public static void main(String[] args) {\n        ChatAssistant assistant = new ChatAssistant();\n        assistant.startChat();\n    }\n\n    /**\n     * Starts the chat session with the assistant.\n     * Continuously reads user input and generates assistant responses until 'exit' is input.\n     */\n    public void startChat() {\n        Scanner scanner = new Scanner(System.in);\n        String userInput;\n        \n        System.out.println(\"Welcome to ChatAssistant! Type 'exit' to end the chat.\");\n\n        while (true) {\n            System.out.print(\"You: \");\n            userInput = readUserInput(scanner);\n            \n            // Exit condition\n            if (\"exit\".equalsIgnoreCase(userInput)) {\n                System.out.println(\"ChatAssistant: Goodbye!\");\n                break;\n            }\n\n            // Generate and print assistant response\n            String response = generateAssistantResponse(userInput);\n            System.out.println(\"ChatAssistant: \" + response);\n        }\n\n        // Close the scanner when done\n        scanner.close();\n    }\n\n    /**\n     * Reads user input from the command line.\n     * Validates to ensure the input is not empty.\n     *\n     * @param scanner Scanner object to read input from the command line.\n     * @return Validated user input string.\n     */\n    private String readUserInput(Scanner scanner) {\n        String input = \"\";\n        while (true) {\n            input = scanner.nextLine().trim();\n            if (input.isEmpty()) {\n                System.out.println(\"Error: Input cannot be empty. Please enter a valid message.\");\n                System.out.print(\"You: \");\n            } else {\n                break;\n            }\n        }\n        return input;\n    }\n\n    /**\n     * Generates a simulated response from the assistant based on the user input.\n     *\n     * @param userInput Input string from the user.\n     * @return Response string from the assistant.\n     */\n    private String generateAssistantResponse(String userInput) {\n        // Simple simulation of assistant responses with some placeholder logic\n        if (userInput.equalsIgnoreCase(\"hi\") || userInput.equalsIgnoreCase(\"hello\")) {\n            return \"Hello! How can I assist you today?\";\n        } else if (userInput.equalsIgnoreCase(\"how are you\")) {\n            return \"I'm just a program, but I'm here to help you!\";\n        } else {\n            return \"Tell me more...\";\n        }\n    }\n}", "file_extension": "java"}, result OK.
FileCreatorAgent: The file `ChatAssistant.java` has been created successfully and saved in the `output` directory.

You can find the file at the following path: `output/ChatAssistant.java`.

Follow the instructions provided to compile and run the program. If you need any further assistance, feel free to ask!

Task 754bd369-eda4-4e33-b9b7-026dacad0726 completed with schedule ID: 4de8812e-85f3-4df3-869a-c859c117496f. Result: Success
```

[Prerequisities]: ../../README.md