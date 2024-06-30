import os
import subprocess
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter, merge_completers
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.shortcuts import print_formatted_text
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
import anthropic
import json
import shlex


def read_file(path):
    try:
        with open(path, 'r') as file:
            return file.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def write_file(path, content):
    try:
        with open(path, 'w') as file:
            file.write(content)
        return "File written successfully"
    except Exception as e:
        return f"Error writing file: {str(e)}"


def list_directory(path):
    try:
        return os.listdir(path)
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def run_bash_command(command):
    try:
        # Split the command string into a list of arguments
        args = shlex.split(command)

        # Check for potentially dangerous commands
        dangerous_commands = ['rm', 'mv', 'cp', 'chmod', 'chown', 'sudo', '>', '>>', '|']
        if any(cmd in args for cmd in dangerous_commands):
            return "Error: This command is not allowed for safety reasons."

        # Run the command and capture output
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)

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


def main():
    load_dotenv()  # Load environment variables from .env file
    console = Console()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[bold red]Error: ANTHROPIC_API_KEY environment variable not set[/bold red]")
        return

    client = anthropic.Client(api_key=api_key)

    commands = ["!help", "!quit"]
    command_completer = WordCompleter(commands)

    session = PromptSession(
        history=FileHistory("chat_history.txt"),
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
        completer=merge_completers([command_completer]),
        complete_while_typing=True,
    )

    console.print(Panel(
        "[bold green]Welcome to the Anthropic Chat Console with Filesystem Access and Bash Command Execution![/bold green]",
        expand=False))
    console.print("[bold yellow]Available commands:[/bold yellow]")
    console.print("[bold yellow]!help - Show help[/bold yellow]")
    console.print("[bold yellow]!quit - Quit the chat[/bold yellow]")

    chat_history = []

    while True:
        print_formatted_text(FormattedText([('#0000FF', ' > ')]), end='')
        user_input = session.prompt("")

        if user_input.startswith("!"):
            if user_input == "!quit":
                break
            elif user_input == "!help":
                console.print("[bold yellow]Available commands:[/bold yellow]")
                console.print("[bold yellow]!help - Show help[/bold yellow]")
                console.print("[bold yellow]!quit - Quit the chat[/bold yellow]")
                console.print("[bold yellow]You can ask the AI to read, write, or list files/directories[/bold yellow]")
                console.print(
                    "[bold yellow]You can also ask the AI to run bash commands (with some restrictions)[/bold yellow]")
            else:
                console.print(f"[bold red]Unknown command: {user_input}[/bold red]")
            continue

        chat_history.append({"role": "user", "content": user_input})
        console.print(Panel(f"[bold blue]You:[/bold blue] {user_input}", expand=False))

        with Live(console=console, auto_refresh=True) as live:
            ai_response = ""
            with client.messages.stream(
                    max_tokens=1024,
                    messages=chat_history,
                    model="claude-3-opus-20240229",
                    tools=[
                        {
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "description": "Read the contents of a file",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string", "description": "Path to the file"}
                                    },
                                    "required": ["path"]
                                }
                            }
                        },
                        {
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "description": "Write content to a file",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string", "description": "Path to the file"},
                                        "content": {"type": "string", "description": "Content to write"}
                                    },
                                    "required": ["path", "content"]
                                }
                            }
                        },
                        {
                            "type": "function",
                            "function": {
                                "name": "list_directory",
                                "description": "List contents of a directory",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string", "description": "Path to the directory"}
                                    },
                                    "required": ["path"]
                                }
                            }
                        },
                        {
                            "type": "function",
                            "function": {
                                "name": "run_bash_command",
                                "description": "Run a bash command",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "command": {"type": "string", "description": "Bash command to execute"}
                                    },
                                    "required": ["command"]
                                }
                            }
                        }
                    ]
            ) as stream:
                for chunk in stream:
                    if chunk.type == "text":
                        ai_response += chunk.text
                        live.update(Panel(f"[bold green]AI Assistant:[/bold green]\n{ai_response}", expand=False))
                    elif chunk.type == "function_call":
                        function_name = chunk.function_call.name
                        arguments = json.loads(chunk.function_call.arguments)

                        if function_name == "read_file":
                            result = read_file(arguments['path'])
                        elif function_name == "write_file":
                            result = write_file(arguments['path'], arguments['content'])
                        elif function_name == "list_directory":
                            result = list_directory(arguments['path'])
                        elif function_name == "run_bash_command":
                            result = run_bash_command(arguments['command'])
                        else:
                            result = f"Unknown function: {function_name}"

                        ai_response += f"\nFunction call: {function_name}\nResult: {result}\n"
                        live.update(Panel(f"[bold green]AI Assistant:[/bold green]\n{ai_response}", expand=False))

            chat_history.append({"role": "assistant", "content": ai_response})

    console.print("[bold green]Chat ended. Goodbye![/bold green]")


if __name__ == "__main__":
    main()

