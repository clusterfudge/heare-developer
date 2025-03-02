import subprocess

from heare.developer.context import AgentContext
from heare.developer.sandbox import DoSomethingElseError
from .framework import tool


@tool
def python_repl(context: "AgentContext", code: str):
    """Run Python code in a sandboxed environment and return the output.
    This tool allows execution of Python code in a secure, isolated environment.

    For security reasons, the following limitations apply:
    1. No imports of potentially dangerous modules (os, sys, subprocess, etc.)
    2. No file operations (open, read, write)
    3. No use of eval, exec, or other dynamic code execution
    4. No use of __import__ or other import mechanisms

    Available modules and functions:
    - math, random, datetime, json, re
    - Basic built-ins like range, len, str, int, float, etc.
    - Collection operations: list, dict, set, tuple, sum, min, max, etc.
    - Other safe functions: all, any, enumerate, zip, sorted, reversed, etc.

    Example usage:
    ```python
    # Basic math operations
    result = 5 * 10
    print(f"5 * 10 = {result}")

    # Working with collections
    numbers = [1, 2, 3, 4, 5]
    print(f"Sum: {sum(numbers)}")
    print(f"Average: {sum(numbers)/len(numbers)}")

    # Using available modules
    import math
    print(f"Square root of 16: {math.sqrt(16)}")
    ```

    Args:
        code: The Python code to execute
    """
    import io
    import ast
    from contextlib import redirect_stdout, redirect_stderr

    # Security check - prevent potentially harmful operations
    try:
        parsed = ast.parse(code)
        for node in ast.walk(parsed):
            # Prevent imports that could be dangerous
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                for name in node.names:
                    module = name.name.split(".")[0]
                    dangerous_modules = [
                        "os",
                        "subprocess",
                        "sys",
                        "shutil",
                        "importlib",
                        "pickle",
                        "socket",
                        "ctypes",
                        "pty",
                        "posix",
                    ]
                    if module in dangerous_modules:
                        return f"Error: Import of '{module}' is restricted for security reasons."

            # Prevent file operations
            if isinstance(node, (ast.Call)):
                if isinstance(node.func, ast.Name) and node.func.id in [
                    "open",
                    "eval",
                    "exec",
                ]:
                    return f"Error: Function '{node.func.id}' is restricted for security reasons."

                # Check attribute access for file operations
                if isinstance(node.func, ast.Attribute) and node.func.attr in [
                    "read",
                    "write",
                    "open",
                    "exec",
                    "eval",
                ]:
                    return f"Error: Method '{node.func.attr}' is restricted for security reasons."
    except SyntaxError as e:
        return f"Syntax Error: {str(e)}"

    # Capture stdout and stderr
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    # Execute the code
    try:
        # Import modules we want to make available
        import math
        import random
        import datetime
        import json
        import re

        # Set up a controlled globals dictionary with allowed built-ins
        restricted_builtins = ["open", "exec", "eval", "__import__", "compile", "input"]

        # Create a safe namespace with built-in functions and our imported modules
        safe_globals = {
            "math": math,
            "random": random,
            "datetime": datetime,
            "json": json,
            "re": re,
            "range": range,  # Explicitly add range
            "len": len,  # Explicitly add len
            "str": str,  # Explicitly add str
            "int": int,  # Explicitly add int
            "float": float,  # Explicitly add float
            "bool": bool,  # Explicitly add bool
            "list": list,  # Explicitly add list
            "dict": dict,  # Explicitly add dict
            "set": set,  # Explicitly add set
            "tuple": tuple,  # Explicitly add tuple
            "sum": sum,  # Explicitly add sum
            "min": min,  # Explicitly add min
            "max": max,  # Explicitly add max
            "abs": abs,  # Explicitly add abs
            "all": all,  # Explicitly add all
            "any": any,  # Explicitly add any
            "enumerate": enumerate,  # Explicitly add enumerate
            "zip": zip,  # Explicitly add zip
            "sorted": sorted,  # Explicitly add sorted
            "reversed": reversed,  # Explicitly add reversed
            "round": round,  # Explicitly add round
            "divmod": divmod,  # Explicitly add divmod
            "chr": chr,  # Explicitly add chr
            "ord": ord,  # Explicitly add ord
            "__builtins__": {
                name: getattr(__builtins__, name)
                for name in dir(__builtins__)
                if name not in restricted_builtins
            },
        }

        # Add our own safe print function that writes to our buffer
        def safe_print(*args, **kwargs):
            # Remove file if it's in kwargs to ensure it prints to our buffer
            kwargs.pop("file", None)
            # Convert all arguments to strings
            print(*args, file=stdout_buffer, **kwargs)

        safe_globals["print"] = safe_print

        # Execute with redirected stdout/stderr
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(code, safe_globals, {})

        # Get the output
        stdout = stdout_buffer.getvalue()
        stderr = stderr_buffer.getvalue()

        # Format the response
        result = ""
        if stdout:
            result += f"STDOUT:\n{stdout}\n"
        if stderr:
            result += f"STDERR:\n{stderr}\n"

        return (
            result.strip()
            if result.strip()
            else "Code executed successfully with no output."
        )

    except Exception:
        # Get exception and traceback info
        import traceback

        tb = traceback.format_exc()
        return f"Error executing code:\n{tb}"


@tool
def run_bash_command(context: "AgentContext", command: str):
    """Run a bash command in a sandboxed environment with safety checks.

    Args:
        command: The bash command to execute
    """
    try:
        # Check for potentially dangerous commands
        dangerous_commands = [
            r"\brm\b",
            r"\bmv\b",
            r"\bcp\b",
            r"\bchown\b",
            r"\bsudo\b",
            r">",
            r">>",
        ]
        import re

        if any(re.search(cmd, command) for cmd in dangerous_commands):
            return "Error: This command is not allowed for safety reasons."

        try:
            if not context.sandbox.check_permissions("shell", command):
                return "Error: Operator denied permission."
        except DoSomethingElseError:
            raise  # Re-raise to be handled by higher-level components

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
