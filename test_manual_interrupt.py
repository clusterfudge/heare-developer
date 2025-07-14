#!/usr/bin/env python3
"""Manual test to verify interrupt functionality works"""

import asyncio
from unittest.mock import MagicMock

from heare.developer.context import AgentContext
from heare.developer.sandbox import SandboxMode
from heare.developer.toolbox import Toolbox


class MockUserInterface:
    def handle_system_message(self, msg):
        print(f"System: {msg}")

    def handle_tool_result(self, name, result):
        print(f"Tool {name} result: {result}")

    def handle_tool_use(self, name, params):
        print(f"Tool {name} called with: {params}")

    def set_toolbox(self, toolbox):
        pass

    def permission_callback(self, action, resource, sandbox_mode, action_arguments):
        return True

    def permission_rendering_callback(self, action, resource, action_arguments):
        pass


async def slow_tool_simulation():
    """Simulate a slow tool that takes time"""
    print("Starting slow tool...")
    await asyncio.sleep(10)  # 10 second delay
    return "Tool completed"


async def main():
    # Create a mock context
    context = AgentContext.create(
        model_spec={
            "title": "test-model",
            "max_tokens": 1000,
            "pricing": {"input": 0.01, "output": 0.02},
            "cache_pricing": {"write": 0.01, "read": 0.001},
        },
        sandbox_mode=SandboxMode.ALLOW_ALL,
        sandbox_contents=[],
        user_interface=MockUserInterface(),
    )

    # Create toolbox
    toolbox = Toolbox(context, tool_names=[])

    # Mock tool uses that would trigger long-running operations
    tool_uses = [
        MagicMock(name="slow_tool", input={"delay": 10}, id="tool_1"),
    ]

    # Mock invoke_tool to use our slow simulation
    async def mock_invoke_tool(context, tool_use, tools=None):
        print(f"Invoking tool: {tool_use.name}")
        await slow_tool_simulation()
        return {
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": "Tool completed successfully",
        }

    # Patch the invoke_tool function
    import heare.developer.tools.framework

    original_invoke_tool = heare.developer.tools.framework.invoke_tool
    heare.developer.tools.framework.invoke_tool = mock_invoke_tool

    try:
        print("Starting tool execution (press Ctrl+C to interrupt)...")
        results = await toolbox.invoke_agent_tools(tool_uses)
        print(f"Tool execution completed: {results}")
    except KeyboardInterrupt:
        print("Tool execution was interrupted by user!")
        return "interrupted"
    finally:
        # Restore original function
        heare.developer.tools.framework.invoke_tool = original_invoke_tool

    return "completed"


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"Final result: {result}")
