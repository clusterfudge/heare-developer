import argparse
import asyncio
import io
import os
import re
import sys
from typing import Dict, Any, List

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.box import HORIZONTALS

from prompt_toolkit import PromptSession, ANSI
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.document import Document

from heare.developer import personas
from heare.developer.agent import run
from heare.developer.context import AgentContext
from heare.developer.models import model_names, get_model
from heare.developer.sandbox import SandboxMode
from heare.developer.user_interface import UserInterface
from heare.developer.toolbox import Toolbox
from prompt_toolkit.completion import Completer, WordCompleter, Completion

from heare.developer.utils import wrap_text_as_content_block

SANDBOX_MODE_MAP = {mode.name.lower(): mode for mode in SandboxMode}
SANDBOX_MODE_MAP["dwr"] = SandboxMode.ALLOW_ALL


def parse_sandbox_mode(value: str) -> SandboxMode:
    canonicalized = value.lower().replace("-", "_")
    if canonicalized in SANDBOX_MODE_MAP:
        return SANDBOX_MODE_MAP[canonicalized]
    raise argparse.ArgumentTypeError(f"Invalid sandbox mode: {value}")


# Use the pre-defined HORIZONTALS box which has only top and bottom borders
# This makes it easier to copy-paste content from the terminal
HORIZONTAL_ONLY_BOX = HORIZONTALS


def create_clean_panel(content, title=None, style=""):
    """Create a panel with only horizontal borders to make copy/paste easier"""
    return Panel(
        content,
        title=title,
        expand=False,
        box=HORIZONTAL_ONLY_BOX,
        border_style=style,
        padding=(1, 0),  # Vertical padding but no horizontal padding
    )


def rich_to_prompt_toolkit(rich_text):
    """Convert Rich formatted text to prompt_toolkit compatible format"""
    # Capture Rich output as ANSI
    string_io = io.StringIO()
    # Force terminal colors to ensure ANSI codes are generated
    console = Console(file=string_io, force_terminal=True, color_system="standard")
    console.print(rich_text, end="")  # end="" prevents extra newline

    # Get the ANSI string
    ansi_string = string_io.getvalue()

    # Convert to prompt_toolkit format
    prompt_toolkit_formatted = ANSI(ansi_string)

    return prompt_toolkit_formatted


class CLIUserInterface(UserInterface):
    def __init__(self, console: Console, sandbox_mode: SandboxMode):
        self.console = console
        self.sandbox_mode = sandbox_mode
        self.toolbox = None  # Will be set after Sandbox is created

        # Initialize the session with the history file
        history_file_path = self._get_history_file_path()
        history = FileHistory(history_file_path)
        self.session = PromptSession(
            history=history,
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
            complete_while_typing=True,
        )

    def _get_history_file_path(self) -> str:
        """
        Create a directory for chat history based on the SHA256 hash of the current working directory.
        Returns the path to the chat history file.

        If a chat_history.txt file exists in the current directory, migrate it to the new location.
        """
        import hashlib
        import shutil

        # Get current working directory and compute its SHA256
        cwd = os.getcwd()
        cwd_hash = hashlib.sha256(cwd.encode()).hexdigest()

        # Create the directory structure
        history_dir = os.path.expanduser(f"~/.cache/hdev/{cwd_hash}")
        os.makedirs(history_dir, exist_ok=True)

        # Store the current working directory in the cwd file
        cwd_file_path = os.path.join(history_dir, "cwd")
        with open(cwd_file_path, "w") as f:
            f.write(cwd)

        # Path to the new history file
        new_history_file_path = os.path.join(history_dir, "chat_history.txt")

        # Check if a chat_history.txt exists in the current directory and migrate it
        old_history_file_path = os.path.join(cwd, "chat_history.txt")
        if os.path.exists(old_history_file_path) and os.path.isfile(
            old_history_file_path
        ):
            # Only migrate if the destination file doesn't exist or is empty
            if (
                not os.path.exists(new_history_file_path)
                or os.path.getsize(new_history_file_path) == 0
            ):
                try:
                    shutil.copy2(old_history_file_path, new_history_file_path)
                    # Optionally remove the old file after successful migration
                    os.remove(old_history_file_path)
                    print(
                        f"Migrated chat history from {old_history_file_path} to {new_history_file_path}"
                    )
                except (shutil.Error, OSError) as e:
                    print(f"Error migrating chat history: {e}")

        # Return the path to the chat history file
        return new_history_file_path

    def set_toolbox(self, toolbox: Toolbox):
        """Set the toolbox and initialize the completer with its commands"""
        self.toolbox = toolbox

        commands = {
            "/quit": "Quit the chat",
            "/exit": "Quit the chat",
            "/restart": "Clear chat history and start over",
        }
        for tool_name, spec in toolbox.local.items():
            commands[f"!{tool_name}"] = spec["docstring"]

        self.session.completer = CustomCompleter(commands, self.session.history)

    def handle_system_message(self, message: str, markdown=True, live=None) -> None:
        from rich.markdown import Markdown

        if not message:
            return

        if markdown:
            # For system messages, use yellow styling but still treat as markdown
            content = Markdown(message)
        else:
            content = message

        panel = create_clean_panel(
            content,
            title="System Message",
            style="bold yellow",
        )

        if live:
            live.update(panel)
        else:
            self.console.print(panel)

    def handle_assistant_message(self, message: str, markdown=True) -> None:
        from rich.markdown import Markdown

        if markdown:
            content = Markdown(message)
        else:
            content = message

        self.console.print(
            create_clean_panel(
                content,
                title="AI Assistant",
                style="bold green",
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
                    "[bold yellow]Allow this action? (y/N/D for 'do something else'): [/bold yellow]"
                )
            )
            .strip()
            .lower()
        )
        if response == "d":
            from heare.developer.sandbox import DoSomethingElseError

            raise DoSomethingElseError()
        return response == "y"

    def permission_rendering_callback(
        self,
        action: str,
        resource: str,
        action_arguments: Dict | None,
    ) -> None:
        from rich.console import Group
        from rich.text import Text

        if not action_arguments:
            action_arguments = {}

        # Create formatted arguments display
        formatted_params = "\n".join(
            [f"  {key}: {value}" for key, value in action_arguments.items()]
        )

        # Create a group with nicely formatted sections
        permission_group = Group(
            Text("Action:", style="bold blue"),
            Text(f"  {action}"),
            Text("Resource:", style="bold cyan"),
            Text(f"  {resource}"),
            Text("Arguments:", style="bold green"),
            Text(f"{formatted_params}"),
        )

        self.console.print(
            create_clean_panel(
                permission_group,
                title="Permission Check",
                style="bold yellow",
            )
        )

    def handle_tool_use(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
    ):
        pass

    def handle_tool_result(
        self, name: str, result: Dict[str, Any], markdown=True, live=None
    ) -> None:
        from rich.markdown import Markdown
        from rich.console import Group
        from rich.text import Text

        # Get the content based on tool type
        content = (
            result["content"]
            if name not in ["read_file", "write_file", "edit_file"]
            else "File operation completed"
        )

        # Format parameters if they exist (removing this could cause compatibility issues)

        # Create the header section with command name only (parameters section removed)
        header = Group(Text("Command:", style="bold blue"), Text(f"  {name}"))

        # Create the result section - treat content as markdown for code blocks, etc.
        result_header = Text("Result:", style="bold green")
        result_content = (
            Markdown(content)
            if isinstance(content, str) and markdown
            else Text(str(content))
        )

        # Group all components together
        display_group = Group(header, Text(""), result_header, result_content)

        panel = create_clean_panel(
            display_group,
            title="Tool Result",
            style="bold magenta",
        )

        if live:
            live.update(panel)
        else:
            self.console.print(panel)

    async def get_user_input(self, prompt: str = "") -> str:
        _console = Console(file=None)
        user_input = await self.session.prompt_async(rich_to_prompt_toolkit(prompt))

        # Handle multi-line input
        if user_input.strip() == "{":
            multi_line_input = []
            while True:
                line = await self.session.prompt_async("... ")
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
        cached_tokens: int | None = None,
        conversation_size: int | None = None,
        context_window: int | None = None,
    ) -> None:
        token_components = [
            ("Token Count:\n", "bold"),
            (
                f"Prompt: {prompt_tokens}{f' (cached: {cached_tokens})' if cached_tokens else ''}\n",
                "cyan",
            ),
            (f"Completion: {completion_tokens}\n", "green"),
            (f"Total: {total_tokens}\n", "yellow"),
        ]

        # Add conversation size and context window information if available
        if conversation_size is not None and context_window is not None:
            # Calculate percentage of context window used
            usage_percentage = (conversation_size / context_window) * 100

            # Calculate tokens remaining before compaction threshold (85% by default)
            compaction_threshold = int(context_window * 0.85)
            tokens_remaining = max(0, compaction_threshold - conversation_size)

            # Choose color based on how full the context window is
            color = "green"
            if usage_percentage > 70:
                color = "yellow"
            if usage_percentage > 80:
                color = "orange"
            if usage_percentage > 90:
                color = "red"

            token_components.extend(
                [
                    (f"Conversation size: {conversation_size:,} tokens ", color),
                    (f"({usage_percentage:.1f}% of {context_window:,})\n", color),
                    (
                        f"Remaining before compaction: {tokens_remaining:,} tokens\n",
                        color,
                    ),
                ]
            )

        # Add cost information
        token_components.append((f"Cost: ${round(total_cost, 6)}", "orange"))

        token_count = Text.assemble(*token_components)
        self.console.print(token_count)

    def display_welcome_message(self) -> None:
        from rich.markdown import Markdown

        welcome_md = """
## Welcome to the Heare Developer CLI

Your personal coding assistant powered by AI.

**Tips:**
* For multi-line input, start with `{` on a new line, enter your content, and end with `}` on a new line
* Markdown formatting is supported for all output
* Code blocks will be syntax highlighted automatically
        """

        self.console.print(
            create_clean_panel(
                Markdown(welcome_md),
                style="bold cyan",
            )
        )

    def status(self, message, spinner=None):
        return self.console.status(message, spinner=spinner or "dots")

    def bare(self, message: str | Any, live=None) -> None:
        if live:
            live.update(message)
        else:
            self.console.print(message)


class CustomCompleter(Completer):
    def __init__(self, commands, history):
        self.commands = commands
        self.history = history
        self.word_completer = WordCompleter(
            list(commands.keys()), ignore_case=True, sentence=True, meta_dict=commands
        )
        self.path_pattern = re.compile(r"[^\s@]+|@[^\s]*")

        # Import model names for model command completion
        try:
            from heare.developer.models import model_names, MODEL_MAP

            self.model_names = model_names()
            self.short_model_names = list(MODEL_MAP.keys())
        except ImportError:
            self.model_names = []
            self.short_model_names = []

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
        if word.startswith("/"):
            # Check if this is a model command with arguments
            text_before_cursor = document.text_before_cursor
            if text_before_cursor.startswith("/model "):
                # Extract the partial model name after "/model "
                model_partial = text_before_cursor[7:]  # Remove "/model "

                # Provide completions for model names
                for model_name in self.short_model_names + [
                    m for m in self.model_names if m not in self.short_model_names
                ]:
                    if model_name.lower().startswith(model_partial.lower()):
                        completion_text = "/model " + model_name
                        yield Completion(
                            completion_text,
                            start_position=-(len(text_before_cursor)),
                            display=model_name,
                        )
            else:
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


def main(args: List[str]):
    # Store original args for session metadata
    original_args = args.copy()

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("sandbox", nargs="*")
    arg_parser.add_argument("--model", default="sonnet", choices=model_names())
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
        "--dwr",
        action="store_const",
        const=SandboxMode.ALLOW_ALL,
        dest="sandbox_mode",
        help="Shorthand for --sandbox-mode dwr",
    )
    arg_parser.add_argument(
        "--prompt",
        help="Initial prompt for the assistant. If starts with @, will read from file",
    )
    arg_parser.add_argument(
        "--disable-compaction",
        action="store_true",
        help="Disable automatic conversation compaction",
    )
    arg_parser.add_argument(
        "--session-id",
        help="Session ID to resume. This will load the session's conversation history.",
    )
    arg_parser.add_argument(
        "--persona",
        choices=personas.names(),
    )
    args = arg_parser.parse_args(args[1:])  # Skip the program name in args[0]

    # Check for session ID in environment variable if not specified in args
    if not args.session_id and "HEARE_DEVELOPER_SESSION_ID" in os.environ:
        args.session_id = os.environ.get("HEARE_DEVELOPER_SESSION_ID")

    console = Console()
    user_interface = CLIUserInterface(console, args.sandbox_mode)

    initial_prompt = None
    if args.prompt:
        if args.prompt.startswith("@"):
            filename = args.prompt[1:]
            try:
                console.print(f"Reading prompt from file: {filename}")
                with open(filename, "r") as f:
                    initial_prompt = f.read().strip()

                    # Replace environment variables that start with HEARE_DEVELOPER_
                    # and are contained in double curly braces
                    def replace_env_var(match):
                        var_name = match.group(1)
                        if var_name.startswith("HEARE_DEVELOPER_"):
                            return os.environ.get(var_name, "")
                        return match.group(
                            0
                        )  # Return the original if not starting with HEARE_DEVELOPER_

                    # Pattern to match {{HEARE_DEVELOPER_*}} but not other {{*}} patterns
                    pattern = r"\{\{(HEARE_DEVELOPER_[A-Za-z0-9_]+)\}\}"
                    initial_prompt = re.sub(pattern, replace_env_var, initial_prompt)

                    console.print(
                        f"File content loaded: {len(initial_prompt)} characters"
                    )
            except FileNotFoundError:
                console.print(f"[red]Error: Could not find file {filename}[/red]")
                return
            except Exception as e:
                console.print(f"[red]Error reading file {filename}: {str(e)}[/red]")
                return
        else:
            initial_prompt = args.prompt

    if not initial_prompt and not args.session_id:
        user_interface.display_welcome_message()

    context = AgentContext.create(
        model_spec=get_model(args.model),
        sandbox_mode=args.sandbox_mode,
        sandbox_contents=args.sandbox,
        user_interface=user_interface,
        session_id=args.session_id,
        cli_args=original_args,
    )

    system_block: dict[str, Any] | None = (
        wrap_text_as_content_block(personas.for_name(args.persona))
        if args.persona
        else None
    )

    asyncio.run(
        run(
            agent_context=context,
            initial_prompt=initial_prompt,
            system_prompt=system_block,
            single_response=bool(initial_prompt),
            enable_compaction=not args.disable_compaction,
        )
    )


if __name__ == "__main__":
    main(sys.argv)
