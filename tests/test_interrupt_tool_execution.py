import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from heare.developer.agent import run
from heare.developer.context import AgentContext
from heare.developer.sandbox import SandboxMode
from heare.developer.toolbox import Toolbox
from heare.developer.tools.framework import tool


@tool
async def slow_test_tool(context: AgentContext, delay: int = 5):
    """A test tool that takes a long time to complete"""
    await asyncio.sleep(delay)
    return "Completed after delay"


@tool
async def fast_test_tool(context: AgentContext, message: str = "hello"):
    """A test tool that completes quickly"""
    return f"Fast tool says: {message}"


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
    async def test_interrupt_during_tool_execution(self, agent_context):
        """Test that KeyboardInterrupt during tool execution creates cancelled results."""
        # Create a toolbox with our test tools
        toolbox = Toolbox(
            agent_context, tool_names=["slow_test_tool", "fast_test_tool"]
        )

        # Mock tool uses that would normally cause long execution
        tool_uses = [
            MagicMock(name="slow_test_tool", input={"delay": 10}, id="tool_1"),
            MagicMock(name="fast_test_tool", input={"message": "test"}, id="tool_2"),
        ]

        # Mock the invoke_tool function to simulate KeyboardInterrupt
        with patch("heare.developer.tools.framework.invoke_tool") as mock_invoke:
            # First call raises KeyboardInterrupt, second call would succeed
            mock_invoke.side_effect = KeyboardInterrupt("User interrupted")

            # Test that KeyboardInterrupt is properly propagated
            with pytest.raises(KeyboardInterrupt):
                await toolbox.invoke_agent_tools(tool_uses)

    @pytest.mark.asyncio
    async def test_agent_handles_tool_interrupt(
        self, agent_context, mock_user_interface
    ):
        """Test that the agent properly handles KeyboardInterrupt from tool execution."""
        # Create a mock final message with tool use
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "slow_test_tool"
        mock_tool_use.input = {"delay": 10}
        mock_tool_use.id = "tool_1"

        mock_final_message = MagicMock()
        mock_final_message.content = [mock_tool_use]
        mock_final_message.stop_reason = "tool_use"
        mock_final_message.usage = MagicMock()
        mock_final_message.usage.input_tokens = 100
        mock_final_message.usage.output_tokens = 50
        mock_final_message.usage.cache_creation_input_tokens = 0
        mock_final_message.usage.cache_read_input_tokens = 0

        # Mock the anthropic client to return our mock message
        with patch("anthropic.Client") as mock_anthropic:
            mock_stream = MagicMock()
            mock_stream.__enter__ = MagicMock(return_value=mock_stream)
            mock_stream.__exit__ = MagicMock(return_value=None)
            mock_stream.get_final_message.return_value = mock_final_message
            mock_stream.response.headers = {}

            # Mock the chunks returned by the stream
            mock_chunk = MagicMock()
            mock_chunk.type = "text"
            mock_chunk.text = "AI response"
            mock_stream.__iter__ = MagicMock(return_value=iter([mock_chunk]))

            mock_client = MagicMock()
            mock_client.messages.stream.return_value = mock_stream
            mock_anthropic.return_value = mock_client

            # Mock the toolbox to raise KeyboardInterrupt
            with patch.object(Toolbox, "invoke_agent_tools") as mock_invoke_tools:
                mock_invoke_tools.side_effect = KeyboardInterrupt("User interrupted")

                # Set up environment
                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                    # Run the agent with single response mode
                    await run(
                        agent_context=agent_context,
                        initial_prompt="Test prompt",
                        single_response=True,
                        enable_compaction=False,
                    )

                # Verify that the system message about interruption was shown
                mock_user_interface.handle_system_message.assert_any_call(
                    "[bold yellow]Tool execution interrupted by user (Ctrl+C)[/bold yellow]"
                )

                # Verify that cancelled results were added to the tool result buffer
                assert len(agent_context.tool_result_buffer) == 1
                result = agent_context.tool_result_buffer[0]
                assert result["type"] == "tool_result"
                assert result["tool_use_id"] == "tool_1"
                assert result["content"] == "cancelled"

    @pytest.mark.asyncio
    async def test_multiple_tool_interrupt_creates_multiple_cancelled_results(
        self, agent_context, mock_user_interface
    ):
        """Test that interrupting multiple tools creates cancelled results for all."""
        # Create mock tool uses
        tool_uses = [
            MagicMock(name="slow_test_tool", input={"delay": 10}, id="tool_1"),
            MagicMock(name="fast_test_tool", input={"message": "test"}, id="tool_2"),
        ]

        # Mock the final message with multiple tool uses
        mock_final_message = MagicMock()
        mock_final_message.content = tool_uses
        mock_final_message.stop_reason = "tool_use"
        mock_final_message.usage = MagicMock()
        mock_final_message.usage.input_tokens = 100
        mock_final_message.usage.output_tokens = 50
        mock_final_message.usage.cache_creation_input_tokens = 0
        mock_final_message.usage.cache_read_input_tokens = 0

        # Mock the anthropic client
        with patch("anthropic.Client") as mock_anthropic:
            mock_stream = MagicMock()
            mock_stream.__enter__ = MagicMock(return_value=mock_stream)
            mock_stream.__exit__ = MagicMock(return_value=None)
            mock_stream.get_final_message.return_value = mock_final_message
            mock_stream.response.headers = {}

            mock_chunk = MagicMock()
            mock_chunk.type = "text"
            mock_chunk.text = "AI response"
            mock_stream.__iter__ = MagicMock(return_value=iter([mock_chunk]))

            mock_client = MagicMock()
            mock_client.messages.stream.return_value = mock_stream
            mock_anthropic.return_value = mock_client

            # Mock the toolbox to raise KeyboardInterrupt
            with patch.object(Toolbox, "invoke_agent_tools") as mock_invoke_tools:
                mock_invoke_tools.side_effect = KeyboardInterrupt("User interrupted")

                with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                    await run(
                        agent_context=agent_context,
                        initial_prompt="Test prompt",
                        single_response=True,
                        enable_compaction=False,
                    )

                # Verify that cancelled results were created for both tools
                assert len(agent_context.tool_result_buffer) == 2

                result1 = agent_context.tool_result_buffer[0]
                assert result1["type"] == "tool_result"
                assert result1["tool_use_id"] == "tool_1"
                assert result1["content"] == "cancelled"

                result2 = agent_context.tool_result_buffer[1]
                assert result2["type"] == "tool_result"
                assert result2["tool_use_id"] == "tool_2"
                assert result2["content"] == "cancelled"

    @pytest.mark.asyncio
    async def test_toolbox_cancellation_propagates_keyboard_interrupt(
        self, agent_context
    ):
        """Test that the toolbox properly propagates KeyboardInterrupt."""
        toolbox = Toolbox(agent_context, tool_names=["slow_test_tool"])

        tool_uses = [
            MagicMock(name="slow_test_tool", input={"delay": 10}, id="tool_1"),
        ]

        # Mock invoke_tool to raise KeyboardInterrupt
        with patch("heare.developer.tools.framework.invoke_tool") as mock_invoke:
            mock_invoke.side_effect = KeyboardInterrupt("User interrupted")

            # Verify that KeyboardInterrupt is properly propagated
            with pytest.raises(KeyboardInterrupt):
                await toolbox.invoke_agent_tools(tool_uses)
