import os
import time
import random
from datetime import datetime, timezone

import anthropic
from anthropic.types import TextBlock
from dotenv import load_dotenv

from heare.developer.prompt import create_system_message
from heare.developer.sandbox import Sandbox
from heare.developer.toolbox import Toolbox
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
    initial_prompt: str = None,
    single_response: bool = False,
):
    load_dotenv()

    sandbox = Sandbox(
        sandbox_contents[0] if sandbox_contents else os.getcwd(),
        mode=sandbox_mode,
        permission_check_callback=user_interface.permission_callback,
        permission_check_rendering_callback=user_interface.permission_rendering_callback,
    )
    toolbox = Toolbox(sandbox)
    if hasattr(user_interface, "set_toolbox"):
        user_interface.set_toolbox(toolbox)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        user_interface.handle_system_message(
            "[bold red]Error: ANTHROPIC_API_KEY environment variable not set[/bold red]"
        )
        return

    client = anthropic.Client(api_key=api_key)
    rate_limiter = RateLimiter()

    if not single_response:
        commands = {
            "/quit": "Quit the chat",
            "/exit": "Quit the chat",
            "/restart": "Clear chat history and start over",
        }
        for tool_name, spec in toolbox.local.items():
            commands[f"/{tool_name}"] = spec["docstring"]

        command_message = "[bold yellow]Available commands:[/bold yellow]\n"

        for tool_name, spec in toolbox.local.items():
            command_message += (
                f"[bold yellow]/{tool_name}: {spec['docstring']}[/bold yellow]\n"
            )

        command_message += "[bold yellow]/quit, /exit - Quit the chat[/bold yellow]\n"

        command_message += (
            "[bold yellow]/restart - Clear chat history and start over[/bold yellow]\n"
        )

        user_interface.handle_system_message(command_message)

    chat_history = []
    tool_result_buffer = []
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    total_cost = 0.0

    interrupt_count = 0
    last_interrupt_time = 0

    # Handle initial prompt if provided
    if initial_prompt:
        chat_history.append({"role": "user", "content": initial_prompt})
        user_interface.handle_user_input(
            f"[bold blue]You:[/bold blue] {initial_prompt}"
        )

    while True:
        try:
            if not tool_result_buffer and not initial_prompt:
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
                        tool = toolbox.local.get("archive")
                        if tool:
                            tool["invoke"](
                                user_interface=user_interface,
                                sandbox=sandbox,
                                user_input=user_input,
                                chat_history=chat_history,
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                total_tokens=total_tokens,
                                total_cost=total_cost,
                            )
                    elif command_name in toolbox.local:
                        tool = toolbox.local.get(command_name)
                        if tool:
                            tool["invoke"](
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
                user_interface.handle_user_input(
                    f"[bold blue]You:[/bold blue] {user_input}"
                )

            else:
                if tool_result_buffer:
                    chat_history.append(
                        {"role": "user", "content": tool_result_buffer.copy()}
                    )
                    tool_result_buffer.clear()
                initial_prompt = None

            system_message = create_system_message(sandbox)
            ai_response = ""
            with user_interface.status(
                "[bold green]AI is thinking...[/bold green]", spinner="dots"
            ):
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
                            tools=toolbox.agent_schema,
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
                            user_interface.handle_system_message(
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

            user_interface.handle_assistant_message(ai_response)
            user_interface.display_token_count(
                prompt_tokens, completion_tokens, total_tokens, total_cost
            )

            if final_message.stop_reason == "tool_use":
                for part in final_message.content:
                    if part.type == "tool_use":
                        user_interface.handle_tool_use(part.name, part.input)
                        result = toolbox.invoke_agent_tool(part)
                        tool_result_buffer.append(result)
                        user_interface.handle_tool_result(part.name, result)
            elif final_message.stop_reason == "max_tokens":
                user_interface.handle_assistant_message(
                    "[bold red]Hit max tokens.[/bold red]"
                )

            interrupt_count = 0
            last_interrupt_time = 0

            # Exit after one response if in single-response mode
            if single_response and not tool_result_buffer:
                break

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
