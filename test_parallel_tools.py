#!/usr/bin/env python3
"""
Test script for parallel tool execution functionality.
"""

import asyncio
import tempfile
from pathlib import Path

from heare.developer.context import AgentContext
from heare.developer.models import get_model
from heare.developer.sandbox import SandboxMode
from heare.developer.toolbox import Toolbox


class MockUserInterface:
    """Mock user interface for testing."""

    def handle_system_message(self, message):
        print(f"[SYSTEM] {message}")

    def handle_tool_use(self, tool_name, tool_input):
        print(f"[TOOL USE] {tool_name}: {tool_input}")

    def handle_tool_result(self, tool_name, result):
        print(f"[TOOL RESULT] {tool_name}: Success")

    def permission_callback(self, action, resource, sandbox_mode, action_arguments):
        return True

    def permission_rendering_callback(self, action, resource, action_arguments):
        pass


async def test_parallel_tool_execution():
    """Test that parallel tool execution works correctly."""
    print("Testing parallel tool execution...")

    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files
        file1 = temp_path / "test1.txt"
        file2 = temp_path / "test2.txt"
        file3 = temp_path / "test3.txt"

        file1.write_text("Content of test file 1")
        file2.write_text("Content of test file 2")
        file3.write_text("Content of test file 3")

        # Create mock user interface
        user_interface = MockUserInterface()

        # Create agent context
        context = AgentContext.create(
            model_spec=get_model("sonnet"),
            sandbox_mode=SandboxMode.ALLOW_ALL,
            sandbox_contents=[str(temp_path)],
            user_interface=user_interface,
        )

        # Create toolbox
        toolbox = Toolbox(context)

        # Create mock tool_use objects for reading multiple files
        class MockToolUse:
            def __init__(self, name, input_data, tool_id):
                self.name = name
                self.input = input_data
                self.id = tool_id

        tool_uses = [
            MockToolUse("read_file", {"path": str(file1)}, "tool_1"),
            MockToolUse("read_file", {"path": str(file2)}, "tool_2"),
            MockToolUse("read_file", {"path": str(file3)}, "tool_3"),
        ]

        # Test parallel execution
        print("Executing 3 read_file operations in parallel...")
        start_time = asyncio.get_event_loop().time()

        results = await toolbox.invoke_agent_tools(tool_uses)

        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time

        print(f"Parallel execution completed in {execution_time:.3f} seconds")
        print(f"Number of results: {len(results)}")

        # Verify results
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"

        for i, result in enumerate(results):
            assert result["type"] == "tool_result", f"Result {i} has wrong type"
            assert (
                result["tool_use_id"] == f"tool_{i+1}"
            ), f"Result {i} has wrong tool_use_id"
            assert (
                f"Content of test file {i+1}" in result["content"]
            ), f"Result {i} has wrong content"

        print("✅ Parallel tool execution test passed!")

        # Test sequential tool execution (edit_file should be sequential)
        print("\nTesting sequential tool execution...")

        sequential_tool_uses = [
            MockToolUse(
                "edit_file",
                {
                    "path": str(file1),
                    "match_text": "Content",
                    "replace_text": "Modified",
                },
                "edit_1",
            ),
            MockToolUse("read_file", {"path": str(file1)}, "read_1"),
        ]

        sequential_results = await toolbox.invoke_agent_tools(sequential_tool_uses)

        print("Sequential execution completed")
        print(f"Number of results: {len(sequential_results)}")

        assert (
            len(sequential_results) == 2
        ), f"Expected 2 results, got {len(sequential_results)}"
        print("✅ Sequential tool execution test passed!")

        return True


async def main():
    """Main test function."""
    try:
        await test_parallel_tool_execution()
        print("\n🎉 All tests passed! Parallel tool execution is working correctly.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
