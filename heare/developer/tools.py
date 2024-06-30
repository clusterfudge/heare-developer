import os
import shlex
import subprocess
import re


def run_bash_command(command):
    try:
        # Split the command string into a list of arguments
        args = shlex.split(command)

        # Check for potentially dangerous commands
        dangerous_commands = ['rm', 'mv', 'cp', 'chmod', 'chown', 'sudo', '>', '>>', '|']
        if any(cmd in args for cmd in dangerous_commands):
            return "Error: This command is not allowed for safety reasons."

        # Run the command and capture output
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)

        # Prepare the output
        output = f"Exit code: {result.returncode}\n"
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"

        return output
    except subprocess.TimeoutExpired:
        return "Error: Command execution timed out"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def read_file(path):
    try:
        with open(path, 'r') as file:
            return file.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def write_file(path, content):
    try:
        with open(path, 'w') as file:
            file.write(content)
        return "File written successfully"
    except Exception as e:
        return f"Error writing file: {str(e)}"


def list_directory(path):
    try:
        return os.listdir(path)
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def edit_file(path, match_text, replace_text):
    try:
        with open(path, 'r') as file:
            content = file.read()

        # Check if the match_text is unique
        if content.count(match_text) > 1:
            return "Error: The text to match is not unique in the file."
        elif content.count(match_text) == 0:
            # If match_text is not found, append replace_text to the end of the file
            with open(path, 'a') as file:
                file.write('\n' + replace_text)
            return "Text not found. Content added to the end of the file."
        else:
            # Replace the matched text
            new_content = content.replace(match_text, replace_text, 1)
            with open(path, 'w') as file:
                file.write(new_content)
            return "File edited successfully"
    except Exception as e:
        return f"Error editing file: {str(e)}"


TOOLS_SCHEMA = [
    {
        "name": "read_file",
        "description": "Read the contents of a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the directory"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "run_bash_command",
        "description": "Run a bash command",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash command to execute"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "edit_file",
        "description": "Make a targeted edit to a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "match_text": {"type": "string", "description": "Text to match"},
                "replace_text": {"type": "string", "description": "Text to replace the matched text with"}
            },
            "required": ["path", "match_text", "replace_text"]
        }
    }
]


def handle_tool_use(final_message):
    tool_use = next(block for block in final_message.content if block.type == "tool_use")
    function_name = tool_use.name
    arguments = tool_use.input
    if function_name == "read_file":
        result = read_file(arguments['path'])
    elif function_name == "write_file":
        result = write_file(arguments['path'], arguments['content'])
    elif function_name == "list_directory":
        result = list_directory(arguments['path'])
    elif function_name == "run_bash_command":
        result = run_bash_command(arguments['command'])
    elif function_name == "edit_file":
        result = edit_file(arguments['path'], arguments['match_text'], arguments['replace_text'])
    else:
        result = f"Unknown function: {function_name}"
    return result, tool_use
