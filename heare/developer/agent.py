import copy
import os
import time
import random
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

import anthropic
from anthropic.types import TextBlock, MessageParam
from dotenv import load_dotenv

from heare.developer.context import AgentContext
from heare.developer.prompt import create_system_message
from heare.developer.rate_limiter import RateLimiter
from heare.developer.toolbox import Toolbox
from heare.developer.sandbox import DoSomethingElseError


def retry_with_exponential_backoff(func, max_retries=5, base_delay=1, max_delay=60):
    def wrapper(*args, **kwargs):
        retries = 0
        rate_limiter = RateLimiter()

        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except anthropic.RateLimitError as e:
                # Special handling for rate limit errors to respect Anthropic's tokens reset time
                retries += 1
                if retries == max_retries:
                    raise

                # Extract information from the rate limit error
                backoff_time = rate_limiter.handle_rate_limit_error(e)

                print(
                    f"Rate limit error encountered. Retrying in {backoff_time:.2f} seconds... (Attempt {retries}/{max_retries})"
                )
                # Wait time is already handled in handle_rate_limit_error

            except (anthropic.APIError, anthropic.APIStatusError) as e:
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
                    f"Server error or overload encountered. Retrying in {delay:.2f} seconds... (Attempt {retries}/{max_retries})"
                )
                time.sleep(delay)

        return func(*args, **kwargs)

    return wrapper


def _extract_file_mentions(message: MessageParam) -> list[Path]:
    """Extract file mentions from a message that start with @ and resolve to actual files.

    File mentions are substrings that:
    - Start with @
    - Contain no breaks or backslash escapes
    - Resolve to an actual file on the filesystem

    Note: This function only extracts the file mentions but does not read the files.
    Access to file contents is controlled by the sandbox when this is used in
    combination with other functions.

    Args:
        message: The message to extract file mentions from

    Returns:
        List of Path objects for files that were mentioned and exist
    """
    if isinstance(message["content"], str):
        content = message["content"]
    elif isinstance(message["content"], list):
        # For messages with multiple content blocks, concatenate text blocks
        content = " ".join(
            block["text"]
            for block in message["content"]
            if isinstance(block, dict) and "text" in block
        )
    else:
        return []

    # Split on whitespace and get tokens starting with @
    words = content.split()
    # Get words starting with @ and strip trailing period if present
    file_mentions = [word[1:].rstrip(".") for word in words if word.startswith("@")]

    # Convert to paths and filter to existing files
    paths = [Path(mention) for mention in file_mentions]
    return [path for path in paths if path.exists()]


def _inline_latest_file_mentions(
    chat_history: list[MessageParam],
) -> list[MessageParam]:
    """Process file mentions in chat history and inline their contents into the messages.

    This function operates outside the sandbox system, treating @ mentions as explicit
    permission to read the referenced files. This is in contrast to other file operations
    that require sandbox permission checks.

    Security Note: This direct file access could potentially be exploited if code is
    copy/pasted into the system or if a sub-agent tool is used where the user message
    originates from a higher-level agent. Care should be taken when processing file
    mentions from untrusted sources.

    Args:
        chat_history: List of message parameters from the conversation history

    Returns:
        Modified chat history with file contents inlined into the messages
    """
    file_mention_map: dict[Path, list[int]] = defaultdict(list)
    # Make a deep copy of the chat history to ensure we don't modify the original
    results: list[MessageParam] = []

    # First, make a direct deep copy of each message
    for idx, message in enumerate(chat_history):
        message_copy = copy.deepcopy(message)
        results.append(message_copy)

        if message["role"] == "user":
            file_mentions = _extract_file_mentions(message)
            for file_mention in file_mentions:
                file_mention_map[file_mention].append(idx)

    # Now update the messages with file contents
    for mentioned_file, message_indexes in file_mention_map.items():
        last_index = message_indexes[-1]
        message_to_update = results[last_index]

        # Read the file content
        try:
            with open(mentioned_file, "r") as f:
                file_content = f.read()
        except Exception as e:
            print(f"Warning: Could not read file {mentioned_file}: {e}")
            continue

        # Format the file content block
        relative_path = mentioned_file.as_posix()
        file_block = (
            f"<mentioned_file path={relative_path}>\n{file_content}\n</mentioned_file>"
        )

        # Convert message content to list format if it's a string
        if isinstance(message_to_update["content"], str):
            message_to_update["content"] = [
                {"type": "text", "text": message_to_update["content"]}
            ]

        # Add the file content as a new text block
        message_to_update["content"].append({"type": "text", "text": file_block})

    # HACK: we just happen to be seeing messages go past, so we'll handle cache_control here.
    # Add cache_control to the last text block in a user message, ensuring all content is list-type
    if results and results[-1]["role"] == "user":
        last_message = results[-1]
        # Ensure content is in the proper list format
        if isinstance(last_message["content"], str):
            last_message["content"] = [
                {"type": "text", "text": last_message["content"]}
            ]

        if len(last_message["content"]) > 0:
            # Only add cache_control to the last text block
            if isinstance(last_message["content"][-1], dict):
                last_message["content"][-1]["cache_control"] = {"type": "ephemeral"}
    return results


def run(
    agent_context: AgentContext,
    initial_prompt: str = None,
    single_response: bool = False,
    tool_names: list[str] | None = None,
    system_prompt: dict[str, Any] | None = None,
) -> list[MessageParam]:
    load_dotenv()
    user_interface, model = (
        agent_context.user_interface,
        agent_context.model_spec,
    )
    toolbox = Toolbox(agent_context, tool_names=tool_names)
    if hasattr(user_interface, "set_toolbox"):
        user_interface.set_toolbox(toolbox)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        user_interface.handle_system_message(
            "[bold red]Error: ANTHROPIC_API_KEY environment variable not set[/bold red]"
        )
        return []

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

        command_message = "## Available commands:\n"

        for tool_name, spec in toolbox.local.items():
            command_message += f"- **/{tool_name}**: {spec['docstring']}\n"

        command_message += "- **/quit, /exit** - Quit the chat\n"

        command_message += "- **/restart** - Clear chat history and start over\n"

        user_interface.handle_system_message(command_message)

    chat_history: list[MessageParam] = []
    tool_result_buffer = []

    interrupt_count = 0
    last_interrupt_time = 0

    # Handle initial prompt if provided
    if initial_prompt:
        chat_history.append(
            {"role": "user", "content": [{"type": "text", "text": initial_prompt}]}
        )
        user_interface.handle_user_input(
            f"[bold blue]You:[/bold blue] {initial_prompt}"
        )

    while True:
        try:
            if chat_history and chat_history[-1]["role"] == "user":
                pass
            elif not tool_result_buffer and not single_response and not initial_prompt:
                cost = f"${agent_context.usage_summary()['total_cost']:.2f}"
                user_input = ""
                while not user_input.strip():
                    user_input = user_interface.get_user_input(f"{cost} > ")

                command_name = (
                    user_input.split()[0][1:] if user_input.startswith("/") else ""
                )

                if user_input.startswith("/"):
                    if user_input in ["/quit", "/exit"]:
                        break
                    elif user_input == "/restart":
                        chat_history = []
                        tool_result_buffer = []
                        # Generate a new session ID for the agent context
                        agent_context.session_id = str(uuid4())
                        user_interface.handle_assistant_message(
                            "[bold green]Chat history cleared and new session started.[/bold green]"
                        )
                    elif command_name in toolbox.local:
                        tool = toolbox.local.get(command_name)
                        if tool:
                            result, append = toolbox.invoke_cli_tool(
                                name=command_name,
                                arg_str=user_input[len(command_name) + 1 :].strip(),
                                chat_history=chat_history,
                            )
                            if append:
                                tool_result_buffer.append(
                                    {"type": "text", "text": result}
                                )
                    else:
                        user_interface.handle_assistant_message(
                            f"[bold red]Unknown command: {user_input}[/bold red]"
                        )
                    continue

                chat_history.append(
                    {"role": "user", "content": [{"type": "text", "text": user_input}]}
                )
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

            system_message = create_system_message(
                agent_context, system_section=system_prompt
            )
            ai_response = ""
            with user_interface.status(
                "[bold green]AI is thinking...[/bold green]", spinner="dots"
            ):
                max_retries = 5
                base_delay = 1
                max_delay = 60

                for attempt in range(max_retries):
                    try:
                        rate_limiter.check_and_wait(user_interface)
                        messages = _inline_latest_file_mentions(chat_history)
                        with client.messages.stream(
                            system=system_message,
                            max_tokens=model["max_tokens"],
                            messages=messages,
                            model=model["title"],
                            tools=toolbox.agent_schema,
                        ) as stream:
                            for chunk in stream:
                                if chunk.type == "text":
                                    ai_response += chunk.text

                            final_message = stream.get_final_message()

                        rate_limiter.update(stream.response.headers)
                        break
                    except anthropic.RateLimitError as e:
                        # Handle rate limit errors specifically
                        backoff_time = rate_limiter.handle_rate_limit_error(e)
                        if attempt == max_retries - 1:
                            user_interface.handle_system_message(
                                "[bold red]Rate limit exceeded. Max retries reached. Please try again later.[/bold red]"
                            )
                            raise

                        user_interface.handle_system_message(
                            f"[bold yellow]Rate limit exceeded. Retrying in {backoff_time:.2f} seconds... (Attempt {attempt+1}/{max_retries})[/bold yellow]"
                        )
                        # Wait time is already set in handle_rate_limit_error
                        continue

                    except anthropic.APIStatusError as e:
                        rate_limiter.update(e.response.headers)
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

            agent_context.report_usage(final_message.usage)
            usage_summary = agent_context.usage_summary()
            user_interface.handle_assistant_message(ai_response)
            user_interface.display_token_count(
                usage_summary["total_input_tokens"],
                usage_summary["total_output_tokens"],
                usage_summary["total_input_tokens"]
                + usage_summary["total_output_tokens"],
                usage_summary["total_cost"],
                cached_tokens=usage_summary["cached_tokens"],
            )

            if final_message.stop_reason == "tool_use":
                for part in final_message.content:
                    if part.type == "tool_use":
                        user_interface.handle_tool_use(part.name, part.input)
                        try:
                            result = toolbox.invoke_agent_tool(part)
                            tool_result_buffer.append(result)
                            user_interface.handle_tool_result(part.name, result)
                        except DoSomethingElseError:
                            # Handle "do something else" workflow:
                            # 1. Remove the last assistant message
                            if chat_history and chat_history[-1]["role"] == "assistant":
                                chat_history.pop()

                            # 2. Get user's alternate prompt
                            user_interface.handle_system_message(
                                "You selected 'do something else'. Please enter what you'd like to do instead:"
                            )
                            alternate_prompt = user_interface.get_user_input()

                            # 3. Append alternate prompt to the last user message
                            for i in reversed(range(len(chat_history))):
                                if chat_history[i]["role"] == "user":
                                    # Add the alternate prompt to the previous user message
                                    if isinstance(chat_history[i]["content"], str):
                                        chat_history[i]["content"] += (
                                            f"\n\nI viewed your response, and have updated my instructions: {alternate_prompt}"
                                        )
                                    elif isinstance(chat_history[i]["content"], list):
                                        # Handle content as list of blocks
                                        chat_history[i]["content"].append(
                                            {
                                                "type": "text",
                                                "text": f"I viewed your response, and have updated my instructions: {alternate_prompt}",
                                            }
                                        )
                                    break

                            # Clear the tool result buffer to avoid processing the current tool request
                            tool_result_buffer.clear()

                            # Skip to the next iteration to immediately process the updated chat history
                            # instead of breaking out of the loop which would wait for next user input
                            continue
            elif final_message.stop_reason == "max_tokens":
                user_interface.handle_assistant_message(
                    "[bold red]Hit max tokens.[/bold red]"
                )

            interrupt_count = 0
            last_interrupt_time = 0

            # Exit after one response if in single-response mode
            if single_response and not tool_result_buffer:
                agent_context.flush(_inline_latest_file_mentions(chat_history))
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
        finally:
            agent_context.flush(chat_history)
    return chat_history
