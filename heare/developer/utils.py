import inspect
import json
from datetime import datetime, date
from enum import Enum
from types import SimpleNamespace
from typing import Any, IO

from prompt_toolkit.completion import Completer, WordCompleter, Completion
from rich.panel import Panel

from heare.developer.prompt import create_system_message
from heare.developer.tools import TOOLS_SCHEMA, run_bash_command


class CLITools:
    def __init__(self):
        self.tools = {}

    def tool(self, func):
        tool_name = func.__name__
        tool_args = inspect.signature(func).parameters
        tool_docstring = inspect.getdoc(func)
        self.tools[tool_name] = {
            "name": tool_name,
            "args": tool_args,
            "docstring": tool_docstring,
            "invoke": func,
        }
        return func


cli_tools = CLITools()


@cli_tools.tool
def help(console, sandbox, user_input, *args, **kwargs):
    """
    Show help
    """
    help_text = "[bold yellow]Available commands:[/bold yellow]\n"
    help_text += "!restart - Clear chat history and start over\n"
    help_text += "!quit - Quit the chat\n"

    for tool_name, spec in cli_tools.tools.items():
        help_text += f"!{tool_name} - {spec['docstring']} - {spec['args']}\n"

    help_text += "You can ask the AI to read, write, or list files/directories\n"
    help_text += "You can also ask the AI to run bash commands (with some restrictions)"

    console.print(Panel(help_text))


@cli_tools.tool
def add(console, sandbox, user_input, *args, **kwargs):
    """
    Add file or directory to sandbox
    """
    path = user_input[4:].strip()
    sandbox.get_directory_listing()  # This will update the internal listing
    console.print(f"[bold green]Added {path} to sandbox[/bold green]")
    tree(console, sandbox)


@cli_tools.tool
def rm(console, sandbox, user_input, *args, **kwargs):
    """
    Remove a file or directory from sandbox
    """
    path = user_input[3:].strip()
    sandbox.get_directory_listing()  # This will update the internal listing
    console.print(f"[bold green]Removed {path} from sandbox[/bold green]")
    tree(console, sandbox)


@cli_tools.tool
def tree(console, sandbox, *args, **kwargs):
    """
    List contents of the sandbox
    """
    sandbox_contents = sandbox.get_directory_listing()
    console.print(
        Panel(
            "[bold cyan]Sandbox contents:[/bold cyan]\n"
            + "\n".join(f"[cyan]{item}[/cyan]" for item in sandbox_contents)
        )
    )


@cli_tools.tool
def dump(console, sandbox, user_input, *args, **kwargs):
    """
    Render the system message, tool specs, and chat history
    """
    console.print("[bold cyan]System Message:[/bold cyan]")
    console.print(create_system_message(sandbox))

    console.print("\n[bold cyan]Tool Specifications:[/bold cyan]")
    console.print(TOOLS_SCHEMA)

    console.print("\n[bold cyan]Chat History:[/bold cyan]")
    for message in kwargs["chat_history"]:
        console.print(f"[bold]{message['role']}:[/bold] {message['content']}")


@cli_tools.tool
def exec(console, sandbox, user_input, *args, **kwargs):
    """
    Execute a bash command and optionally add it to tool result buffer
    """
    command = user_input[5:].strip()  # Remove '!exec' from the beginning
    result = run_bash_command(sandbox, command)

    console.print("[bold cyan]Command Output:[/bold cyan]")
    console.print(result)

    add_to_buffer = (
        console.input(
            "[bold yellow]Add command and output to tool result buffer? (y/n): [/bold yellow]"
        )
        .strip()
        .lower()
    )
    if add_to_buffer == "y":
        chat_entry = f"Executed bash command: {command}\n\nCommand output:\n{result}"
        tool_result_buffer = kwargs.get("tool_result_buffer", [])
        tool_result_buffer.append({"role": "user", "content": chat_entry})
        console.print(
            "[bold green]Command and output added to tool result buffer as a user message.[/bold green]"
        )
    else:
        console.print(
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


@cli_tools.tool
def archive_chat(console, sandbox, user_input, *args, **kwargs):
    """
    Archive the current chat history to a JSON file
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

    with open(filename, "w") as f:
        serialize_to_file(archive_data, f, indent=2)

    console.print(f"[bold green]Chat history archived to {filename}[/bold green]")


class CustomCompleter(Completer):
    def __init__(self, commands, history):
        self.commands = commands
        self.history = history
        self.word_completer = WordCompleter(
            list(commands.keys()), ignore_case=True, sentence=True, meta_dict=commands
        )

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if text.startswith("!"):
            yield from self.word_completer.get_completions(document, complete_event)
        else:
            for history_item in reversed(self.history.get_strings()):
                if history_item.startswith(text):
                    yield Completion(history_item, start_position=-len(text))
