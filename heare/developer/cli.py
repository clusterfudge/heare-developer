import argparse
import os
import re
from typing import Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.document import Document

from heare.developer.agent import run
from heare.developer.sandbox import SandboxMode
from heare.developer.user_interface import UserInterface
from heare.developer.toolbox import Toolbox
from prompt_toolkit.completion import Completer, WordCompleter, Completion

MODEL_MAP = {
    "opus": {
        "title": "claude-3-opus-20240229",
        "pricing": {"input": 15.00, "output": 75.00},
    },
    "sonnet": {
        "title": "claude-3-sonnet-20240229",
        "pricing": {"input": 15.00, "output": 75.00},
    },
    "sonnet-3.5": {
        "title": "claude-3-5-sonnet-latest",
        "pricing": {"input": 15.00, "output": 75.00},
    },
    "haiku": {
        "title": "claude-3-haiku-20240307",
        "pricing": {"input": 15.00, "output": 75.00},
    },
}

SANDBOX_MODE_MAP = {mode.name.lower(): mode for mode in SandboxMode}


def parse_sandbox_mode(value: str) -> SandboxMode:
    canonicalized = value.lower().replace("-", "_")
    if canonicalized in SANDBOX_MODE_MAP:
        return SANDBOX_MODE_MAP[canonicalized]
    raise argparse.ArgumentTypeError(f"Invalid sandbox mode: {value}")


class CLIUserInterface(UserInterface):
    def __init__(self, console: Console, sandbox_mode: SandboxMode):
        self.console = console
        self.sandbox_mode = sandbox_mode
        self.toolbox = None  # Will be set after Sandbox is created

        history = FileHistory("./chat_history.txt")
        self.session = PromptSession(
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
            complete_while_typing=True,
        )

    def set_toolbox(self, toolbox: Toolbox):
        """Set the toolbox and initialize the completer with its commands"""
        self.toolbox = toolbox

        commands = {
            "!quit": "Quit the chat",
            "!exit": "Quit the chat",
            "!restart": "Clear chat history and start over",
        }
        for tool_name, spec in toolbox.local.items():
            commands[f"!{tool_name}"] = spec["docstring"]

        self.session.completer = CustomCompleter(commands, self.session.history)

    def handle_system_message(self, message: str) -> None:
        self.console.print("\n")
        self.console.print(
            Panel(
                f"[bold yellow]{message}[/bold yellow]",
                title="System Message",
                expand=False,
                border_style="bold yellow",
            )
        )

    def handle_assistant_message(self, message: str) -> None:
        self.console.print(
            Panel(
                f"[bold green]{message}[/bold green]",
                title="AI Assistant",
                expand=False,
                border_style="bold green",
            )
        )

    def permission_callback(
        self,
        action: str,
        resource: str,
        sandbox_mode: SandboxMode,
        action_arguments: Dict | None,
    ) -> bool:
        response = (
            str(
                self.console.input(
                    "[bold yellow]Allow this action? (y/N): [/bold yellow]"
                )
            )
            .strip()
            .lower()
        )
        return response == "y"

    def permission_rendering_callback(
        self,
        action: str,
        resource: str,
        action_arguments: Dict | None,
    ) -> None:
        if not action_arguments:
            action_arguments = {}
        formatted_params = "\n".join(
            [f"  {key}: {value}" for key, value in action_arguments.items()]
        )

        self.console.print(
            Panel(
                f"[bold blue]Action:[/bold blue] {action}\n"
                f"[bold cyan]Resource:[/bold cyan] {resource}\n"
                f"[bold green]Arguments:[/bold green]\n{formatted_params}",
                title="Permission Check",
                expand=False,
                border_style="bold yellow",
            )
        )

    def handle_tool_use(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
    ):
        pass

    def handle_tool_result(self, name: str, result: Dict[str, Any]) -> None:
        # Get the content based on tool type
        content = (
            result["content"]
            if name not in ["read_file", "write_file", "edit_file"]
            else "File operation completed"
        )

        # Format parameters if they exist
        params_str = ""
        if "params" in result:
            params_str = "\n".join(
                f"  {key}: {value}" for key, value in result["params"].items()
            )

        display_text = (
            f"[bold blue]Command:[/bold blue] {name}\n"
            f"[bold cyan]Parameters:[/bold cyan]\n{params_str}\n"
            f"[bold green]Result:[/bold green]\n{content}"
        )

        self.console.print(
            Panel(
                display_text,
                title="Tool Result",
                expand=False,
                border_style="bold magenta",
            )
        )

    def get_user_input(self, prompt: str = "") -> str:
        user_input = self.session.prompt(prompt)

        # Handle multi-line input
        if user_input.strip() == "{":
            multi_line_input = []
            while True:
                line = self.session.prompt("... ")
                if line.strip() == "}":
                    break
                multi_line_input.append(line)
            user_input = "\n".join(multi_line_input)

        return user_input

    def handle_user_input(self, user_input: str):
        """
        Get input from the user.

        :param user_input: the input from the user
        """
        # in the CLI, we don't have a good mechanism to remove the input box.
        # instead, we just won't re-render the user's input

    def display_token_count(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        total_cost: float,
    ) -> None:
        token_count = Text.assemble(
            ("Token Count:\n", "bold"),
            (f"Prompt: {prompt_tokens}\n", "cyan"),
            (f"Completion: {completion_tokens}\n", "green"),
            (f"Total: {total_tokens}\n", "yellow"),
            (f"Cost: ${round(total_cost, 2)}", "orange"),
        )
        self.console.print(token_count)

    def display_welcome_message(self) -> None:
        self.console.print(
            Panel(
                "[bold green]Welcome to the Heare Developer CLI, your personal coding assistant.[/bold green]\n"
                "[bold yellow]For multi-line input, start with '{' on a new line, enter your content, and end with '}' on a new line.[/bold yellow]",
                expand=False,
            )
        )

    def status(self, message, spinner=None):
        return self.console.status(message, spinner=spinner)


class CustomCompleter(Completer):
    def __init__(self, commands, history):
        self.commands = commands
        self.history = history
        self.word_completer = WordCompleter(
            list(commands.keys()), ignore_case=True, sentence=True, meta_dict=commands
        )
        self.path_pattern = re.compile(r"[^\s@]+|@[^\s]*")

    def get_word_under_cursor(self, document: Document) -> tuple[str, int]:
        """Get the word under the cursor and its start position."""
        # Get the text before cursor
        text_before_cursor = document.text_before_cursor

        # Find the last space before cursor
        last_space = text_before_cursor.rindex(" ") if " " in text_before_cursor else -1
        current_word = text_before_cursor[last_space + 1 :]

        # If we have a word starting with @, that's our target
        if "@" in current_word:
            return current_word, -(len(current_word))

        return current_word, -(len(current_word))

    def get_completions(self, document, complete_event):
        word, start_position = self.get_word_under_cursor(document)

        # Handle command completions
        if word.startswith("!"):
            yield from self.word_completer.get_completions(document, complete_event)

        # Handle file system completions
        elif "@" in word:
            # Get the path after @
            at_index = word.index("@")
            path = word[at_index + 1 :]
            dirname = os.path.dirname(path) if path else "."
            basename = os.path.basename(path)

            try:
                # If dirname is empty, use current directory
                if not dirname or dirname == "":
                    dirname = "."

                # List directory contents
                for entry in os.listdir(dirname):
                    entry_path = os.path.join(dirname, entry)

                    # Only show entries that match the current basename
                    if entry.lower().startswith(basename.lower()):
                        # Add trailing slash for directories
                        display = entry + "/" if os.path.isdir(entry_path) else entry
                        full_path = os.path.join(dirname, display)

                        # Remove './' from the beginning if present
                        if full_path.startswith("./"):
                            full_path = full_path[2:]

                        # Preserve any text before the @ in the completion
                        prefix = word[:at_index]
                        completion = prefix + "@" + full_path

                        yield Completion(
                            completion, start_position=start_position, display=display
                        )
            except OSError:
                pass  # Handle any filesystem errors gracefully

        # Handle history completions
        else:
            for history_item in reversed(self.history.get_strings()):
                if history_item.startswith(word):
                    yield Completion(history_item, start_position=start_position)


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("sandbox", nargs="*")
    arg_parser.add_argument(
        "--model", default="sonnet-3.5", choices=list(MODEL_MAP.keys())
    )
    arg_parser.add_argument(
        "--summary-cache",
        default=os.path.join(os.path.expanduser("~"), ".cache/heare.summary_cache"),
    )
    arg_parser.add_argument(
        "--sandbox-mode",
        type=parse_sandbox_mode,
        choices=list(SANDBOX_MODE_MAP.values()),
        default="remember_per_resource",
        help="Set the sandbox mode for file operations",
    )
    arg_parser.add_argument(
        "--prompt",
        help="Initial prompt for the assistant. If starts with @, will read from file",
    )
    args = arg_parser.parse_args()

    console = Console()
    user_interface = CLIUserInterface(console, args.sandbox_mode)

    initial_prompt = None
    if args.prompt:
        if args.prompt.startswith("@"):
            filename = args.prompt[1:]
            try:
                with open(filename, "r") as f:
                    initial_prompt = f.read().strip()
            except FileNotFoundError:
                console.print(f"[red]Error: Could not find file {filename}[/red]")
                return
            except Exception as e:
                console.print(f"[red]Error reading file {filename}: {str(e)}[/red]")
                return
        else:
            initial_prompt = args.prompt

    if not initial_prompt:
        user_interface.display_welcome_message()

    run(
        MODEL_MAP.get(args.model),
        args.sandbox,
        args.sandbox_mode,
        None,  # Toolbox will be created in run()
        user_interface,
        initial_prompt=initial_prompt,
        single_response=bool(initial_prompt),
    )


if __name__ == "__main__":
    main()
