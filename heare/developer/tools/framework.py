import inspect
from functools import wraps
from typing import get_origin, Union, get_args, List, Callable

import anthropic

from heare.developer.context import AgentContext


def tool(func):
    """Decorator that adds a schema method to a function and validates sandbox parameter"""
    # Validate that first parameter is context: AgentContext
    sig = inspect.signature(func)
    params = list(sig.parameters.items())
    if not params or params[0][0] != "context":
        raise ValueError(f"First parameter of {func.__name__} must be 'context'")

    type_hints = inspect.get_annotations(func)
    if type_hints.get("context") not in ("AgentContext", AgentContext):
        raise ValueError(
            f"First parameter of {func.__name__} must be annotated with 'AgentContext' type"
        )

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    def schema():
        # Parse the docstring to get description and param docs
        docstring = inspect.getdoc(func)
        if docstring:
            # Split into description and param sections
            parts = docstring.split("\n\nArgs:")
            description = parts[0].strip()

            param_docs = {}
            if len(parts) > 1:
                param_section = parts[1].strip()
                # Parse each parameter description
                for line in param_section.split("\n"):
                    line = line.strip()
                    if line and ":" in line:
                        param_name, param_desc = line.split(":", 1)
                        param_docs[param_name.strip()] = param_desc.strip()
        else:
            description = ""
            param_docs = {}

        # Get type hints
        type_hints = inspect.get_annotations(func)

        # Create schema
        schema = {
            "name": func.__name__,
            "description": description,
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }

        # Process parameters
        sig = inspect.signature(func)
        for param_name, param in sig.parameters.items():
            if param_name == "context":  # Skip context parameter
                continue

            # Check if parameter is optional
            type_hint = type_hints.get(param_name)
            is_optional = False
            if type_hint is not None:
                origin = get_origin(type_hint)
                if origin is Union:
                    args = get_args(type_hint)
                    is_optional = type(None) in args

            if not is_optional:
                schema["input_schema"]["required"].append(param_name)

            # Get parameter description from docstring
            param_desc = param_docs.get(param_name, "")

            # Add to properties with proper type detection
            param_type = "string"  # Default type

            # Determine proper type based on type hint
            if param_name in type_hints:
                hint = type_hints[param_name]
                # Handle Union types (like Optional)
                if get_origin(hint) is Union:
                    args = get_args(hint)
                    # Get the non-None type for Optional
                    hint = next((arg for arg in args if arg is not type(None)), hint)

                # Map Python types to JSON Schema types
                if hint in (int, int) or (
                    isinstance(hint, type) and issubclass(hint, int)
                ):
                    param_type = "integer"
                elif hint in (float,) or (
                    isinstance(hint, type) and issubclass(hint, float)
                ):
                    param_type = "number"

            schema["input_schema"]["properties"][param_name] = {
                "type": param_type,
                "description": param_desc,
            }

        return schema

    wrapper.schema = schema
    return wrapper


def invoke_tool(context: "AgentContext", tool_use, tools: List[Callable] = None):
    """Invoke a tool based on the tool_use specification.

    Args:
        context: The agent's context
        tool_use: The tool use specification containing name, input, and id
        tools: List of tool functions to use. Defaults to ALL_TOOLS.
    """
    if tools is None:
        from heare.developer.tools import ALL_TOOLS

        tools = ALL_TOOLS

    function_name = tool_use.name
    arguments = tool_use.input

    # Create a mapping of tool names to functions
    tool_map = {func.__name__: func for func in tools}

    # Look up the tool function
    tool_func = tool_map.get(function_name)
    if tool_func is None:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": f"Unknown function: {function_name}",
        }

    # Convert arguments to the correct type based on function annotations
    converted_args = {}
    type_hints = inspect.get_annotations(tool_func)

    for arg_name, arg_value in arguments.items():
        if arg_name in type_hints:
            hint = type_hints[arg_name]
            # Handle Union types (like Optional)
            if get_origin(hint) is Union:
                args = get_args(hint)
                # Get the non-None type for Optional
                hint = next((arg for arg in args if arg is not type(None)), hint)

            # Convert string to appropriate type
            if hint == int and isinstance(arg_value, str):  # noqa: E721
                try:
                    converted_args[arg_name] = int(arg_value)
                except ValueError:
                    return {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": f"Error: Parameter '{arg_name}' must be an integer, got '{arg_value}'",
                    }
            elif hint == float and isinstance(arg_value, str):  # noqa: E721
                try:
                    converted_args[arg_name] = float(arg_value)
                except ValueError:
                    return {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": f"Error: Parameter '{arg_name}' must be a number, got '{arg_value}'",
                    }
            else:
                converted_args[arg_name] = arg_value
        else:
            converted_args[arg_name] = arg_value

    # Call the tool function with the sandbox and converted arguments
    result = tool_func(context, **converted_args)

    return {"type": "tool_result", "tool_use_id": tool_use.id, "content": result}


def _call_anthropic_with_retry(
    context: "AgentContext",
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    model: str = "claude-sonnet-3-7.latest",
    temperature: float = 0,
):
    """Helper function to call Anthropic API with retry logic.

    Args:
        context: The agent context for reporting usage
        model: The model name to use
        system_prompt: The system prompt
        user_prompt: The user prompt
        max_tokens: Maximum number of tokens to generate
        temperature: Temperature for generation, defaults to 0
    """
    # Retry with exponential backoff
    max_retries = 5
    base_delay = 1
    max_delay = 60
    import time
    import random

    client = anthropic.Anthropic()

    for attempt in range(max_retries):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # Report usage if context is provided
            if context:
                context.report_usage(
                    message.usage,
                    {
                        "title": model,
                        "pricing": {"input": 0.80, "output": 4.00},
                        "cache_pricing": {"write": 1.00, "read": 0.08},
                        "max_tokens": 8192,
                    },
                )

            return message
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
            if attempt == max_retries - 1:
                raise
            delay = min(base_delay * (2**attempt) + random.uniform(0, 1), max_delay)
            print(
                f"Rate limit, server error, or overload encountered. Retrying in {delay:.2f} seconds..."
            )
            time.sleep(delay)
