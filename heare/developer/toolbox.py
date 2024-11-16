from .sandbox import Sandbox
import subprocess
import os


class Toolbox:
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

        # Local tools (CLI tools)
        self.local = {
            "archive": {
                "docstring": "Archive the current chat session",
                "invoke": lambda *args, **kwargs: NotImplemented,  # To be set by CLI
            }
        }

        # Agent tools (used by the LLM)
        self.agent = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "list_directory": self._list_directory,
            "run_bash_command": self._run_bash_command,
            "edit_file": self._edit_file,
        }

        # Schema for agent tools
        self.agent_schema = [
            {
                "name": "read_file",
                "description": "Read the contents of a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file"}
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",
                "description": "Write content to a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file"},
                        "content": {
                            "type": "string",
                            "description": "Content to write",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "list_directory",
                "description": "List contents of a directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the directory",
                        }
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "run_bash_command",
                "description": "Run a bash command",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Bash command to execute",
                        }
                    },
                    "required": ["command"],
                },
            },
            {
                "name": "edit_file",
                "description": "Make a targeted edit to a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file"},
                        "match_text": {
                            "type": "string",
                            "description": "Text to match",
                        },
                        "replace_text": {
                            "type": "string",
                            "description": "Text to replace the matched text with",
                        },
                    },
                    "required": ["path", "match_text", "replace_text"],
                },
            },
        ]

    def invoke_agent_tool(self, tool_use):
        """Invoke an agent tool based on the tool use object."""
        function_name = tool_use.name
        arguments = tool_use.input

        if function_name not in self.agent:
            return {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": f"Unknown function: {function_name}",
            }

        result = self.agent[function_name](**arguments)
        return {"type": "tool_result", "tool_use_id": tool_use.id, "content": result}

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
