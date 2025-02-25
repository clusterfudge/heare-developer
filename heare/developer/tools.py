import contextlib
import subprocess
import inspect
from functools import wraps
from typing import Optional, Union, get_origin, get_args, List, Callable

from rich.status import Status

from .context import AgentContext
from .user_interface import UserInterface


def tool(func):
    """Decorator that adds a schema method to a function and validates sandbox parameter"""
    # Validate that first parameter is context: AgentContext
    sig = inspect.signature(func)
    params = list(sig.parameters.items())
    if not params or params[0][0] != "context":
        raise ValueError(f"First parameter of {func.__name__} must be 'context'")

    type_hints = inspect.get_annotations(func)
    if type_hints.get("context") != "AgentContext":
        raise ValueError(
            f"First parameter of {func.__name__} must be annotated with 'AgentContext' type"
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
            if param_name == "context":  # Skip context parameter
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
def run_bash_command(context: "AgentContext", command: str):
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
            r"\bchown\b",
            r"\bsudo\b",
            r">",
            r">>",
        ]
        import re

        if any(re.search(cmd, command) for cmd in dangerous_commands):
            return "Error: This command is not allowed for safety reasons."

        if not context.sandbox.check_permissions("shell", command):
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
def read_file(context: "AgentContext", path: str):
    """Read and return the contents of a file from the sandbox.

    Args:
        path: Path to the file to read
    """
    try:
        return context.sandbox.read_file(path)
    except PermissionError:
        return f"Error: No read permission for {path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def write_file(context: "AgentContext", path: str, content: str):
    """Write content to a file in the sandbox.

    Args:
        path: Path where the file should be written
        content: Content to write to the file
    """
    try:
        context.sandbox.write_file(path, content)
        return "File written successfully"
    except PermissionError:
        return f"Error: No write permission for {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
def list_directory(
    context: "AgentContext", path: str, recursive: Optional[bool] = None
):
    """List contents of a directory in the sandbox.

    Args:
        path: Path to the directory to list
        recursive: If True, list contents recursively (optional)
    """
    try:
        contents = context.sandbox.get_directory_listing(
            path, recursive=bool(recursive) if recursive is not None else False
        )

        result = f"Contents of {path}:\n"
        for item in contents:
            result += f"{item}\n"
        return result
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool
def edit_file(context: "AgentContext", path: str, match_text: str, replace_text: str):
    """Make a targeted edit to a file in the sandbox by replacing specific text.

    Args:
        path: Path to the file to edit
        match_text: Text to find in the file
        replace_text: Text to replace the matched text with
    """
    try:
        content = context.sandbox.read_file(path)

        # Check if the match_text is unique
        if content.count(match_text) > 1:
            return "Error: The text to match is not unique in the file."
        elif content.count(match_text) == 0:
            # If match_text is not found, append replace_text to the end of the file
            new_content = content + "\n" + replace_text
            context.sandbox.write_file(path, new_content)
            return "Text not found. Content added to the end of the file."
        else:
            # Replace the matched text
            new_content = content.replace(match_text, replace_text, 1)
            context.sandbox.write_file(path, new_content)
            return "File edited successfully"
    except PermissionError:
        return f"Error: No read or write permission for {path}"
    except Exception as e:
        return f"Error editing file: {str(e)}"


@tool
def web_search(context: "AgentContext", search_query: str) -> str:
    """Perform a web search using Brave Search API.

    Args:
        search_query: The search query to send to Brave Search
    """
    import os
    import asyncio
    from brave_search_python_client import BraveSearch, WebSearchRequest

    # Try to get API key from environment first
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")

    # If not in environment, try to read from ~/.brave-search-api-key
    if not api_key:
        try:
            key_path = os.path.expanduser("~/.brave-search-api-key")
            if os.path.exists(key_path):
                with open(key_path, "r") as f:
                    api_key = f.read().strip()
        except Exception:
            pass

    if not api_key:
        return "Error: BRAVE_SEARCH_API_KEY not found in environment or ~/.brave-search-api-key"

    try:
        # Initialize Brave Search client
        bs = BraveSearch(api_key=api_key)

        # Create event loop and run the async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(bs.web(WebSearchRequest(q=search_query)))
        loop.close()

        # Format results
        results = []
        if response.web and response.web.results:
            for result in response.web.results:
                results.append(f"Title: {result.title}")
                results.append(f"URL: {result.url}")
                if result.description:
                    results.append(f"Description: {result.description}")
                results.append("---")

            return "\n".join(results)
        else:
            return "No results found"

    except Exception as e:
        return f"Error performing web search: {str(e)}"


# Create a minimal UI that captures output as string
class CaptureInterface(UserInterface):
    def get_user_input(self, prompt: str = "") -> str:
        pass

    def display_welcome_message(self) -> None:
        pass

    def status(
        self, message: str, spinner: str = None, update=False
    ) -> contextlib.AbstractContextManager:
        if update:
            self._status.update(message, spinner=spinner or "aesthetic")
        return self._status

    def __init__(self, parent: UserInterface, status: Status) -> None:
        self.output = []
        self.parent = parent
        self._status = status

    def handle_system_message(self, message):
        self.output.append(message)

    def handle_user_input(self, message):
        self.output.append(message)

    def handle_assistant_message(self, message):
        self.output.append(message)

    def handle_tool_use(self, tool_name, tool_input):
        message = f"Using tool {tool_name} with input {tool_input}"
        self.status(message, update=True)
        self.output.append(message)

    def handle_tool_result(self, tool_name, result):
        self.output.append(f"Tool {tool_name} result: {result}")

    def display_token_count(
        self, prompt_tokens, completion_tokens, total_tokens, total_cost
    ):
        pass

    def permission_callback(self, operation, path, sandbox_mode, action_arguments):
        return True

    def permission_rendering_callback(self, operation, path, action_arguments):
        return True


@tool
def agent(context: "AgentContext", prompt: str, tool_names: List[str]):
    """Run a prompt through a sub-agent with a limited set of tools.
    Use an agent when you believe that the action desired will require multiple steps, but you do not
    believe the details of the intermediate steps are important -- only the result.
    The sub-agent will take multiple turns and respond with a result to the query.
    When selecting this tool, the model should choose a list of tools (by tool name)
    that is the likely minimal set necessary to achieve the agent's goal.
    Do not assume that the user can see the response of the agent, and summarize it for them.
    Do not indicate in your response that you used a sub-agent, simply present the results.

    Args:
        prompt: the initial prompt question to ask the
        tool_names: a list of tool names from the existing tools to provide to the sub-agent. this should be a subset!
    """
    from .agent import run

    with context.user_interface.status(f"Initiating sub-agent: {prompt}") as status:
        ui = CaptureInterface(parent=context.user_interface, status=status)

        # Run the agent with single response mode
        chat_history = run(
            agent_context=context.with_user_interface(ui),
            initial_prompt=prompt,
            single_response=True,
            tool_names=tool_names,
        )

        # Get the final assistant message from chat history
        for message in reversed(chat_history):
            if message["role"] == "assistant":
                # Handle both string and list content formats
                if isinstance(message["content"], str):
                    return message["content"]
                elif isinstance(message["content"], list):
                    # Concatenate all text blocks
                    return "".join(
                        block.text
                        for block in message["content"]
                        if hasattr(block, "text")
                    )

        return "No response generated"


# List of all available tools
ALL_TOOLS = [
    read_file,
    write_file,
    list_directory,
    run_bash_command,
    edit_file,
    web_search,
    agent,
]


def invoke_tool(context: "AgentContext", tool_use, tools: List[Callable] = None):
    """Invoke a tool based on the tool_use specification.

    Args:
        context: The agent's context
        tool_use: The tool use specification containing name, input, and id
        tools: List of tool functions to use. Defaults to ALL_TOOLS.
    """
    if tools is None:
        tools = ALL_TOOLS

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
    result = tool_func(context, **arguments)

    return {"type": "tool_result", "tool_use_id": tool_use.id, "content": result}
