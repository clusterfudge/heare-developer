import os
import time
import random
from functools import partial

import anthropic
from anthropic.types import TextBlock
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.panel import Panel

from heare.developer.utils import archive_chat, CustomCompleter
from heare.developer.prompt import create_system_message
from heare.developer.sandbox import Sandbox
from heare.developer.tools import TOOLS_SCHEMA, handle_tool_use


def retry_with_exponential_backoff(func, max_retries=5, base_delay=1, max_delay=60):
    def wrapper(*args, **kwargs):
        retries = 0
        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except (
                anthropic.RateLimitError,
                anthropic.APIError,
                anthropic.APIStatusError,
            ) as e:
                if isinstance(e, anthropic.APIError) and e.status_code not in [
                    429,
                    500,
                    503,
                    529,
                ]:
                    raise
                retries += 1
                if retries == max_retries:
                    raise
                delay = min(base_delay * (2**retries) + random.uniform(0, 1), max_delay)
                print(
                    f"Rate limit, server error, or overload encountered. Retrying in {delay:.2f} seconds..."
                )
                time.sleep(delay)
        return func(*args, **kwargs)

    return wrapper


def run(
    model,
    sandbox_contents,
    sandbox_mode,
    cli_tools,
    permission_check_callback,
    render_tool_use,
    format_token_count,
):
    load_dotenv()
    console = Console()

    if sandbox_contents:
        sandbox = Sandbox(
            sandbox_contents[0],
            mode=sandbox_mode,
            permission_check_callback=partial(permission_check_callback, console),
        )
    else:
        sandbox = Sandbox(
            os.getcwd(),
            mode=sandbox_mode,
            permission_check_callback=partial(permission_check_callback, console),
        )

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error: ANTHROPIC_API_KEY environment variable not set[/bold red]"
        )
        return

    client = anthropic.Client(api_key=api_key)

    commands = {
        "!quit": "Quit the chat",
        "!exit": "Quit the chat",
        "!restart": "Clear chat history and start over",
    }
    for tool_name, spec in cli_tools.tools.items():
        commands[f"!{tool_name}"] = spec["docstring"]
    history = FileHistory("./chat_history.txt")
    custom_completer = CustomCompleter(commands, history)

    session = PromptSession(
        history=history,
        auto_suggest=AutoSuggestFromHistory(),
        enable_history_search=True,
        completer=custom_completer,
        complete_while_typing=True,
    )

    console.print(
        Panel(
            "[bold green]Welcome to the Heare Developer CLI, your personal coding assistant.[/bold green]",
            expand=False,
        )
    )
    console.print("[bold yellow]Available commands:[/bold yellow]")
    for tool_name, spec in cli_tools.tools.items():
        row = f"![bold yellow]{tool_name}"
        if spec["docstring"]:
            row += f" - {spec['docstring']}"
        row += "[/bold yellow]"
        console.print(row)
    console.print("[bold yellow]!quit, !exit - Quit the chat[/bold yellow]")
    console.print(
        "[bold yellow]!restart - Clear chat history and start over[/bold yellow]"
    )

    chat_history = []
    tool_result_buffer = []
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    total_cost = 0.0

    interrupt_count = 0
    last_interrupt_time = 0

    while True:
        try:
            if not tool_result_buffer:
                user_input = session.prompt(FormattedText([("#00FF00", " > ")]))

                # Handle multi-line input
                if user_input.strip() == "{":
                    multi_line_input = []
                    while True:
                        line = session.prompt(FormattedText([("#00FF00", "... ")]))
                        if line.strip() == "}":
                            break
                        multi_line_input.append(line)
                    user_input = "\n".join(multi_line_input)

                command_name = (
                    user_input.split()[0][1:] if user_input.startswith("!") else ""
                )

                if user_input.startswith("!"):
                    if user_input in ["!quit", "!exit"]:
                        break
                    elif user_input == "!restart":
                        chat_history = []
                        tool_result_buffer = []
                        prompt_tokens = 0
                        completion_tokens = 0
                        total_tokens = 0
                        total_cost = 0.0
                        console.print(
                            Panel(
                                "[bold green]Chat history cleared. Starting over.[/bold green]"
                            )
                        )
                    elif user_input.startswith("!archive"):
                        archive_chat(
                            console=console,
                            sandbox=sandbox,
                            user_input=user_input,
                            chat_history=chat_history,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens,
                            total_cost=total_cost,
                        )
                    elif command_name in cli_tools.tools.keys():
                        cli_tool = cli_tools.get_tool(command_name)
                        if cli_tool:
                            cli_tool["invoke"](
                                console=console,
                                sandbox=sandbox,
                                user_input=user_input,
                                chat_history=chat_history,
                                tool_result_buffer=tool_result_buffer,
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                total_tokens=total_tokens,
                                total_cost=total_cost,
                            )
                    else:
                        console.print(
                            Panel(f"[bold red]Unknown command: {user_input}[/bold red]")
                        )
                    continue

                chat_history.append({"role": "user", "content": user_input})
                console.print(
                    Panel(f"[bold blue]You:[/bold blue] {user_input}", expand=False)
                )

            else:
                chat_history.append(tool_result_buffer.pop(0))

            system_message = create_system_message(sandbox)
            ai_response = ""
            with console.status(
                "[bold green]AI is thinking...[/bold green]", spinner="dots"
            ):

                @retry_with_exponential_backoff
                def stream_messages():
                    return client.messages.stream(
                        system=system_message,
                        max_tokens=4096,
                        messages=chat_history,
                        model=model["title"],
                        tools=TOOLS_SCHEMA,
                    )

                with stream_messages() as stream:
                    for chunk in stream:
                        if chunk.type == "text":
                            ai_response += chunk.text

                    final_message = stream.get_final_message()

                    final_content = final_message.content
                    filtered = []
                    if isinstance(final_content, list):
                        for message in final_content:
                            if isinstance(message, TextBlock):
                                message.text = message.text.strip()

                                # skipping empty text block from llm
                                if not message.text:
                                    continue

                            filtered.append(message)
                    else:
                        filtered = final_content

                    chat_history.append({"role": "assistant", "content": filtered})

                    # Update token counts
                    prompt_tokens += final_message.usage.input_tokens
                    completion_tokens += final_message.usage.output_tokens
                    total_tokens = prompt_tokens + completion_tokens
                    total_cost += (
                        final_message.usage.input_tokens
                        / 1_000_000.0
                        * model["pricing"]["input"]
                    ) + (
                        final_message.usage.output_tokens
                        / 1_000_000.0
                        * model["pricing"]["output"]
                    )

            console.print(
                Panel(
                    f"[bold green]AI Assistant:[/bold green]\n{ai_response}",
                    expand=False,
                )
            )
            console.print(
                format_token_count(
                    prompt_tokens, completion_tokens, total_tokens, total_cost
                )
            )

            if final_message.stop_reason == "tool_use":
                results = handle_tool_use(sandbox, final_message)

                tool_result_buffer.append({"role": "user", "content": results})
                render_tool_use(console, final_message, results)
            elif final_message.stop_reason == "max_tokens":
                console.print(Panel("[bold red]Hit max tokens.[/bold red]"))

            # Reset interrupt count after successful interaction
            interrupt_count = 0
            last_interrupt_time = 0

        except KeyboardInterrupt:
            current_time = time.time()
            if (
                current_time - last_interrupt_time < 1
            ):  # If less than 1 second has passed
                interrupt_count += 1
            else:
                interrupt_count = 1
            last_interrupt_time = current_time

            if interrupt_count >= 2:
                console.print(
                    "\n[bold red]Double interrupt detected. Exiting...[/bold red]"
                )
                break
            else:
                console.print(
                    "\n[bold yellow]KeyboardInterrupt detected. Press Ctrl+C again to exit, or continue typing to resume.[/bold yellow]"
                )

    console.print("[bold green]Chat ended. Goodbye![/bold green]")
