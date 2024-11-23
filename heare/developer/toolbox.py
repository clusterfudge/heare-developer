from typing import Callable, List
from .sandbox import Sandbox
import subprocess
import os
import inspect
from .commit import run_commit


from .tools import ALL_TOOLS


class Toolbox:
    def __init__(self, sandbox: Sandbox, agent_tools: List[Callable] = ALL_TOOLS):
        self.sandbox = sandbox
        self.local = {}  # CLI tools
        self.agent_tools = agent_tools

        self.register_cli_tool(
            "archive",
            self._archive_chat,
            "Archive the current chat history to a JSON file",
        )

        # Register CLI tools
        self.register_cli_tool("help", self._help, "Show help", aliases=["h"])
        self.register_cli_tool(
            "add", self._add, "Add file or directory to sandbox", aliases=["a"]
        )
        self.register_cli_tool(
            "remove",
            self._remove,
            "Remove a file or directory from sandbox",
            aliases=["rm", "delete"],
        )
        self.register_cli_tool(
            "list", self._list, "List contents of the sandbox", aliases=["ls", "tree"]
        )
        self.register_cli_tool(
            "dump",
            self._dump,
            "Render the system message, tool specs, and chat history",
        )
        self.register_cli_tool(
            "exec",
            self._exec,
            "Execute a bash command and optionally add it to tool result buffer",
        )
        self.register_cli_tool(
            "commit", self._commit, "Generate and execute a commit message"
        )

        # Agent tools (used by the LLM)
        self.agent = {
            tool.__name__: getattr(self, f"_{tool.__name__}")
            for tool in self.agent_tools
        }

        # Schema for agent tools
        self.agent_schema = self.schemas()

    def register_cli_tool(
        self,
        name: str,
        func: Callable,
        docstring: str = None,
        aliases: List[str] = None,
    ):
        """Register a CLI tool with the toolbox."""
        tool_info = {
            "name": name,
            "docstring": docstring or inspect.getdoc(func),
            "invoke": func,
            "aliases": aliases or [name],
        }
        self.local[name] = tool_info
        if aliases:
            for alias in aliases:
                self.local[alias] = tool_info

    def invoke_agent_tool(self, tool_use):
        """Invoke an agent tool based on the tool use object."""
        from .tools import invoke_tool

        # Convert agent tools to a list matching tools format
        return invoke_tool(self.sandbox, tool_use, tools=self.agent_tools)

    # CLI Tools
    def _help(self, user_interface, sandbox, user_input, *args, **kwargs):
        """Show help"""
        help_text = "[bold yellow]Available commands:[/bold yellow]\n"
        help_text += "/restart - Clear chat history and start over\n"
        help_text += "/quit - Quit the chat\n"

        displayed_tools = set()
        for tool_name, spec in self.local.items():
            if tool_name not in displayed_tools:
                aliases = ", ".join(
                    [f"/{alias}" for alias in spec["aliases"] if alias != tool_name]
                )
                alias_text = f" (aliases: {aliases})" if aliases else ""
                help_text += f"/{tool_name}{alias_text} - {spec['docstring']}\n"
                displayed_tools.add(tool_name)
                displayed_tools.update(spec["aliases"])

        help_text += "\nYou can ask the AI to read, write, or list files/directories\n"
        help_text += (
            "You can also ask the AI to run bash commands (with some restrictions)"
        )

        user_interface.handle_system_message(help_text)

    def _add(self, user_interface, sandbox, user_input, *args, **kwargs):
        """Add file or directory to sandbox"""
        path = user_input[4:].strip()
        sandbox.get_directory_listing()  # This will update the internal listing
        user_interface.handle_system_message(f"Added {path} to sandbox")
        self._list(user_interface, sandbox)

    def _remove(self, user_interface, sandbox, user_input, *args, **kwargs):
        """Remove a file or directory from sandbox"""
        path = user_input[3:].strip()
        sandbox.get_directory_listing()  # This will update the internal listing
        user_interface.handle_system_message(f"Removed {path} from sandbox")
        self._list(user_interface, sandbox)

    def _list(self, user_interface, sandbox, *args, **kwargs):
        """List contents of the sandbox"""
        sandbox_contents = sandbox.get_directory_listing()
        content = "[bold cyan]Sandbox contents:[/bold cyan]\n" + "\n".join(
            f"[cyan]{item}[/cyan]" for item in sandbox_contents
        )
        user_interface.handle_system_message(content)

    def _dump(self, user_interface, sandbox, user_input, *args, **kwargs):
        """Render the system message, tool specs, and chat history"""
        from .prompt import create_system_message

        content = "[bold cyan]System Message:[/bold cyan]\n"
        content += create_system_message(sandbox)
        content += "\n\n[bold cyan]Tool Specifications:[/bold cyan]\n"
        content += str(self.agent_schema)
        content += "\n\n[bold cyan]Chat History:[/bold cyan]\n"
        for message in kwargs["chat_history"]:
            content += f"\n[bold]{message['role']}:[/bold] {message['content']}"

        user_interface.handle_system_message(content)

    def _exec(self, user_interface, sandbox, user_input, *args, **kwargs):
        """Execute a bash command and optionally add it to tool result buffer"""
        command = user_input[5:].strip()  # Remove '/exec' from the beginning
        result = self._run_bash_command(command)

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
            chat_entry = (
                f"Executed bash command: {command}\n\nCommand output:\n{result}"
            )
            tool_result_buffer = kwargs.get("tool_result_buffer", [])
            tool_result_buffer.append({"role": "user", "content": chat_entry})
            user_interface.handle_system_message(
                "[bold green]Command and output added to tool result buffer as a user message.[/bold green]"
            )
        else:
            user_interface.handle_system_message(
                "[bold yellow]Command and output not added to tool result buffer.[/bold yellow]"
            )

    def _archive_chat(self, user_interface, sandbox, user_input, *args, **kwargs):
        """Archive the current chat history to a JSON file"""
        from datetime import datetime
        from .utils import serialize_to_file, get_data_file

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

    def _commit(self, user_interface, sandbox, user_input, *args, **kwargs):
        """Generate and execute a commit message"""
        # Stage all unstaged changes
        stage_result = self._run_bash_command("git add -A")
        user_interface.handle_system_message(
            "[bold green]Staged all changes:[/bold green]\n" + stage_result
        )

        # Commit the changes
        result = run_commit()
        user_interface.handle_system_message(result)

    # Agent Tools
    def _run_bash_command(self, command: str) -> str:
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

            if not self.sandbox.check_permissions("shell", command):
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

    def _read_file(self, path: str) -> str:
        try:
            return self.sandbox.read_file(path)
        except PermissionError:
            return f"Error: No read permission for {path}"
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def _write_file(self, path: str, content: str) -> str:
        try:
            self.sandbox.write_file(path, content)
            return "File written successfully"
        except PermissionError:
            return f"Error: No write permission for {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    def _list_directory(self, path: str) -> str:
        try:
            contents = self.sandbox.get_directory_listing()

            result = f"Contents of {path}:\n"
            for item_path in contents:
                relative_path = os.path.relpath(item_path, path)
                result += f"{relative_path}\n"
            return result
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    def _edit_file(self, path: str, match_text: str, replace_text: str) -> str:
        try:
            content = self.sandbox.read_file(path)

            # Check if the match_text is unique
            if content.count(match_text) > 1:
                return "Error: The text to match is not unique in the file."
            elif content.count(match_text) == 0:
                # If match_text is not found, append replace_text to the end of the file
                new_content = content + "\n" + replace_text
                self.sandbox.write_file(path, new_content)
                return "Text not found. Content added to the end of the file."
            else:
                # Replace the matched text
                new_content = content.replace(match_text, replace_text, 1)
                self.sandbox.write_file(path, new_content)
                return "File edited successfully"
        except PermissionError:
            return f"Error: No read or write permission for {path}"
        except Exception as e:
            return f"Error editing file: {str(e)}"

    def schemas(self) -> List[dict]:
        """Generate schemas for all tools in the toolbox.

        Returns a list of schema dictionaries matching the format of TOOLS_SCHEMA.
        Each schema has name, description, and input_schema with properties and required fields.
        """
        schemas = []
        for tool in self.agent_tools:
            if hasattr(tool, "schema"):
                schemas.append(tool.schema())
        return schemas
