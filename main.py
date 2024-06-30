import os
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

from heare.developer.tools import TOOLS_SCHEMA, handle_tool_use


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
    tool_result_buffer = []

    while True:
        if not tool_result_buffer:
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

        else:
            chat_history.append(tool_result_buffer.pop(0))

        with Live(console=console, auto_refresh=True) as live:
            ai_response = ""
            with client.messages.stream(
                    max_tokens=1024,
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
                    result, tool_use = handle_tool_use(final_message)

                    tool_result_buffer.append({"role": "user", "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result
                    }]})
                elif final_message.stop_reason == 'max_tokens':
                    console.print(Panel(f"[bold red]Hit max tokens.[/bold red]"))



    console.print("[bold green]Chat ended. Goodbye![/bold green]")


if __name__ == "__main__":
    main()

