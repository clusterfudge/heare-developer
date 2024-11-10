import argparse
import os
from typing import Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from heare.developer.agent import run
from heare.developer.utils import cli_tools, CustomCompleter
from heare.developer.sandbox import SandboxMode
from heare.developer.user_interface import UserInterface

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

        commands = {
            "!quit": "Quit the chat",
            "!exit": "Quit the chat",
            "!restart": "Clear chat history and start over",
        }
        for tool_name, spec in cli_tools.tools.items():
            commands[f"!{tool_name}"] = spec["docstring"]

        history = FileHistory("./chat_history.txt")
        custom_completer = CustomCompleter(commands, history)

        self.session = PromptSession(
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
            completer=custom_completer,
            complete_while_typing=True,
        )

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
        formatted_params = (
            "\n".join([f"  {key}: {value}" for key, value in action_arguments.items()])
            if action_arguments
            else ""
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

    def handle_tool_use(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
    ):
        formatted_params = "\n".join(
            [f"  {key}: {value}" for key, value in tool_params.items()]
        )

        self.console.print(
            Panel(
                f"[bold blue]Action:[/bold blue] {tool_name}\n"
                f"[bold cyan]Resource:[/bold cyan] {tool_params.get('path', 'N/A')}\n"
                f"[bold green]Arguments:[/bold green]\n{formatted_params}",
                title="Permission Check",
                expand=False,
                border_style="bold yellow",
            )
        )

    def handle_tool_result(self, name: str, result: Dict[str, Any]) -> None:
        content = (
            result["content"]
            if name not in ["read_file", "write_file", "edit_file"]
            else "File operation completed"
        )
        self.console.print(
            Panel(
                f"[bold green]Result:[/bold green]\n{content}",
                title=f"Tool Result: {name}",
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
        cli_tools,
        user_interface,
        initial_prompt=initial_prompt,
        single_response=bool(initial_prompt),
    )


if __name__ == "__main__":
    main()
