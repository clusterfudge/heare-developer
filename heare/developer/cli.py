import argparse
import os
import shutil
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter, Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.shortcuts import print_formatted_text
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
import anthropic

from heare.developer.sandbox import Sandbox
from heare.developer.tools import TOOLS_SCHEMA, handle_tool_use
from heare.developer.prompt import create_system_message
from heare.developer.utils import CLITools

cli_tools = CLITools()

def initialize_sandbox(sandbox_dir=os.getcwd()):
    if not os.path.exists(sandbox_dir):
        os.makedirs(sandbox_dir)
    return sandbox_dir

class CustomCompleter(Completer):
    def __init__(self, commands, history):
        self.commands = commands
        self.history = history
        self.word_completer = WordCompleter(list(commands.keys()), ignore_case=True, sentence=True, meta_dict=commands)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if text.startswith('!'):
            yield from self.word_completer.get_completions(document, complete_event)
        else:
            for history_item in reversed(self.history.get_strings()):
                if history_item.startswith(text):
                    yield Completion(history_item, start_position=-len(text))


MODEL_MAP = {
    "opus": {"title": "claude-3-opus-20240229", "pricing": {"input": 15.00, "output": 75.00}},
    "sonnet": {"title": "claude-3-sonnet-20240229", "pricing": {"input": 15.00, "output": 75.00}},
    "sonnet-3.5": {"title": "claude-3-5-sonnet-20240620", "pricing": {"input": 15.00, "output": 75.00}},
    "haiku": {"title": "claude-3-haiku-20240307", "pricing": {"input": 15.00, "output": 75.00}},
}

def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--sandbox', default=None)
    arg_parser.add_argument('--model', default='sonnet-3.5', choices=list(MODEL_MAP.keys()))
    arg_parser.add_argument('--summary-cache', default=os.path.join(os.path.expanduser('~'), '.cache/heare.summary_cache'))
    args = arg_parser.parse_args()
    run(MODEL_MAP.get(args.model), args.sandbox)


def format_token_count(prompt_tokens, completion_tokens, total_tokens, total_cost):
    return Text.assemble(
        ("Token Count:\n", "bold"),
        (f"Prompt: {prompt_tokens}\n", "cyan"),
        (f"Completion: {completion_tokens}\n", "green"),
        (f"Total: {total_tokens}\n", "yellow"),
        (f"Cost: ${round(total_cost, 2)}", "orange"),
    )


def run(model, sandbox_dir):
    load_dotenv()
    if sandbox_dir:
        os.chdir(sandbox_dir)
        sandbox = Sandbox(sandbox_dir)
    else:
        sandbox = Sandbox()
    console = Console()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[bold red]Error: ANTHROPIC_API_KEY environment variable not set[/bold red]")
        return

    client = anthropic.Client(api_key=api_key)

    commands = {
        '!quit': 'Quit the chat',
        '!restart': 'Clear chat history and start over',
    }
    for tool_name, spec in cli_tools.tools.items():
        commands[f"!{tool_name}"] = spec['docstring']
    history = FileHistory("../../chat_history.txt")
    custom_completer = CustomCompleter(commands, history)

    session = PromptSession(
        history=history,
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
        completer=custom_completer,
        complete_while_typing=True,
    )

    console.print(Panel(
        "[bold green]Welcome to the Heare Developer CLI, your personal coding assistant.[/bold green]",
        expand=False))
    console.print("[bold yellow]Available commands:[/bold yellow]")
    for tool_name, spec in cli_tools.tools.items():
        row = f"![bold yellow]{tool_name}"
        if spec['docstring']:
            row += f" - {spec['docstring']}"
        row += "[/bold yellow]"
        console.print(row)
    console.print("[bold yellow]!quit - Quit the chat[/bold yellow]")
    console.print("[bold yellow]!restart - Clear chat history and start over[/bold yellow]")

    chat_history = []
    tool_result_buffer = []
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    total_cost = 0.0

    try:
        while True:
            try:
                if not tool_result_buffer:
                    user_input = session.prompt(FormattedText([('#00FF00', ' > ')]))

                    if user_input.startswith("!"):
                        if user_input == "!quit":
                            break
                        elif user_input == "!restart":
                            chat_history = []
                            tool_result_buffer = []
                            prompt_tokens = 0
                            completion_tokens = 0
                            total_tokens = 0
                            console.print(Panel("[bold green]Chat history cleared. Starting over.[/bold green]"))
                        elif user_input in cli_tools.tools.keys():
                            cli_tool = cli_tools.tools.get(user_input[1:].split()[0])
                            if cli_tool:
                                cli_tool['invoke'](console=console, sandbox=sandbox, user_input=user_input)
                        else:
                            console.print(Panel(f"[bold red]Unknown command: {user_input}[/bold red]"))
                        continue

                    chat_history.append({"role": "user", "content": user_input})
                    console.print(Panel(f"[bold blue]You:[/bold blue] {user_input}", expand=False))

                else:
                    chat_history.append(tool_result_buffer.pop(0))

                system_message = create_system_message(sandbox)
                ai_response = ""
                with console.status("[bold green]AI is thinking...[/bold green]", spinner="dots"):
                    with client.messages.stream(
                            system=system_message,
                            max_tokens=4096,
                            messages=chat_history,
                            model=model['title'],
                            tools=TOOLS_SCHEMA
                    ) as stream:
                        for chunk in stream:
                            if chunk.type == "text":
                                ai_response += chunk.text

                        final_message = stream.get_final_message()
                        chat_history.append({
                            "role": "assistant",
                            "content": final_message.content
                        })

                        # Update token counts
                        prompt_tokens += final_message.usage.input_tokens
                        completion_tokens += final_message.usage.output_tokens
                        total_tokens = prompt_tokens + completion_tokens
                        total_cost += (final_message.usage.input_tokens / 1_000_000.0 * model['pricing']['input']) \
                            + (final_message.usage.output_tokens / 1_000_000.0 * model['pricing']['output'])

                console.print(Panel(f"[bold green]AI Assistant:[/bold green]\n{ai_response}", expand=False))
                console.print(format_token_count(prompt_tokens, completion_tokens, total_tokens, total_cost))

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
            except KeyboardInterrupt:
                console.print("\n[bold yellow]KeyboardInterrupt detected. Press Ctrl+C again to exit, or continue typing to resume.[/bold yellow]")
                continue
    except KeyboardInterrupt:
        pass

    console.print("[bold green]Chat ended. Goodbye![/bold green]")


@cli_tools.tool
def help(console, sandbox, user_input, *args, **kwargs):
    """
    Show help
    """
    help_text = "[bold yellow]Available commands:[/bold yellow]\n"
    help_text += "!restart - Clear chat history and start over\n"
    help_text += "!quit - Quit the chat\n"

    for tool_name, spec in cli_tools.tools.items():
        help_text += f"!{tool_name} - {spec['docstring']} - {spec['args']}\n"

    help_text += "You can ask the AI to read, write, or list files/directories\n"
    help_text += "You can also ask the AI to run bash commands (with some restrictions)"


    console.print(Panel(help_text))


@cli_tools.tool
def add(console, sandbox, user_input, *args, **kwargs):
    """
    Add file or directory to sandbox
    """
    sandbox.add_to_sandbox(user_input[4:].strip())
    tree(console, sandbox)


@cli_tools.tool
def tree(console, sandbox, *args, **kwargs):
    """
    List contents of the sandbox
    """
    sandbox_contents = sandbox.list_sandbox()
    console.print(Panel(
        "[bold cyan]Sandbox contents:[/bold cyan]\n" + "\n".join(f"[cyan]{item}[/cyan]" for item in sandbox_contents)))


if __name__ == "__main__":
    main()
    