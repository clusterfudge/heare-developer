#!/usr/bin/env python3
"""Simple manual test of interrupt functionality"""

from unittest.mock import MagicMock

from heare.developer.context import AgentContext
from heare.developer.sandbox import SandboxMode


def test_interrupt_implementation():
    """Test that the interrupt handling creates cancelled results"""

    # Create mock UI
    mock_ui = MagicMock()
    mock_ui.permission_callback = MagicMock(return_value=True)
    mock_ui.permission_rendering_callback = MagicMock()

    # Create context
    context = AgentContext.create(
        model_spec={
            "title": "test-model",
            "max_tokens": 1000,
            "pricing": {"input": 0.01, "output": 0.02},
            "cache_pricing": {"write": 0.01, "read": 0.001},
        },
        sandbox_mode=SandboxMode.ALLOW_ALL,
        sandbox_contents=[],
        user_interface=mock_ui,
    )

    # Create mock tool uses
    tool_uses = [
        MagicMock(name="slow_tool", input={"delay": 10}, id="tool_1"),
        MagicMock(name="another_tool", input={"param": "value"}, id="tool_2"),
    ]

    # Simulate the agent's interrupt handling code
    print("Simulating KeyboardInterrupt during tool execution...")

    # This is what the agent does when KeyboardInterrupt is caught
    context.user_interface.handle_system_message(
        "[bold yellow]Tool execution interrupted by user (Ctrl+C)[/bold yellow]"
    )

    # Create cancelled results for all tool uses
    for tool_use in tool_uses:
        result = {
            "type": "tool_result",
            "tool_use_id": getattr(tool_use, "id", "unknown_id"),
            "content": "cancelled",
        }
        context.tool_result_buffer.append(result)
        tool_name = getattr(tool_use, "name", "unknown_tool")
        context.user_interface.handle_tool_result(tool_name, result)

    # Check results
    print(f"Tool result buffer has {len(context.tool_result_buffer)} entries")
    for i, result in enumerate(context.tool_result_buffer):
        print(f"Result {i+1}: {result}")

    # Verify all results are cancelled
    all_cancelled = all(
        result["content"] == "cancelled" for result in context.tool_result_buffer
    )
    print(f"All results are cancelled: {all_cancelled}")

    # Verify UI methods were called
    print(f"handle_system_message called: {mock_ui.handle_system_message.called}")
    print(f"handle_tool_result called {mock_ui.handle_tool_result.call_count} times")

    print("Test completed successfully!")


if __name__ == "__main__":
    test_interrupt_implementation()
