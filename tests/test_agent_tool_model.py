import pytest
from unittest.mock import patch, MagicMock

from heare.developer.context import AgentContext
from heare.developer.models import MODEL_MAP
from heare.developer.tools.subagent import agent
from heare.developer.user_interface import UserInterface
from heare.developer.sandbox import Sandbox


@pytest.fixture
def mock_agent_run():
    with patch("heare.developer.agent.run") as mock_run:
        yield mock_run


@pytest.fixture
def agent_context():
    # Setup test model spec
    model_spec = {
        "title": "claude-3-sonnet-20240229",
        "pricing": {"input": 3.0, "output": 15.0},
        "cache_pricing": {"write": 3.0, "read": 0.6},
        "max_tokens": 4096,
    }

    # Create mocks
    mock_ui = MagicMock(spec=UserInterface)
    mock_sandbox = MagicMock(spec=Sandbox)

    # Create context
    context = AgentContext(
        parent_session_id=None,
        session_id="test-session",
        model_spec=model_spec,
        sandbox=mock_sandbox,
        user_interface=mock_ui,
        usage=[],
    )

    return context


def test_agent_tool_with_default_model(agent_context, mock_agent_run):
    # Setup
    mock_agent_run.return_value = [
        {"role": "user", "content": "test prompt"},
        {"role": "assistant", "content": "test response"},
    ]

    # Execute
    result = agent(agent_context, "test prompt", "web_search")

    # Verify
    assert mock_agent_run.call_count == 1
    assert mock_agent_run.call_args.kwargs["tool_names"] == ["web_search"]
    # Should use the default model from the context
    assert "claude-3-sonnet-20240229" == agent_context.model_spec["title"]
    # The result should be the assistant's response
    assert result == "test response"


def test_agent_tool_with_custom_model(agent_context, mock_agent_run):
    # Setup
    mock_agent_run.return_value = [
        {"role": "user", "content": "test prompt"},
        {"role": "assistant", "content": "test response with custom model"},
    ]

    # Execute with custom model parameter using the 'light' alias
    result = agent(agent_context, "test prompt", "web_search", model="light")

    # Verify that run was called with a context having the specified model
    assert mock_agent_run.call_count == 1

    # Extract the AgentContext object passed to run()
    context_arg = mock_agent_run.call_args.kwargs["agent_context"]

    # Verify the model was changed in the sub-agent context to the haiku model
    assert context_arg.model_spec["title"] == MODEL_MAP["haiku"]["title"]

    # The original context should remain unchanged
    assert agent_context.model_spec["title"] == "claude-3-sonnet-20240229"

    # The result should be the assistant's response
    assert result == "test response with custom model"


def test_agent_tool_with_smart_model(agent_context, mock_agent_run):
    # Setup
    mock_agent_run.return_value = [
        {"role": "user", "content": "test prompt"},
        {"role": "assistant", "content": "test response with smart model"},
    ]

    # Execute with the 'smart' alias
    result = agent(agent_context, "test prompt", "web_search", model="smart")

    # Verify
    assert mock_agent_run.call_count == 1

    # Extract the AgentContext object passed to run()
    context_arg = mock_agent_run.call_args.kwargs["agent_context"]

    # Verify the model was set to the 'smart' alias's corresponding model
    assert context_arg.model_spec["title"] == MODEL_MAP["sonnet-3.7"]["title"]

    # The result should be the assistant's response
    assert result == "test response with smart model"


def test_agent_tool_with_invalid_model(agent_context, mock_agent_run):
    # Setup
    mock_agent_run.return_value = [
        {"role": "user", "content": "test prompt"},
        {"role": "assistant", "content": "test response"},
    ]

    # Execute with an invalid model alias - should fall back to the default
    result = agent(agent_context, "test prompt", "web_search", model="nonexistent")

    # Verify
    assert mock_agent_run.call_count == 1

    # Extract the AgentContext object passed to run()
    context_arg = mock_agent_run.call_args.kwargs["agent_context"]

    # Since the model alias is invalid, it should use the default model from the original context
    assert context_arg.model_spec["title"] == "claude-3-sonnet-20240229"

    # The result should be the assistant's response
    assert result == "test response"
