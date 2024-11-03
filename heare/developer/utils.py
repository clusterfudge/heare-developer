import inspect
import json
import os
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, IO

from prompt_toolkit.completion import Completer, WordCompleter, Completion

from heare.developer.commit import run_commit
from heare.developer.prompt import create_system_message
from heare.developer.tools import TOOLS_SCHEMA, run_bash_command

# Constants for app name and directories
APP_NAME = "heare"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / APP_NAME
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / APP_NAME


def get_config_dir() -> Path:
    """Get the configuration directory for the application."""
    config_dir = os.environ.get("XDG_CONFIG_HOME", DEFAULT_CONFIG_DIR)
    return Path(config_dir)


def get_data_dir() -> Path:
    """Get the data directory for the application."""
    data_dir = os.environ.get("XDG_DATA_HOME", DEFAULT_DATA_DIR)
    return Path(data_dir)


def ensure_dir_exists(directory: Path) -> None:
    """Ensure that the given directory exists."""
    directory.mkdir(parents=True, exist_ok=True)


def get_config_file(filename: str) -> Path:
    """Get the path to a configuration file."""
    config_dir = get_config_dir()
    ensure_dir_exists(config_dir)
    return config_dir / filename


def get_data_file(filename: str) -> Path:
    """Get the path to a data file."""
    data_dir = get_data_dir()
    ensure_dir_exists(data_dir)
    return data_dir / filename


class CLITools:
    def __init__(self):
        self.tools = {}

    def tool(self, *aliases):
        def decorator(func):
            tool_name = func.__name__
            tool_args = inspect.signature(func).parameters
            tool_docstring = inspect.getdoc(func)

            # Wrap the function to take user_interface instead of console
            def wrapped_func(user_interface, *args, **kwargs):
                return func(user_interface=user_interface, *args, **kwargs)

            tool_info = {
                "name": tool_name,
                "args": tool_args,
                "docstring": tool_docstring,
                "invoke": wrapped_func,
                "aliases": list(aliases) if aliases else [tool_name],
            }
            self.tools[tool_name] = tool_info
            for alias in aliases or [tool_name]:
                self.tools[alias] = tool_info
            return func

        return decorator

    def get_tool(self, name_or_alias):
        """
        Get a tool by its name or alias.

        Args:
            name_or_alias (str): The name or alias of the tool to retrieve.

        Returns:
            dict: The tool information if found, None otherwise.
        """
        return self.tools.get(name_or_alias)


cli_tools = CLITools()


@cli_tools.tool("help", "h")
def help(user_interface, sandbox, user_input, *args, **kwargs):
    """
    Show help
    """
    help_text = "[bold yellow]Available commands:[/bold yellow]\n"
    help_text += "/restart - Clear chat history and start over\n"
    help_text += "/quit - Quit the chat\n"

    displayed_tools = set()
    for tool_name, spec in cli_tools.tools.items():
        if tool_name not in displayed_tools:
            aliases = ", ".join(
                [f"/{alias}" for alias in spec["aliases"] if alias != tool_name]
            )
            alias_text = f" (aliases: {aliases})" if aliases else ""
            help_text += (
                f"/{tool_name}{alias_text} - {spec['docstring']} - {spec['args']}\n"
            )
            displayed_tools.add(tool_name)
            displayed_tools.update(spec["aliases"])

    help_text += "You can ask the AI to read, write, or list files/directories\n"
    help_text += "You can also ask the AI to run bash commands (with some restrictions)"

    user_interface.handle_system_message(help_text)


@cli_tools.tool("a")
def add(user_interface, sandbox, user_input, *args, **kwargs):
    """
    Add file or directory to sandbox
    """
    path = user_input[4:].strip()
    sandbox.get_directory_listing()  # This will update the internal listing
    user_interface.handle_system_message(f"Added {path} to sandbox")
    tree(user_interface, sandbox)


@cli_tools.tool("remove", "delete")
def rm(user_interface, sandbox, user_input, *args, **kwargs):
    """
    Remove a file or directory from sandbox
    """
    path = user_input[3:].strip()
    sandbox.get_directory_listing()  # This will update the internal listing
    user_interface.handle_system_message(f"Removed {path} from sandbox")
    tree(user_interface, sandbox)


@cli_tools.tool("ls", "list")
def tree(user_interface, sandbox, *args, **kwargs):
    """
    List contents of the sandbox
    """
    sandbox_contents = sandbox.get_directory_listing()
    content = "[bold cyan]Sandbox contents:[/bold cyan]\n" + "\n".join(
        f"[cyan]{item}[/cyan]" for item in sandbox_contents
    )
    user_interface.handle_system_message(content)


@cli_tools.tool("dump")
def dump(user_interface, sandbox, user_input, *args, **kwargs):
    """
    Render the system message, tool specs, and chat history
    """
    content = "[bold cyan]System Message:[/bold cyan]\n"
    content += create_system_message(sandbox)
    content += "\n\n[bold cyan]Tool Specifications:[/bold cyan]\n"
    content += TOOLS_SCHEMA
    content += "\n\n[bold cyan]Chat History:[/bold cyan]\n"
    for message in kwargs["chat_history"]:
        content += f"\n[bold]{message['role']}:[/bold] {message['content']}"

    user_interface.handle_system_message(content)


@cli_tools.tool("exec")
def exec(user_interface, sandbox, user_input, *args, **kwargs):
    """
    Execute a bash command and optionally add it to tool result buffer
    """
    command = user_input[5:].strip()  # Remove '/exec' from the beginning
    result = run_bash_command(sandbox, command)

    user_interface.handle_system_message(
        f"[bold cyan]Command Output:[/bold cyan]\n{result}"
    )

    add_to_buffer = (
        user_interface.get_user_input(
            "[bold yellow]Add command and output to tool result buffer? (y/n): [/bold yellow]"
        )
        .strip()
        .lower()
    )
    if add_to_buffer == "y":
        chat_entry = f"Executed bash command: {command}\n\nCommand output:\n{result}"
        tool_result_buffer = kwargs.get("tool_result_buffer", [])
        tool_result_buffer.append({"role": "user", "content": chat_entry})
        user_interface.handle_system_message(
            "[bold green]Command and output added to tool result buffer as a user message.[/bold green]"
        )
    else:
        user_interface.handle_system_message(
            "[bold yellow]Command and output not added to tool result buffer.[/bold yellow]"
        )


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Enum):
            return obj.name
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, SimpleNamespace):
            return vars(obj)
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        if hasattr(obj, "__slots__"):
            return {
                slot: getattr(obj, slot) for slot in obj.__slots__ if hasattr(obj, slot)
            }
        return super().default(obj)


def serialize_to_file(obj: Any, fp: IO[str], indent: int = None) -> None:
    json.dump(obj, fp, cls=CustomJSONEncoder, indent=indent)


def load_config(filename: str = "config.json") -> dict:
    """
    Load a configuration file from the config directory
    """
    config_file = get_config_file(filename)
    if config_file.exists():
        with open(config_file, "r") as f:
            return json.load(f)
    return {}


def save_config(config: dict, filename: str = "config.json") -> None:
    """
    Save a configuration file to the config directory
    """
    config_file = get_config_file(filename)
    with open(config_file, "w") as f:
        serialize_to_file(config, f, indent=2)


@cli_tools.tool
def update_config(user_interface, sandbox, user_input, *args, **kwargs):
    """
    Update the configuration file with a new key-value pair
    """
    parts = user_input.split(maxsplit=3)
    if len(parts) != 4:
        user_interface.handle_system_message(
            "[bold red]Usage: /update_config <key> <value>[/bold red]"
        )
        return

    _, key, value = parts[1:]
    config = load_config()
    config[key] = value
    save_config(config)
    user_interface.handle_system_message(
        f"[bold green]Updated config: {key} = {value}[/bold green]"
    )


@cli_tools.tool
def archive_chat(user_interface, sandbox, user_input, *args, **kwargs):
    """
    Archive the current chat history to a JSON file in the application data directory
    """
    from datetime import datetime

    chat_history = kwargs.get("chat_history", [])
    prompt_tokens = kwargs.get("prompt_tokens", 0)
    completion_tokens = kwargs.get("completion_tokens", 0)
    total_tokens = kwargs.get("total_tokens", 0)
    total_cost = kwargs.get("total_cost", 0.0)

    archive_data = {
        "timestamp": datetime.now().isoformat(),
        "chat_history": chat_history,
        "token_usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
        },
    }

    filename = f"chat_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    archive_file = get_data_file(filename)

    with open(archive_file, "w") as f:
        serialize_to_file(archive_data, f, indent=2)

    user_interface.handle_system_message(
        f"[bold green]Chat history archived to {archive_file}[/bold green]"
    )


class CustomCompleter(Completer):
    def __init__(self, commands, history):
        self.commands = commands
        self.history = history
        self.word_completer = WordCompleter(
            list(commands.keys()), ignore_case=True, sentence=True, meta_dict=commands
        )

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if text.startswith("/"):
            yield from self.word_completer.get_completions(document, complete_event)
        else:
            for history_item in reversed(self.history.get_strings()):
                if history_item.startswith(text):
                    yield Completion(history_item, start_position=-len(text))


@cli_tools.tool()
def commit(user_interface, sandbox, user_input, *args, **kwargs):
    # Stage all unstaged changes
    stage_result = run_bash_command(sandbox, "git add -A")
    user_interface.handle_system_message(
        "[bold green]Staged all changes:[/bold green]\n" + stage_result
    )

    # Commit the changes
    result = run_commit()
    user_interface.handle_system_message(result)
