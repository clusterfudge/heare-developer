import pytest
from unittest.mock import Mock, patch
from dataclasses import dataclass
from heare.developer.agent import run
from heare.developer.user_interface import UserInterface
from heare.developer.sandbox import SandboxMode
from typing import List


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class MockMessage:
    type: str
    text: str = None
    content: List[str] = None
    usage: Usage = None
    stop_reason: str = None


@dataclass
class MockResponse:
    headers: dict


class MockStream:
    def __init__(self, content):
        self.content = content
        self.final_message = MockMessage(
            type="message",
            content=[content],
            usage=Usage(input_tokens=100, output_tokens=50),
            stop_reason="end_turn",
        )
        self.response = MockResponse(
            {
                "x-ratelimit-limit": "100000",
                "x-ratelimit-remaining": "99999",
                "x-ratelimit-reset": "3600",
            }
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def __iter__(self):
        yield MockMessage(type="text", text=self.content)

    def get_final_message(self):
        return self.final_message


class MockUserInterface(UserInterface):
    def __init__(self):
        self.messages = []
        self.inputs = []
        self.current_input_index = 0

    def handle_assistant_message(self, message: str) -> None:
        self.messages.append(("assistant", message))

    def handle_system_message(self, message: str) -> None:
        self.messages.append(("system", message))

    def get_user_input(self, prompt: str = "") -> str:
        if self.current_input_index < len(self.inputs):
            result = self.inputs[self.current_input_index]
            self.current_input_index += 1
            return result
        return "/quit"

    def handle_user_input(self, user_input: str) -> str:
        self.messages.append(("user", user_input))
        return user_input

    def handle_tool_use(self, tool_name: str, tool_params: dict) -> bool:
        return True

    def handle_tool_result(self, name: str, result: dict) -> None:
        pass

    def display_token_count(self, *args, **kwargs) -> None:
        pass

    def display_welcome_message(self) -> None:
        pass

    def permission_callback(
        self,
        action: str,
        resource: str,
        sandbox_mode: SandboxMode,
        action_arguments: dict | None,
    ) -> bool:
        return True

    def permission_rendering_callback(
        self,
        action: str,
        resource: str,
        action_arguments: dict | None,
    ):
        pass

    def status(self, message: str, spinner: str = None):
        class NoOpContextManager:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        return NoOpContextManager()


class MockToolbox:
    def __init__(self, local_tools=None):
        self.local = local_tools or {}
        self.agent_schema = []

    def invoke_agent_tool(self, tool_use):
        return {"type": "tool_result", "tool_use_id": "test", "content": "test result"}


@pytest.fixture
def mock_anthropic():
    with patch("anthropic.Client") as mock:
        mock_client = Mock()
        stream = MockStream("Test response")
        mock_client.messages.stream.return_value = stream
        mock.return_value = mock_client
        yield mock


@pytest.fixture
def mock_environment():
    with patch("heare.developer.agent.load_dotenv"), patch(
        "os.getenv", return_value="test-key"
    ):
        yield


@pytest.fixture
def model_config():
    return {
        "title": "claude-3-opus-20240229",
        "pricing": {"input": 15.0, "output": 75.0},
    }


@pytest.fixture
def mock_system_message():
    with patch("heare.developer.agent.create_system_message") as mock:
        mock.return_value = "Test system message"
        yield mock


@pytest.fixture
def mock_toolbox():
    with patch("heare.developer.agent.Toolbox") as mock:
        mock_instance = MockToolbox()
        mock.return_value = mock_instance
        yield mock_instance


def test_single_response_mode(
    mock_anthropic, mock_environment, model_config, mock_system_message, mock_toolbox
):
    ui = MockUserInterface()

    run(
        model_config,
        {},
        "remember_per_resource",
        mock_toolbox,
        ui,
        initial_prompt="Hello",
        single_response=True,
    )

    # Verify initial prompt was processed
    assert any("Hello" in str(msg) for msg in ui.messages if msg[0] == "user")
    # Verify the session ended after one response
    assert mock_anthropic.return_value.messages.stream.call_count == 1
    # Verify we got a response
    assert any(
        "Test response" in str(msg) for msg in ui.messages if msg[0] == "assistant"
    )


def test_initial_prompt_without_single_response(
    mock_anthropic, mock_environment, model_config, mock_system_message, mock_toolbox
):
    ui = MockUserInterface()
    ui.inputs = ["/quit"]  # Add quit command to end the session

    run(
        model_config,
        {},
        "remember_per_resource",
        mock_toolbox,
        ui,
        initial_prompt="Hello",
        single_response=False,
    )

    # Verify initial prompt was processed
    assert any("Hello" in str(msg) for msg in ui.messages if msg[0] == "user")
    # Verify we got a response
    assert any(
        "Test response" in str(msg) for msg in ui.messages if msg[0] == "assistant"
    )


def test_command_display_with_single_response(
    mock_anthropic, mock_environment, model_config, mock_system_message, mock_toolbox
):
    ui = MockUserInterface()

    run(
        model_config,
        {},
        "remember_per_resource",
        mock_toolbox,
        ui,
        initial_prompt="Hello",
        single_response=True,
    )

    # Verify commands are not displayed in single response mode
    assert not any("Available commands" in str(msg) for msg in ui.messages)


def test_command_display_without_single_response(
    mock_anthropic, mock_environment, model_config, mock_system_message
):
    ui = MockUserInterface()
    ui.inputs = ["/quit"]

    mock_toolbox = MockToolbox({"test": {"docstring": "Test command"}})

    run(
        model_config,
        {},
        "remember_per_resource",
        mock_toolbox,
        ui,
        initial_prompt=None,
        single_response=False,
    )

    # Verify commands are displayed in normal mode
    assert any("Available commands" in str(msg) for msg in ui.messages)
