import sys
from typing import List

from dotenv import load_dotenv
from rich.console import Console

from heare.developer.hdev import main as dev_main, CLIUserInterface
from heare.developer.sandbox import Sandbox, SandboxMode
from heare.developer.toolbox import Toolbox


def main(args: List[str] = None):
    if not args:
        args = sys.argv
    # TODO: this is spooky?
    sandbox = Sandbox(".", SandboxMode.ALLOW_ALL)
    toolbox = Toolbox(sandbox)

    commands = set(toolbox.local.keys())

    if len(args) > 1 and args[1] in commands:
        # Pass remaining arguments to the developer CLI
        # translate tool spec to argparse
        load_dotenv()
        console = Console()
        user_interface = CLIUserInterface(console, sandbox.mode)
        toolbox.local[args[1]]["invoke"](user_interface, sandbox, " ".join(args[2:]))
    else:
        dev_main(args)


if __name__ == "__main__":
    main()
