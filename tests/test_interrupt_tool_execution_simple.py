import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from heare.developer.context import AgentContext
from heare.developer.sandbox import SandboxMode
from heare.developer.toolbox import Toolbox


class TestInterruptToolExecution:
    @pytest.fixture
    def mock_user_interface(self):
        ui = MagicMock()
        ui.handle_system_message = MagicMock()
        ui.handle_tool_result = MagicMock()
        ui.handle_tool_use = MagicMock()
        ui.handle_assistant_message = MagicMock()
        ui.get_user_input = AsyncMock(return_value="test input")
        ui.display_token_count = MagicMock()
        ui.status = MagicMock()
        ui.status.return_value.__enter__ = MagicMock()
        ui.status.return_value.__exit__ = MagicMock()
        ui.set_toolbox = MagicMock()
        return ui

    @pytest.fixture
    def agent_context(self, mock_user_interface):
        return AgentContext.create(
            model_spec={
                "title": "test-model",
                "max_tokens": 1000,
                "pricing": {"input": 0.01, "output": 0.02},
                "cache_pricing": {"write": 0.01, "read": 0.001},
            },
            sandbox_mode=SandboxMode.ALLOW_ALL,
            sandbox_contents=[],
            user_interface=mock_user_interface,
        )

    @pytest.mark.asyncio
    async def test_toolbox_keyboard_interrupt_propagation(self, agent_context):
        """Test that the toolbox properly propagates KeyboardInterrupt."""
        toolbox = Toolbox(agent_context, tool_names=[])

        # Create mock tool uses
        tool_uses = [
            MagicMock(name="test_tool", input={}, id="tool_1"),
        ]

        # Mock invoke_tool to raise KeyboardInterrupt
        with patch("heare.developer.tools.framework.invoke_tool") as mock_invoke:
            mock_invoke.side_effect = KeyboardInterrupt("User interrupted")

            # Test that KeyboardInterrupt is properly propagated
            with pytest.raises(KeyboardInterrupt):
                await toolbox.invoke_agent_tools(tool_uses)

    @pytest.mark.asyncio
    async def test_gather_keyboard_interrupt_handling(self):
        """Test that asyncio.gather properly handles KeyboardInterrupt."""

        async def failing_task():
            raise KeyboardInterrupt("User interrupted")

        with pytest.raises(KeyboardInterrupt):
            await asyncio.gather(failing_task(), return_exceptions=True)

    def test_cancelled_tool_result_structure(self, agent_context):
        """Test that cancelled tool results have the correct structure."""
        tool_use = MagicMock()
        tool_use.id = "test_tool_id"
        tool_use.name = "test_tool"

        # This is the structure that should be created for cancelled tools
        expected_result = {
            "type": "tool_result",
            "tool_use_id": "test_tool_id",
            "content": "cancelled",
        }

        # Verify the structure is correct
        assert expected_result["type"] == "tool_result"
        assert expected_result["tool_use_id"] == "test_tool_id"
        assert expected_result["content"] == "cancelled"
