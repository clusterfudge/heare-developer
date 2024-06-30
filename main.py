import os
import shutil
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

from heare.developer.sandbox import Sandbox
from heare.developer.tools import TOOLS_SCHEMA, handle_tool_use
from heare.developer.prompt import create_system_message


def initialize_sandbox(sandbox_dir=os.getcwd()):
    if not os.path.exists(sandbox_dir):
        os.makedirs(sandbox_dir)
    return sandbox_dir


def main():
    load_dotenv()  # Load environment variables from .env file
    sandbox_dir = initialize_sandbox()
    os.chdir(sandbox_dir)  # Change working directory to the sandbox
    sandbox = Sandbox(sandbox_dir)
    console = Console()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[bold red]Error: ANTHROPIC_API_KEY environment variable not set[/bold red]")
        return

    client = anthropic.Client(api_key=api_key)

    commands = ["!help", "!quit", "!tree", "!restart"]
    command_completer = WordCompleter(commands)

    session = PromptSession(
        history=FileHistory("chat_history.txt"),
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
        completer=merge_completers([command_completer]),
        complete_while_typing=True,
    )

    console.print(Panel(
        "[bold green]Welcome to the Heare Developer CLI, your personal coding assistant.[/bold green]",
        expand=False))
    console.print("[bold yellow]Available commands:[/bold yellow]")
    console.print("[bold yellow]!help - Show help[/bold yellow]")
    console.print("[bold yellow]!quit - Quit the chat[/bold yellow]")
    console.print("[bold yellow]!tree - List contents of the sandbox[/bold yellow]")
    console.print("[bold yellow]!restart - Clear chat history and start over[/bold yellow]")

    # Create system message with current directory contents
    system_message = create_system_message(sandbox)

    chat_history = []
    tool_result_buffer = []

    while True:
        if not tool_result_buffer:
            user_input = session.prompt(FormattedText([('#00FF00', ' > ')]))

            if user_input.startswith("!"):
                if user_input == "!quit":
                    break
                elif user_input == "!help":
                    console.print("[bold yellow]Available commands:[/bold yellow]")
                    console.print("[bold yellow]!help - Show help[/bold yellow]")
                    console.print("[bold yellow]!quit - Quit the chat[/bold yellow]")
                    console.print("[bold yellow]!tree - List contents of the sandbox[/bold yellow]")
                    console.print("[bold yellow]!restart - Clear chat history and start over[/bold yellow]")
                    console.print("[bold yellow]You can ask the AI to read, write, or list files/directories[/bold yellow]")
                    console.print(
                        "[bold yellow]You can also ask the AI to run bash commands (with some restrictions)[/bold yellow]")
                elif user_input == "!tree":
                    sandbox_contents = sandbox.list_sandbox()
                    console.print("[bold cyan]Sandbox contents:[/bold cyan]")
                    for item in sandbox_contents:
                        console.print(f"[cyan]{item}[/cyan]")
                elif user_input == "!restart":
                    chat_history = []
                    tool_result_buffer = []
                    console.print("[bold green]Chat history cleared. Starting over.[/bold green]")
                    continue
                else:
                    console.print(f"[bold red]Unknown command: {user_input}[/bold red]")
                continue

            chat_history.append({"role": "user", "content": user_input})
            console.print(Panel(f"[bold blue]You:[/bold blue] {user_input}", expand=False))

        else:
            chat_history.append(tool_result_buffer.pop(0))

        with (Live(console=console, auto_refresh=True) as live):
            ai_response = ""
            with client.messages.stream(
                    system=system_message,
                    max_tokens=2048,
                    messages=chat_history,
                    model="claude-3-5-sonnet-20240620",
                    tools=TOOLS_SCHEMA
            ) as stream:
                for chunk in stream:
                    if chunk.type == "text":
                        ai_response += chunk.text
                        live.update(Panel(f"[bold green]AI Assistant:[/bold green]\n{ai_response}", expand=False))

                live.update(Panel(f"[bold green]AI Assistant:[/bold green]\n{ai_response}", expand=False))

                final_message = stream.get_final_message()
                chat_history.append({
                    "role": "assistant",
                    "content": final_message.content
                })
        if final_message.stop_reason == 'tool_use':
            results = handle_tool_use(sandbox, final_message)

            tool_result_buffer.append({"role": "user", "content": results})
            for result in results:
                console.print(
                    Panel(
                        f"[italic]tool: {result['tool_use_id']}\n{result['content']}[/italic]",
                        border_style="bold green",
                    )
                )
        elif final_message.stop_reason == 'max_tokens':
            console.print(Panel(f"[bold red]Hit max tokens.[/bold red]"))

    console.print("[bold green]Chat ended. Goodbye![/bold green]")


if __name__ == "__main__":
    main()