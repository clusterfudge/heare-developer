#!/usr/bin/env python3
"""
Simple test script for the interactive timeout functionality.
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import heare modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heare.developer.context import AgentContext
from heare.developer.sandbox import SandboxMode
from heare.developer.user_interface import UserInterface
from heare.developer.tools.repl import run_bash_command


class TestUserInterface(UserInterface):
    """Test user interface that simulates user input."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.response_index = 0
        self.messages = []

    def handle_assistant_message(self, message: str) -> None:
        print(f"ASSISTANT: {message}")

    def handle_system_message(self, message: str, markdown=True) -> None:
        print(f"SYSTEM: {message}")
        self.messages.append(("system", message))

    def permission_callback(
        self, action: str, resource: str, sandbox_mode: SandboxMode, action_arguments
    ):
        return True  # Always allow for testing

    def permission_rendering_callback(
        self, action: str, resource: str, action_arguments
    ):
        pass

    def handle_tool_use(self, tool_name: str, tool_params):
        print(f"TOOL USE: {tool_name} with {tool_params}")

    def handle_tool_result(self, name: str, result):
        print(f"TOOL RESULT: {name} -> {result}")

    async def get_user_input(self, prompt: str = "") -> str:
        print(f"PROMPT: {prompt}")
        if self.response_index < len(self.responses):
            response = self.responses[self.response_index]
            self.response_index += 1
            print(f"SIMULATED INPUT: {response}")
            return response
        else:
            # Default to continue if no more responses
            print("SIMULATED INPUT: C")
            return "C"

    def handle_user_input(self, user_input: str) -> str:
        return user_input

    def display_token_count(self, *args, **kwargs):
        pass

    def display_welcome_message(self):
        pass

    def status(self, message: str, spinner: str = None):
        class DummyContext:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        return DummyContext()

    def bare(self, message):
        print(f"BARE: {message}")


async def test_quick_command():
    """Test a command that completes quickly."""
    print("=== Testing quick command ===")

    ui = TestUserInterface()
    context = AgentContext.create(
        model_spec={},
        sandbox_mode=SandboxMode.ALLOW_ALL,
        sandbox_contents=[],
        user_interface=ui,
    )

    result = await run_bash_command(context, "echo 'Hello World'")
    print(f"Result: {result}")
    print()


async def test_timeout_continue():
    """Test a command that times out and user chooses to continue."""
    print("=== Testing timeout with continue ===")

    # Simulate user choosing to continue, then kill
    ui = TestUserInterface(responses=["C", "K"])
    context = AgentContext.create(
        model_spec={},
        sandbox_mode=SandboxMode.ALLOW_ALL,
        sandbox_contents=[],
        user_interface=ui,
    )

    # Use a command that will definitely timeout (sleep for longer than our test timeout)
    result = await run_bash_command(context, "sleep 5")  # Will timeout after 30s
    print(f"Result: {result}")
    print()


async def test_timeout_kill():
    """Test a command that times out and user chooses to kill."""
    print("=== Testing timeout with kill ===")

    ui = TestUserInterface(responses=["K"])
    context = AgentContext.create(
        model_spec={},
        sandbox_mode=SandboxMode.ALLOW_ALL,
        sandbox_contents=[],
        user_interface=ui,
    )

    # Use a short timeout for testing (modify the function to accept timeout)
    from heare.developer.tools.repl import _run_bash_command_with_interactive_timeout

    result = await _run_bash_command_with_interactive_timeout(
        context, "sleep 10", initial_timeout=2
    )
    print(f"Result: {result}")
    print()


async def test_timeout_background():
    """Test a command that times out and user chooses to background."""
    print("=== Testing timeout with background ===")

    ui = TestUserInterface(responses=["B"])
    context = AgentContext.create(
        model_spec={},
        sandbox_mode=SandboxMode.ALLOW_ALL,
        sandbox_contents=[],
        user_interface=ui,
    )

    # Use a short timeout for testing
    from heare.developer.tools.repl import _run_bash_command_with_interactive_timeout

    result = await _run_bash_command_with_interactive_timeout(
        context, "sleep 10", initial_timeout=2
    )
    print(f"Result: {result}")
    print()


async def main():
    """Run all tests."""
    await test_quick_command()
    await test_timeout_kill()
    await test_timeout_background()
    print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
