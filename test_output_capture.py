#!/usr/bin/env python3
"""
Test output capture during interactive timeout.
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import heare modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from heare.developer.context import AgentContext
from heare.developer.sandbox import SandboxMode
from test_interactive_timeout import TestUserInterface
from heare.developer.tools.repl import _run_bash_command_with_interactive_timeout


async def test_output_capture():
    """Test that output is captured properly during timeout."""
    print("=== Testing output capture during timeout ===")

    ui = TestUserInterface(responses=["K"])
    context = AgentContext.create(
        model_spec={},
        sandbox_mode=SandboxMode.ALLOW_ALL,
        sandbox_contents=[],
        user_interface=ui,
    )

    # Create a command that produces output then sleeps
    command = """
for i in {1..5}; do
    echo "Output line $i"
    sleep 1
done
echo "Final output"
sleep 10
"""

    result = await _run_bash_command_with_interactive_timeout(
        context, command, initial_timeout=3
    )
    print(f"Result: {result}")
    print()


if __name__ == "__main__":
    asyncio.run(test_output_capture())
