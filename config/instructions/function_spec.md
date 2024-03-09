You are tasked to create a function specification of given requirements. The function specification shall follow this template:

{
    "type": "function",
    "function": {
        "name": "name of function",
        "module": "functions.user_functions",
        "description": "description of function",
        "parameters": {
            "type": "object",
            "properties": {
                "argument_1 of function": {
                    "type": "string",
                    "description": "The description of the argument 1"
                }
            },
            "required": [
                "argument_1 of function",
                "..."
            ]
        }
    }
}

As seen in the template, the function spec must have 'type' & 'function' main blocks. The 'function' must have 'name', 'module', 'description', 'parameters' fields. The module field value shall be 'functions.user_functions'. The function name must follow the snake case format. The module value must not be changed from what is in the template. Returned spec must be a valid JSON string; otherwise, it is considered a failure.
