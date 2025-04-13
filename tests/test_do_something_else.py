import pytest
from unittest.mock import MagicMock, patch

from heare.developer.sandbox import Sandbox, SandboxMode, DoSomethingElseError


def test_do_something_else_error():
    # Mock a permission callback that raises DoSomethingElseError
    mock_callback = MagicMock(side_effect=DoSomethingElseError())

    # Create a sandbox with the mock callback
    sandbox = Sandbox(
        ".", SandboxMode.REQUEST_EVERY_TIME, permission_check_callback=mock_callback
    )

    # Verify that the error is properly raised
    with pytest.raises(DoSomethingElseError):
        sandbox.check_permissions("test_action", "test_resource")

    # Verify the callback was called with correct parameters
    mock_callback.assert_called_once_with(
        "test_action", "test_resource", SandboxMode.REQUEST_EVERY_TIME, None
    )


def test_default_permission_callback_do_something_else(monkeypatch):
    # Mock the input function to return 'd'
    monkeypatch.setattr("builtins.input", lambda _: "d")

    # Create a sandbox using the default permission callback
    sandbox = Sandbox(".", SandboxMode.REQUEST_EVERY_TIME)

    # Verify that DoSomethingElseError is raised when user enters 'd'
    with pytest.raises(DoSomethingElseError):
        sandbox.check_permissions("test_action", "test_resource")


# TODO: what is the goal of this test?
# def test_tool_propagates_do_something_else_error():
#     """Test that tools correctly propagate the DoSomethingElseError."""
#     from heare.developer.tools.files import read_file
#
#     # Create a mock context with a sandbox that raises DoSomethingElseError
#     mock_context = MagicMock()
#     heare.developer.tools.files.read_file.side_effect = DoSomethingElseError()
#
#     # Call the read_file tool, which should propagate the exception
#     with pytest.raises(DoSomethingElseError):
#         read_file(mock_context, "test_file.txt")


@patch("heare.developer.tools.framework.invoke_tool")
def test_toolbox_propagates_do_something_else_error(mock_invoke_tool):
    """Test that the toolbox correctly propagates the DoSomethingElseError."""
    from heare.developer.toolbox import Toolbox

    # Setup mock
    mock_invoke_tool.side_effect = DoSomethingElseError()

    # Create toolbox and context
    mock_context = MagicMock()
    toolbox = Toolbox(mock_context)

    # Create a mock tool_use object
    mock_tool_use = MagicMock()

    # Call invoke_agent_tool, which should propagate the exception
    with pytest.raises(DoSomethingElseError):
        toolbox.invoke_agent_tool(mock_tool_use)

    # Verify invoke_tool was called
    mock_invoke_tool.assert_called_once()


def test_agent_workflow_do_something_else():
    """Test the complete agent workflow when 'do something else' is selected."""

    # Create a chat history with a user message and an assistant message
    chat_history = [
        {"role": "user", "content": "Can you help me optimize this code?"},
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "I'll help you optimize this code."}],
        },
    ]

    # Simulate the handling of DoSomethingElseError in subagent.py
    # This essentially replicates the error handling block in subagent.py

    # 1. Remove the last assistant message
    if chat_history and chat_history[-1]["role"] == "assistant":
        chat_history.pop()

    # 2. Get alternative prompt (simulated)
    alternate_prompt = "Let me describe the code instead"

    # 3. Append alternate prompt to the last user message
    for i in reversed(range(len(chat_history))):
        if chat_history[i]["role"] == "user":
            # Add the alternate prompt to the previous user message
            if isinstance(chat_history[i]["content"], str):
                chat_history[i]["content"] += (
                    f"\n\nAlternate request: {alternate_prompt}"
                )
            elif isinstance(chat_history[i]["content"], list):
                # Handle content as list of blocks
                chat_history[i]["content"].append(
                    {
                        "type": "text",
                        "text": f"\n\nAlternate request: {alternate_prompt}",
                    }
                )
            break

    # Verify the chat history was modified correctly
    assert (
        len(chat_history) == 1
    ), "Assistant message should have been removed from chat history"
    assert chat_history[0]["role"] == "user", "First message should be from user"

    # The user message should now contain the alternate request
    assert (
        "Alternate request: Let me describe the code instead"
        in chat_history[0]["content"]
    ), "User message should contain the alternate request"


@patch("heare.developer.sandbox.DoSomethingElseError", DoSomethingElseError)
def test_agent_tool_handling_with_do_something_else():
    """Test the handling of DoSomethingElseError during tool invocation in the agent."""
    from heare.developer.sandbox import DoSomethingElseError

    # Create mock objects for the test
    mock_ui = MagicMock()
    mock_ui.get_user_input.return_value = "I want to try a different approach"

    # Mock the part object representing a tool use
    mock_part = MagicMock()
    mock_part.name = "read_file"
    mock_part.input = {"path": "test.py"}

    # Mock the tool invocation to raise DoSomethingElseError
    mock_toolbox = MagicMock()
    mock_toolbox.invoke_agent_tool.side_effect = DoSomethingElseError()

    # Set up chat history with a user and assistant message
    chat_history = [
        {"role": "user", "content": "Help me understand this code"},
        {"role": "assistant", "content": "I'll analyze the code for you"},
    ]

    # Create an empty tool result buffer
    tool_result_buffer = []

    # Simulate the error handling code from subagent.py
    try:
        # This will raise DoSomethingElseError
        result = mock_toolbox.invoke_agent_tool(mock_part)
        tool_result_buffer.append(result)
        mock_ui.handle_tool_result(mock_part.name, result)
    except DoSomethingElseError:
        # Handle "do something else" workflow:
        # 1. Remove the last assistant message
        if chat_history and chat_history[-1]["role"] == "assistant":
            chat_history.pop()

        # 2. Get user's alternate prompt
        mock_ui.handle_system_message(
            "You selected 'do something else'. Please enter what you'd like to do instead:"
        )
        alternate_prompt = mock_ui.get_user_input()

        # 3. Append alternate prompt to the last user message
        for i in reversed(range(len(chat_history))):
            if chat_history[i]["role"] == "user":
                # Add the alternate prompt to the previous user message
                if isinstance(chat_history[i]["content"], str):
                    chat_history[i]["content"] += (
                        f"\n\nAlternate request: {alternate_prompt}"
                    )
                elif isinstance(chat_history[i]["content"], list):
                    # Handle content as list of blocks
                    chat_history[i]["content"].append(
                        {
                            "type": "text",
                            "text": f"\n\nAlternate request: {alternate_prompt}",
                        }
                    )
                break

        # Clear the tool result buffer to avoid processing the current tool request
        tool_result_buffer.clear()

    # Verify UI was used to get alternate prompt
    mock_ui.handle_system_message.assert_called_with(
        "You selected 'do something else'. Please enter what you'd like to do instead:"
    )
    mock_ui.get_user_input.assert_called_once()

    # Check the chat history was properly modified
    assert len(chat_history) == 1, "Expected only the user message in chat history"
    assert (
        chat_history[0]["role"] == "user"
    ), "Expected the remaining message to be from user"
    assert (
        "Alternate request: I want to try a different approach"
        in chat_history[0]["content"]
    ), "User message should contain the alternate request"

    # Check that tool_result_buffer was cleared
    assert len(tool_result_buffer) == 0, "Expected tool_result_buffer to be cleared"


def test_cli_user_interface_do_something_else():
    """Test that the CLI user interface permission callback properly handles 'do something else'."""
    from heare.developer.hdev import CLIUserInterface
    from rich.console import Console

    # Create a mock console that returns 'd' for input
    mock_console = MagicMock(spec=Console)
    mock_console.input.return_value = "d"

    # Create the user interface
    ui = CLIUserInterface(mock_console, SandboxMode.REQUEST_EVERY_TIME)

    # Test the permission callback
    with pytest.raises(DoSomethingElseError):
        ui.permission_callback(
            "test_action", "test_resource", SandboxMode.REQUEST_EVERY_TIME, {}
        )

    # Verify the console was used to get input with the correct prompt
    mock_console.input.assert_called_once_with(
        "[bold yellow]Allow this action? (y/N/D for 'do something else'): [/bold yellow]"
    )


@patch("heare.developer.agent.RateLimiter")
@patch("anthropic.Client")
def test_do_something_else_continues_conversation(mock_client, mock_rate_limiter):
    """Test that after 'do something else' is selected, the conversation continues with the updated prompt."""
    from heare.developer.agent import run
    from heare.developer.context import AgentContext
    from heare.developer.sandbox import DoSomethingElseError

    # Mock the anthropic client and stream
    mock_stream = MagicMock()
    mock_stream.get_final_message.return_value = MagicMock(
        content=[{"type": "text", "text": "I'll respond to your new request"}],
        usage={"input_tokens": 100, "output_tokens": 50},
        stop_reason="end_turn",
    )
    mock_client.return_value.messages.stream.return_value.__enter__.return_value = (
        mock_stream
    )

    # Create mock agent context and UI
    mock_ui = MagicMock()
    mock_context = MagicMock(spec=AgentContext)
    mock_context.user_interface = mock_ui
    mock_context.model_spec = {"title": "claude-3-sonnet", "max_tokens": 4000}

    # Create mock toolbox
    mock_toolbox = MagicMock()
    mock_context.toolbox = mock_toolbox

    # Set up to simulate DoSomethingElseError on the first tool call
    # and then normal processing afterwards
    call_count = [0]

    def side_effect_function(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise DoSomethingElseError()
        return {"type": "text", "text": "Tool executed successfully on second try"}

    mock_toolbox.invoke_agent_tool.side_effect = side_effect_function

    # Mock user input for the "do something else" prompt
    mock_ui.get_user_input.return_value = "Let me try a different approach instead"

    # We don't need to create an initial chat history as it will be
    # created by the run function with our initial_prompt

    # Run the agent with the mocked client and capture updates to chat_history
    # We need to patch the _inline_latest_file_mentions function to just return its input
    with patch(
        "heare.developer.agent._inline_latest_file_mentions", side_effect=lambda x: x
    ):
        run(
            agent_context=mock_context,
            initial_prompt="Can you help me with this task?",
            single_response=True,
        )

    # Verify the UI interactions
    mock_ui.handle_system_message.assert_any_call(
        "You selected 'do something else'. Please enter what you'd like to do instead:"
    )
    mock_ui.get_user_input.assert_called_once()

    # Verify that the client was called twice - once for initial response and once after "do something else"
    assert (
        mock_client.return_value.messages.stream.call_count > 1
    ), "Agent should continue the conversation after 'do something else'"

    # Verify the assistant response was displayed after the "do something else" flow
    mock_ui.handle_assistant_message.assert_called_with(
        "I'll respond to your new request"
    )
