from unittest.mock import MagicMock, patch
from anthropic.types import Message, ToolUseBlock

from heare.developer.agent import run
from heare.developer.context import AgentContext
from heare.developer.sandbox import SandboxMode
from heare.developer.tools.framework import invoke_tool


def create_mock_response_with_unknown_tool():
    """Create a mock response with an unknown tool_spec invocation"""
    # Create a response object that simulates an unknown tool invocation
    mock_response = MagicMock()
    # Set up the get_final_message to return a message with an unknown tool use
    final_message = Message(
        id="msg_123",
        content=[
            ToolUseBlock(
                type="tool_use",
                id="tu_123",
                name="unknown_tool",  # This tool doesn't exist in our toolbox
                input={"param": "value"},
            )
        ],
        model="claude-3-haiku-20240307",
        role="assistant",
        stop_reason="tool_use",
        stop_sequence=None,
        type="message",
        usage=MagicMock(),
    )
    mock_response.get_final_message.return_value = final_message
    return mock_response


def create_mock_response_with_malformed_tool():
    """Create a mock response with a malformed tool_spec invocation"""
    # Create a response object that simulates a malformed tool invocation
    mock_response = MagicMock()
    # Create a custom tool block that is missing required fields
    malformed_tool = MagicMock()
    malformed_tool.type = "tool_use"
    malformed_tool.id = "tu_456"
    # Intentionally missing name and input attributes

    # Set up the final message
    final_message = Message(
        id="msg_456",
        content=[malformed_tool],
        model="claude-3-haiku-20240307",
        role="assistant",
        stop_reason="tool_use",
        stop_sequence=None,
        type="message",
        usage=MagicMock(),
    )
    mock_response.get_final_message.return_value = final_message
    return mock_response


@patch("anthropic.resources.messages.Messages.stream")
def test_unknown_tool_handled_gracefully(mock_stream):
    """Test that the agent handles unknown tools gracefully"""
    # Set up the mock stream to return a response with an unknown tool
    mock_stream.return_value.__enter__.return_value = (
        create_mock_response_with_unknown_tool()
    )

    # Create minimal context for testing
    user_interface = MagicMock()
    context = AgentContext.create(
        model_spec={
            "title": "claude-3-haiku-20240307",
            "max_tokens": 1000,
            "pricing": {"input": 0.25, "output": 1.25},
        },
        sandbox_mode=SandboxMode.ALLOW_ALL,
        user_interface=user_interface,
    )

    # Add a message to the chat history
    context.chat_history.append({"role": "user", "content": "Use a tool"})

    # Run the agent
    run(agent_context=context, single_response=True)

    # Check that no exception was raised and the error was handled
    # Verify the assistant reported an unknown function error
    assert user_interface.handle_tool_result.called
    tool_result_args = user_interface.handle_tool_result.call_args[0]
    assert "unknown_tool" == tool_result_args[0]  # First arg is the tool name
    assert "Unknown function" in tool_result_args[1]["content"]  # Error content


@patch("anthropic.resources.messages.Messages.stream")
def test_malformed_tool_spec_handled_gracefully(mock_stream):
    """Test that the agent handles malformed tool specifications gracefully"""
    # Set up the mock stream to return a response with a malformed tool
    mock_stream.return_value.__enter__.return_value = (
        create_mock_response_with_malformed_tool()
    )

    # Create minimal context for testing
    user_interface = MagicMock()
    context = AgentContext.create(
        model_spec={
            "title": "claude-3-haiku-20240307",
            "max_tokens": 1000,
            "pricing": {"input": 0.25, "output": 1.25},
        },
        sandbox_mode=SandboxMode.ALLOW_ALL,
        user_interface=user_interface,
    )

    # Add a message to the chat history
    context.chat_history.append({"role": "user", "content": "Use a malformed tool"})

    # Run the agent - should not crash
    run(agent_context=context, single_response=True)

    # Verify the assistant handled the malformed tool gracefully
    assert user_interface.handle_tool_result.called
    # Tool name should default to "unknown_tool" when missing
    assert "unknown_tool" in user_interface.handle_tool_result.call_args[0][0]
    # Check that error message mentions invalid or missing attributes
    result_content = user_interface.handle_tool_result.call_args[0][1]["content"]
    assert "missing" in result_content.lower() or "invalid" in result_content.lower()


def test_invoke_tool_with_empty_toolspec():
    """Test invoking a tool with an empty or invalid tool specification"""
    context = MagicMock()

    # Test with None
    result = invoke_tool(context, None)
    assert "Invalid tool specification" in result["content"]

    # Test with dict instead of proper tool_use object
    result = invoke_tool(context, {"type": "tool_use"})
    assert "Invalid tool specification" in result["content"]

    # Test with MagicMock missing required attributes
    mock_tool = MagicMock()
    mock_tool.type = "tool_use"
    # Intentionally missing name and input
    result = invoke_tool(context, mock_tool)
    assert "Invalid tool specification" in result["content"]
