import argparse
import os

from typing import Dict

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from heare.developer.agent import run
from heare.developer.utils import cli_tools
from heare.developer.sandbox import SandboxMode

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
        "title": "claude-3-5-sonnet-20240620",
        "pricing": {"input": 15.00, "output": 75.00},
    },
    "haiku": {
        "title": "claude-3-haiku-20240307",
        "pricing": {"input": 15.00, "output": 75.00},
    },
}


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
        type=SandboxMode,
        choices=list(SandboxMode),
        default=SandboxMode.REMEMBER_PER_RESOURCE,
        help="Set the sandbox mode for file operations",
    )
    args = arg_parser.parse_args()

    console = Console()
    console.print(
        Panel(
            "[bold green]Welcome to the Heare Developer CLI, your personal coding assistant.[/bold green]\n"
            "[bold yellow]For multi-line input, start with '{' on a new line, enter your content, and end with '}' on a new line.[/bold yellow]",
            expand=False,
        )
    )

    run(
        MODEL_MAP.get(args.model),
        args.sandbox,
        args.sandbox_mode,
        cli_tools,
        permission_check_callback,
        render_tool_use,
        format_token_count,
    )


def format_token_count(prompt_tokens, completion_tokens, total_tokens, total_cost):
    return Text.assemble(
        ("Token Count:\n", "bold"),
        (f"Prompt: {prompt_tokens}\n", "cyan"),
        (f"Completion: {completion_tokens}\n", "green"),
        (f"Total: {total_tokens}\n", "yellow"),
        (f"Cost: ${round(total_cost, 2)}", "orange"),
    )


def render_permission_check(
    console, action: str, resource: str, action_arguments: Dict | None = None
):
    formatted_args = "\n".join(
        [f"  {key}: {value}" for key, value in (action_arguments or {}).items()]
    )
    console.print(
        Panel(
            f"[bold blue]Action:[/bold blue] {action}\n"
            f"[bold cyan]Resource:[/bold cyan] {resource}\n"
            f"[bold green]Arguments:[/bold green]\n{formatted_args}",
            title="Permission Check",
            expand=False,
            border_style="bold yellow",
        )
    )


def permission_check_callback(
    console: Console,
    action: str,
    resource: str,
    mode: SandboxMode,
    action_arguments: Dict | None = None,
) -> bool:
    render_permission_check(console, action, resource, action_arguments)
    response = (
        str(console.input("[bold yellow]Allow this action? (y/N): [/bold yellow]"))
        .strip()
        .lower()
    )

    return response == "y"


def render_tool_use(console, tool_use_message, results):
    tool_use_map = {
        tool_use.id: tool_use
        for tool_use in tool_use_message.content
        if tool_use.type == "tool_use"
    }
    for result in results:
        tool_use = tool_use_map[result["tool_use_id"]]
        tool_name = tool_use.name
        tool_params = tool_use.input

        formatted_params = "\n".join(
            [f"  {key}: {value}" for key, value in tool_params.items()]
        )

        renderable = (
            f"[bold blue]Tool:[/bold blue] {tool_name}\n"
            f"[bold cyan]Parameters:[/bold cyan]\n{formatted_params}\n"
        )

        if tool_name not in ["read_file", "write_file", "edit_file"]:
            renderable += f"[bold green]Result:[/bold green]\n{result['content']}"

        console.print(
            Panel(
                renderable,
                title="Tool Usage",
                expand=False,
                border_style="bold magenta",
            )
        )


if __name__ == "__main__":
    main()
