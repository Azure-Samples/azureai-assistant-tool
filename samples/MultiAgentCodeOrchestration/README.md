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
user: hello

TaskPlannerAgent: Hello! How can I assist you with your software development tasks today? If you have any specific requests or need guidance, feel free to let me know!

user: create basic CLI program in Java for chat between user and assistant

TaskPlannerAgent: To create a basic Command Line Interface (CLI) program in Java for a chat between a user and an assistant, we'll need to follow these steps:

1. Set up the Java project structure with the necessary classes.
2. Implement a main class that will handle the CLI input and output.
3. Create a method to process user input and generate responses from the assistant.
4. Implement a loop to allow continuous conversation until the user decides to exit.
5. Ensure proper error handling and user experience considerations.

Here's a plan to accomplish this task:

[
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Create a Java CLI application that allows a user to chat with an assistant. The application should include a main class with a method to handle user input and output, a loop for continuous conversation, and proper error handling. The conversation should continue until the user types 'exit'. Please save the Java file in the 'output' folder and inform the user about the file path once completed."
    },
    {
        "assistant": "CodeInspectionAgent",
        "task": "Review the Java CLI application code created by CodeProgrammerAgent for chat functionality. Ensure the code is idiomatic, follows best practices, and includes adequate documentation and error handling. Provide feedback for any necessary improvements."
    },
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Implement the improvements suggested by CodeInspectionAgent in the Java CLI chat application. Ensure all feedback is addressed and the application is functioning as expected. Update the file in the 'output' folder and inform the user about the updated file path."
    }
]

Before we proceed with this plan, could you please confirm if this aligns with your expectations?
user: yes, looks good

TaskPlannerAgent: Great! Here's the plan based on your confirmation:

[
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Create a Java CLI application that allows a user to chat with an assistant. The application should include a main class with a method to handle user input and output, a loop for continuous conversation, and proper error handling. The conversation should continue until the user types 'exit'. Please save the Java file in the 'output' folder and inform the user about the file path once completed."
    },
    {
        "assistant": "CodeInspectionAgent",
        "task": "Review the Java CLI application code created by CodeProgrammerAgent for chat functionality. Ensure the code is idiomatic, follows best practices, and includes adequate documentation and error handling. Provide feedback for any necessary improvements."
    },
    {
        "assistant": "CodeProgrammerAgent",
        "task": "Implement the improvements suggested by CodeInspectionAgent in the Java CLI chat application. Ensure all feedback is addressed and the application is functioning as expected. Update the file in the 'output' folder and inform the user about the updated file path."
    }
]

The assistants will now begin working on the tasks as outlined. You will be informed about the progress and the output file path once the tasks are completed.

Task d6c7f964-110c-417a-9e1c-d27f675b3728 started with schedule ID: 8e1ac77b-ca51-400d-8ca6-03954e500067

Task d6c7f964-110c-417a-9e1c-d27f675b3728 execute with schedule ID: 8e1ac77b-ca51-400d-8ca6-03954e500067

CodeProgrammerAgent: working on the task..............................
CodeProgrammerAgent: To create the Java CLI application that enables a user to chat with an assistant, we need to build a simple command-line program with a main class that includes a method for handling user input and output. The application will run a loop that facilitates continuous conversation until the user decides to terminate it by typing 'exit'. Additionally, the program should handle potential input errors gracefully.

Below are the steps and the Java code that meets the specified requirements:

1. Define a `ChatAssistant` class with a `main` method.
2. Inside the `main` method, implement a loop to handle the continuous conversation.
3. Use `Scanner` class to read user input from the terminal.
4. Handle user input and provide responses accordingly.
5. Include error handling and an option to exit the loop.
6. Save the file in the 'output' directory.
7. Notify the user about the file path once the code is written.

Here is the code for the `ChatAssistant.java` class:

import java.util.Scanner;

public class ChatAssistant {

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        System.out.println("Welcome to the Chat Assistant. Type 'exit' to end the conversation.");

        while(true) {
            try {
                System.out.print("You: ");
                String userInput = scanner.nextLine();

                if("exit".equalsIgnoreCase(userInput)) {
                    System.out.println("Assistant: Goodbye!");
                    break;
                }

                // Handle the user input here. For simplicity, we'll echo the user input.
                // This could be replaced with more sophisticated response logic.
                String response = "Assistant: You said '" + userInput + "'";
                System.out.println(response);

            } catch (Exception e) {
                System.err.println("Error handling the input: " + e.getMessage());
            }
        }
        scanner.close();
    }
}

Now, I will save the above Java class in a file named `ChatAssistant.java` inside the directory `output`. Since my capabilities do not allow me to perform file operations directly, I will provide the instructions to guide you on how to save this code.

Assuming you have a Java development environment set up, here's what you would do:

1. Open your preferred text editor or Integrated Development Environment (IDE).
2. Copy the provided Java class code.
3. Paste the code into a new file.
4. Save the file as `ChatAssistant.java` inside a folder named `output` that you've created in a directory of your choice.

After saving the file, you would compile and run the Java program like this:

javac output/ChatAssistant.java
java -cp output ChatAssistant

Once the file is saved and the program is running, you can have a text-based conversation with the assistant in your terminal. To exit the conversation, simply type 'exit' when prompted for input.

The path to the saved Java file for the user will depend on where you have your `output` directory. For example, if you have the `output` folder on your desktop, the path would be something like:

C:\Users\YourUsername\Desktop\output\ChatAssistant.java

Replace `YourUsername` with your actual username, and ensure the path matches your file system's structure.

CodeInspectionAgent: working on the task........................................
CodeInspectionAgent: The Java CLI application code provided for the chat functionality is a good start, but there are a number of enhancements and best practices that can be applied to improve its idiomatic nature, robustness, and documentation.

Let's go through the feedback for improvements:

1. Use Try-with-Resources:
Instead of manually closing the `Scanner`, use the try-with-resources statement. This ensures that the resource is closed automatically after use and also handles exceptions gracefully.

2. Documentation:
Add a class-level Javadoc comment explaining the purpose of the `ChatAssistant` class and a method-level Javadoc for `main`.

3. Error Handling:
While there is a basic error handling mechanism, it would be more idiomatic to separate business logic from exception handling.

4. Response Logic Placeholder:
It would be helpful to include a placeholder method for future response generation logic, which separates the concerns and makes the code more maintainable.

5. User Prompt:
Consider extracting the user prompt into a separate method for better structure and potentially to support localization in the future.

Here's the improved Java code:

import java.util.Scanner;

/**
 * ChatAssistant is a command-line application that enables users to have a text-based
 * conversation with an assistant. The conversation continues until the user types 'exit'.
 */
public class ChatAssistant {

    /**
     * The starting point of the chat application.
     *
     * @param args Command line arguments (not used).
     */
    public static void main(String[] args) {
        // Using try-with-resources to ensure the scanner is closed automatically
        try (Scanner scanner = new Scanner(System.in)) {
            System.out.println("Welcome to the Chat Assistant. Type 'exit' to end the conversation.");

            while (true) {
                String userInput = promptUserInput(scanner);

                if ("exit".equalsIgnoreCase(userInput)) {
                    System.out.println("Assistant: Goodbye!");
                    break;
                }

                // Placeholder for future sophisticated response logic
                String response = generateResponse(userInput);
                System.out.println(response);
            }
        } catch (Exception e) {
            System.err.println("An unexpected error occurred: " + e.getMessage());
        }
    }

    /**
     * Prompts the user for input and returns the user's input as a string.
     *
     * @param scanner The scanner object to read the input.
     * @return The user's input as a string.
     */
    private static String promptUserInput(Scanner scanner) {
        System.out.print("You: ");
        return scanner.nextLine();
    }

    /**
     * Generates a response based on user input. Currently, it echoes back the input.
     *
     * @param userInput The input provided by the user.
     * @return A string response to be displayed to the user.
     */
    private static String generateResponse(String userInput) {
        // Logic for generating a response can be implemented here
        return "Assistant: You said '" + userInput + "'";
    }
}

These changes provide better error handling, code structure, readability, and maintainability. The new methods `promptUserInput` and `generateResponse` improve separation of concerns and allow for easier updates to the input prompting and response logic respectively.

Please remember that the above code is an improved version, but for an actual chat functionality, you'd likely integrate with a back-end service or AI platform that processes the user input and generates meaningful responses. This is simply a skeleton to be fleshed out according to the actual requirements of the chat functionality.

CodeProgrammerAgent: working on the task.....................................................
CodeProgrammerAgent: Let's apply the suggested improvements to the Java CLI chat application. This involves:

1. Adding try-with-resources for the `Scanner`.
2. Documenting the code with Javadoc comments.
3. Extracting user input prompt and response generation into separate methods.
4. Providing clearer error handling.

The updated Java class `ChatAssistant` will now look like this:

import java.util.Scanner;

/**
 * The ChatAssistant class represents a command-line interface application that
 * facilitates a text-based conversation with an assistant. The user can interact
 * with the assistant until the command 'exit' is entered.
 */
public class ChatAssistant {

    /**
     * Main method that serves as the entry point of the application.
     * It initializes a conversation loop that continues until the user exits.
     *
     * @param args Command line arguments (not currently used).
     */
    public static void main(String[] args) {
        System.out.println("Welcome to the Chat Assistant. Type 'exit' to end the conversation.");

        // Use try-with-resources to ensure the Scanner is closed properly
        try (Scanner scanner = new Scanner(System.in)) {
            while (true) {
                String userInput = promptUserInput(scanner);

                if ("exit".equalsIgnoreCase(userInput)) {
                    System.out.println("Assistant: Goodbye!");
                    break;
                }

                String response = generateResponse(userInput);
                System.out.println(response);
            }
        } catch (Exception e) {
            System.err.println("An unexpected error occurred: " + e.getMessage());
        }
    }

    /**
     * Prompts the user for their input and reads the next line from the console.
     *
     * @param scanner A Scanner object for reading user input.
     * @return The user input as a string.
     */
    private static String promptUserInput(Scanner scanner) {
        System.out.print("You: ");
        return scanner.nextLine();
    }

    /**
     * Generates a response to the user input. In this template, it simply echoes the input.
     * This method can be expanded with more complex logic in the future.
     *
     * @param userInput The user's input string.
     * @return A response string to be displayed to the user.
     */
    private static String generateResponse(String userInput) {
        return "Assistant: You said '" + userInput + "'";
    }
}

To save this as a Java file, you would need to create a file named `ChatAssistant.java` in the `output` folder manually, as I don't have the capability to interact with the file system directly. Follow these steps:

1. Open a text editor or an IDE on your computer.
2. Copy the updated code from above.
3. Paste the code into the editor.
4. Save the file with the name `ChatAssistant.java` in an `output` directory that you have created.

For example, if you placed the 'output' folder on your desktop, you would save the file at the following path (assuming you're using Windows):

C:\Users\YourUsername\Desktop\output\ChatAssistant.java

Once saved, compile and run the Java program as before:

javac output/ChatAssistant.java
java -cp output ChatAssistant

Remember to replace `YourUsername` with your actual user name. Adjust the path accordingly if your `output` folder is located elsewhere. The path is relative to where you've chosen to store it.

Task d6c7f964-110c-417a-9e1c-d27f675b3728 completed with schedule ID: 8e1ac77b-ca51-400d-8ca6-03954e500067. Result: Success

user: exit
Exiting chat.
```

[Prerequisities]: ../../README.md