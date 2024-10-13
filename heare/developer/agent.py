import os
import time
import random
from datetime import datetime, timezone

import anthropic
from anthropic.types import TextBlock
from dotenv import load_dotenv

from heare.developer.utils import archive_chat
from heare.developer.prompt import create_system_message
from heare.developer.sandbox import Sandbox
from heare.developer.tools import TOOLS_SCHEMA, invoke_took
from heare.developer.user_interface import UserInterface


class RateLimiter:
    def __init__(self):
        self.tokens_remaining = None
        self.reset_time = None

    def update(self, headers):
        self.tokens_remaining = int(
            headers.get("anthropic-ratelimit-tokens-remaining", 0)
        )
        reset_time_str = headers.get("anthropic-ratelimit-tokens-reset")
        if reset_time_str:
            self.reset_time = datetime.fromisoformat(reset_time_str).replace(
                tzinfo=timezone.utc
            )

    def check_and_wait(self):
        if self.tokens_remaining is not None and self.tokens_remaining < 1000:
            if self.reset_time:
                current_time = datetime.now(timezone.utc)
                wait_time = max(0, (self.reset_time - current_time).total_seconds())
                if wait_time > 0:
                    print(
                        f"Rate limit approaching. Waiting for {wait_time:.2f} seconds until reset."
                    )
                    time.sleep(wait_time)
            else:
                print("Rate limit approaching. Waiting for 60 seconds.")
                time.sleep(60)


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
    user_interface: UserInterface,
):
    load_dotenv()

    if sandbox_contents:
        sandbox = Sandbox(
            sandbox_contents[0],
            mode=sandbox_mode,
            permission_check_callback=user_interface.permission_callback,
        )
    else:
        sandbox = Sandbox(
            os.getcwd(),
            mode=sandbox_mode,
            permission_check_callback=user_interface.permission_callback,
        )

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        user_interface.handle_assistant_message(
            "[bold red]Error: ANTHROPIC_API_KEY environment variable not set[/bold red]"
        )
        return

    client = anthropic.Client(api_key=api_key)
    rate_limiter = RateLimiter()

    commands = {
        "/quit": "Quit the chat",
        "/exit": "Quit the chat",
        "/restart": "Clear chat history and start over",
    }
    for tool_name, spec in cli_tools.tools.items():
        commands[f"/{tool_name}"] = spec["docstring"]

    user_interface.handle_assistant_message(
        "[bold yellow]Available commands:[/bold yellow]"
    )
    for tool_name, spec in cli_tools.tools.items():
        user_interface.handle_assistant_message(
            f"/[bold yellow]{tool_name} - {spec['docstring']}[/bold yellow]"
        )
    user_interface.handle_assistant_message(
        "[bold yellow]/quit, /exit - Quit the chat[/bold yellow]"
    )
    user_interface.handle_assistant_message(
        "[bold yellow]/restart - Clear chat history and start over[/bold yellow]"
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
                user_input = user_interface.get_user_input(" > ")

                command_name = (
                    user_input.split()[0][1:] if user_input.startswith("/") else ""
                )

                if user_input.startswith("/"):
                    if user_input in ["/quit", "/exit"]:
                        break
                    elif user_input == "/restart":
                        chat_history = []
                        tool_result_buffer = []
                        prompt_tokens = 0
                        completion_tokens = 0
                        total_tokens = 0
                        total_cost = 0.0
                        user_interface.handle_assistant_message(
                            "[bold green]Chat history cleared. Starting over.[/bold green]"
                        )
                    elif user_input.startswith("/archive"):
                        archive_chat(
                            user_interface=user_interface,
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
                                user_interface=user_interface,
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
                        user_interface.handle_assistant_message(
                            f"[bold red]Unknown command: {user_input}[/bold red]"
                        )
                    continue

                chat_history.append({"role": "user", "content": user_input})
                user_interface.handle_assistant_message(
                    f"[bold blue]You:[/bold blue] {user_input}"
                )

            else:
                chat_history.append(
                    {"role": "user", "content": tool_result_buffer.copy()}
                )
                tool_result_buffer.clear()

            system_message = create_system_message(sandbox)
            ai_response = ""
            user_interface.handle_assistant_message(
                "[bold green]AI is thinking...[/bold green]"
            )

            max_retries = 5
            base_delay = 1
            max_delay = 60

            for attempt in range(max_retries):
                try:
                    rate_limiter.check_and_wait()

                    with client.messages.stream(
                        system=system_message,
                        max_tokens=4096,
                        messages=chat_history,
                        model=model["title"],
                        tools=TOOLS_SCHEMA,
                    ) as stream:
                        for chunk in stream:
                            if chunk.type == "text":
                                ai_response += chunk.text

                        final_message = stream.get_final_message()

                    rate_limiter.update(stream.response.headers)
                    break
                except anthropic.APIStatusError as e:
                    if attempt == max_retries - 1:
                        raise
                    if "Overloaded" in str(e):
                        delay = min(
                            base_delay * (2**attempt) + random.uniform(0, 1),
                            max_delay,
                        )
                        user_interface.handle_assistant_message(
                            f"API overloaded. Retrying in {delay:.2f} seconds..."
                        )
                        time.sleep(delay)
                    else:
                        raise

            final_content = final_message.content
            filtered = []
            if isinstance(final_content, list):
                for message in final_content:
                    if isinstance(message, TextBlock):
                        message.text = message.text.strip()
                        if not message.text:
                            continue
                    filtered.append(message)
            else:
                filtered = final_content

            chat_history.append({"role": "assistant", "content": filtered})

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

            user_interface.handle_assistant_message(
                f"[bold green]AI Assistant:[/bold green]\n{ai_response}"
            )
            user_interface.display_token_count(
                prompt_tokens, completion_tokens, total_tokens, total_cost
            )

            if final_message.stop_reason == "tool_use":
                for part in final_message.content:
                    if part.type == "tool_use":
                        tool_use = part
                        result = invoke_took(sandbox, tool_use)
                        tool_result_buffer.append(result)
                        user_interface.handle_tool_result(tool_use.name, tool_use.name)
            elif final_message.stop_reason == "max_tokens":
                user_interface.handle_assistant_message(
                    "[bold red]Hit max tokens.[/bold red]"
                )

            interrupt_count = 0
            last_interrupt_time = 0

        except KeyboardInterrupt:
            current_time = time.time()
            if current_time - last_interrupt_time < 1:
                interrupt_count += 1
            else:
                interrupt_count = 1
            last_interrupt_time = current_time

            if interrupt_count >= 2:
                user_interface.handle_system_message(
                    "[bold red]Double interrupt detected. Exiting...[/bold red]"
                )
                break
            else:
                user_interface.handle_system_message(
                    "[bold yellow]"
                    "KeyboardInterrupt detected. Press Ctrl+C again to exit, or continue typing to resume."
                    "[/bold yellow]"
                )
