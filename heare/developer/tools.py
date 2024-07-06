import os
import shlex
import subprocess
import re
from enum import Flag, auto
from .sandbox import Permission


def run_bash_command(sandbox, command):
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


def read_file(sandbox, path):
    try:
        return sandbox.read_file(path)
    except PermissionError:
        return f"Error: No read permission for {path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


def write_file(sandbox, path, content):
    try:
        sandbox.write_file(path, content)
        return "File written successfully"
    except PermissionError:
        return f"Error: No write permission for {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


def list_directory(sandbox, path):
    try:
        contents = sandbox.list_sandbox()
        relevant_contents = [
            (p, perms) for p, perms in contents
            if p.startswith(path) and p != path
        ]
        if not relevant_contents:
            return f"No contents found for path: {path}"

        result = f"Contents of {path}:\n"
        for item_path, item_perms in relevant_contents:
            relative_path = os.path.relpath(item_path, path)
            perms_str = ', '.join([p.name for p in Permission if p in item_perms and p != Permission.NONE])
            result += f"{relative_path}: {perms_str}\n"
        return result
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def edit_file(sandbox, path, match_text, replace_text):
    try:
        content = sandbox.read_file(path)

        # Check if the match_text is unique
        if content.count(match_text) > 1:
            return "Error: The text to match is not unique in the file."
        elif content.count(match_text) == 0:
            # If match_text is not found, append replace_text to the end of the file
            new_content = content + '\n' + replace_text
            sandbox.write_file(path, new_content)
            return "Text not found. Content added to the end of the file."
        else:
            # Replace the matched text
            new_content = content.replace(match_text, replace_text, 1)
            sandbox.write_file(path, new_content)
            return "File edited successfully"
    except PermissionError:
        return f"Error: No read or write permission for {path}"
    except Exception as e:
        return f"Error editing file: {str(e)}"


def request_permission(sandbox, path, permission):
    try:
        # Convert string permission to Permission enum
        perm = Permission[permission.upper()]

        # Prompt the user for approval
        user_input = input(f"Permission request: {permission} for path {path}. Approve? (y/n): ").lower().strip()

        if user_input == 'y':
            sandbox.grant_permission(path, perm)
            return f"Permission {permission} granted for {path}"
        else:
            return f"Permission {permission} denied for {path}"
    except KeyError:
        return f"Error: Invalid permission '{permission}'. Valid permissions are LIST, READ, WRITE."
    except Exception as e:
        return f"Error processing permission request: {str(e)}"


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
    },
    {
        "name": "request_permission",
        "description": "Request a specific permission for a path (requires user approval via command line). Permissions are list by default, and recursive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to request permission for"},
                "permission": {"type": "string", "description": "Permission to request (LIST, READ, or WRITE)"}
            },
            "required": ["path", "permission"]
        }
    }
]


def handle_tool_use(sandbox, final_message):
    results = []
    for tool_use in [block for block in final_message.content if block.type == "tool_use"]:
        function_name = tool_use.name
        arguments = tool_use.input
        if function_name == "read_file":
            result = read_file(sandbox, arguments['path'])
        elif function_name == "write_file":
            result = write_file(sandbox, arguments['path'], arguments['content'])
        elif function_name == "list_directory":
            result = list_directory(sandbox, arguments['path'])
        elif function_name == "run_bash_command":
            result = run_bash_command(sandbox, arguments['command'])
        elif function_name == "edit_file":
            result = edit_file(sandbox, arguments['path'], arguments['match_text'], arguments['replace_text'])
        elif function_name == "request_permission":
            result = request_permission(sandbox, arguments['path'], arguments['permission'])
        else:
            result = f"Unknown function: {function_name}"
        results.append({
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": result
        })
    return results
