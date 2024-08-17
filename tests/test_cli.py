import pytest
from unittest.mock import Mock, patch
from heare.developer.cli import permission_check_callback
from heare.developer.sandbox import SandboxMode
from prompt_toolkit.input import PipeInput


@pytest.fixture
def mock_console():
    return Mock()


@pytest.fixture
def mock_session():
    return Mock()


def test_permission_check_single_line(mock_console, mock_session):
    with patch("heare.developer.cli.PromptSession", return_value=mock_session):
        mock_session.prompt.return_value = "y"
        result = permission_check_callback(
            mock_console, "read", "file.txt", SandboxMode.REMEMBER_PER_RESOURCE
        )
        assert result


def test_permission_check_multi_line(mock_console, mock_session):
    with patch("heare.developer.cli.PromptSession", return_value=mock_session):
        mock_session.prompt.return_value = "This is a\nmulti-line\ninput\ny"
        result = permission_check_callback(
            mock_console, "write", "file.txt", SandboxMode.REMEMBER_PER_RESOURCE
        )
        assert result


def test_permission_check_negative_response(mock_console, mock_session):
    with patch("heare.developer.cli.PromptSession", return_value=mock_session):
        mock_session.prompt.return_value = "n"
        result = permission_check_callback(
            mock_console, "delete", "file.txt", SandboxMode.REMEMBER_PER_RESOURCE
        )
        assert result


# This test requires more setup to simulate actual key presses
def test_permission_check_shift_enter():
    inp = PipeInput()
    inp.send_text("This is a\nMulti-line input\nwith Shift+Enter\ny\n")

    with patch("heare.developer.cli.PromptSession") as MockPromptSession:
        mock_session = MockPromptSession.return_value
        mock_session.prompt.return_value = inp.read()

        result = permission_check_callback(
            Mock(), "read", "file.txt", SandboxMode.REMEMBER_PER_RESOURCE
        )

        assert result
        assert "Multi-line input" in mock_session.prompt.return_value
