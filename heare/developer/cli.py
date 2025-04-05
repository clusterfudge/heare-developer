import sys
from typing import List

from dotenv import load_dotenv
from rich.console import Console

from heare.developer.context import AgentContext
from heare.developer.hdev import main as dev_main, CLIUserInterface
from heare.developer.sandbox import Sandbox, SandboxMode
from heare.developer.toolbox import Toolbox


def main(args: List[str] = None):
    if not args:
        args = sys.argv
    load_dotenv()
    console = Console()
    sandbox = Sandbox(".", SandboxMode.ALLOW_ALL)
    context = AgentContext.create(
        model_spec={},
        sandbox_mode=SandboxMode.ALLOW_ALL,
        sandbox_contents=[],
        user_interface=CLIUserInterface(console, sandbox.mode),
    )
    toolbox = Toolbox(context)

    commands = set(toolbox.local.keys())

    if len(args) > 1 and args[1] in commands:
        # Pass remaining arguments to the developer CLI
        # translate tool spec to argparse
        tool_name = args[1]
        tool_args = " ".join(args[2:])  # TODO(2025-03-19): do something with shlex
        toolbox.invoke_cli_tool(tool_name, arg_str=tool_args, confirm_to_add=False)
    else:
        # Pass all arguments to the developer main function
        dev_main(args)


if __name__ == "__main__":
    main()
