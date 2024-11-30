import subprocess
import inspect
from functools import wraps
from typing import Optional, Union, get_origin, get_args, List, Callable
from .sandbox import Sandbox


def tool(func):
    """Decorator that adds a schema method to a function and validates sandbox parameter"""
    # Validate that first parameter is sandbox: Sandbox
    sig = inspect.signature(func)
    params = list(sig.parameters.items())
    if not params or params[0][0] != "sandbox":
        raise ValueError(f"First parameter of {func.__name__} must be 'sandbox'")

    type_hints = inspect.get_annotations(func)
    if type_hints.get("sandbox") != Sandbox:
        raise ValueError(
            f"First parameter of {func.__name__} must be annotated with 'Sandbox' type"
        )

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    def schema():
        # Parse the docstring to get description and param docs
        docstring = inspect.getdoc(func)
        if docstring:
            # Split into description and param sections
            parts = docstring.split("\n\nArgs:")
            description = parts[0].strip()

            param_docs = {}
            if len(parts) > 1:
                param_section = parts[1].strip()
                # Parse each parameter description
                for line in param_section.split("\n"):
                    line = line.strip()
                    if line and ":" in line:
                        param_name, param_desc = line.split(":", 1)
                        param_docs[param_name.strip()] = param_desc.strip()
        else:
            description = ""
            param_docs = {}

        # Get type hints
        type_hints = inspect.get_annotations(func)

        # Create schema
        schema = {
            "name": func.__name__,
            "description": description,
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }

        # Process parameters
        sig = inspect.signature(func)
        for param_name, param in sig.parameters.items():
            if param_name == "sandbox":  # Skip sandbox parameter
                continue

            # Check if parameter is optional
            type_hint = type_hints.get(param_name)
            is_optional = False
            if type_hint is not None:
                origin = get_origin(type_hint)
                if origin is Union:
                    args = get_args(type_hint)
                    is_optional = type(None) in args

            if not is_optional:
                schema["input_schema"]["required"].append(param_name)

            # Get parameter description from docstring
            param_desc = param_docs.get(param_name, "")

            # Add to properties
            schema["input_schema"]["properties"][param_name] = {
                "type": "string",  # Default to string, could be enhanced to detect other types
                "description": param_desc,
            }

        return schema

    wrapper.schema = schema
    return wrapper


@tool
def run_bash_command(sandbox: Sandbox, command: str):
    """Run a bash command in a sandboxed environment with safety checks.

    Args:
        command: The bash command to execute
    """
    try:
        # Check for potentially dangerous commands
        dangerous_commands = [
            r"\brm\b",
            r"\bmv\b",
            r"\bcp\b",
            r"\bchmod\b",
            r"\bchown\b",
            r"\bsudo\b",
            r">",
            r">>",
        ]
        import re

        if any(re.search(cmd, command) for cmd in dangerous_commands):
            return "Error: This command is not allowed for safety reasons."

        if not sandbox.check_permissions("shell", command):
            return "Error: Operator denied permission."

        # Run the command and capture output
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=10
        )

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


@tool
def read_file(sandbox: Sandbox, path: str):
    """Read and return the contents of a file from the sandbox.

    Args:
        path: Path to the file to read
    """
    try:
        return sandbox.read_file(path)
    except PermissionError:
        return f"Error: No read permission for {path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def write_file(sandbox: Sandbox, path: str, content: str):
    """Write content to a file in the sandbox.

    Args:
        path: Path where the file should be written
        content: Content to write to the file
    """
    try:
        sandbox.write_file(path, content)
        return "File written successfully"
    except PermissionError:
        return f"Error: No write permission for {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
def list_directory(sandbox: Sandbox, path: str, recursive: Optional[bool] = None):
    """List contents of a directory in the sandbox.

    Args:
        path: Path to the directory to list
        recursive: If True, list contents recursively (optional)
    """
    try:
        contents = sandbox.get_directory_listing(
            path, recursive=bool(recursive) if recursive is not None else False
        )

        result = f"Contents of {path}:\n"
        for item in contents:
            result += f"{item}\n"
        return result
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool
def edit_file(sandbox: Sandbox, path: str, match_text: str, replace_text: str):
    """Make a targeted edit to a file in the sandbox by replacing specific text.

    Args:
        path: Path to the file to edit
        match_text: Text to find in the file
        replace_text: Text to replace the matched text with
    """
    try:
        content = sandbox.read_file(path)

        # Check if the match_text is unique
        if content.count(match_text) > 1:
            return "Error: The text to match is not unique in the file."
        elif content.count(match_text) == 0:
            # If match_text is not found, append replace_text to the end of the file
            new_content = content + "\n" + replace_text
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


# List of all available tools
ALL_TOOLS = [read_file, write_file, list_directory, run_bash_command, edit_file]


def invoke_tool(sandbox: Sandbox, tool_use, tools: List[Callable] = ALL_TOOLS):
    """Invoke a tool based on the tool_use specification.

    Args:
        sandbox: The sandbox environment
        tool_use: The tool use specification containing name, input, and id
        tools: List of tool functions to use. Defaults to ALL_TOOLS.
    """
    function_name = tool_use.name
    arguments = tool_use.input

    # Create a mapping of tool names to functions
    tool_map = {func.__name__: func for func in tools}

    # Look up the tool function
    tool_func = tool_map.get(function_name)
    if tool_func is None:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": f"Unknown function: {function_name}",
        }

    # Call the tool function with the sandbox and arguments
    result = tool_func(sandbox, **arguments)

    return {"type": "tool_result", "tool_use_id": tool_use.id, "content": result}
