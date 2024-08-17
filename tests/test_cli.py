import pytest
from unittest.mock import Mock
from heare.developer.cli import permission_check_callback
from heare.developer.sandbox import SandboxMode
from prompt_toolkit.input import PipeInput


class ConcretePipeInput(PipeInput):
    def __init__(self):
        self._text = ""

    def attach(self, input):
        pass

    def detach(self):
        pass

    def read_keys(self):
        for c in self._text:
            yield c
        self._text = ""

    def raw_mode(self):
        return True

    def cooked_mode(self):
        return True

    def fileno(self):
        return 0

    def typeahead_hash(self):
        return str(id(self))

    def close(self):
        pass

    @property
    def closed(self):
        return False

    def send_text(self, data):
        self._text += data

    def send_bytes(self, data):
        self._text += data.decode("utf-8")


@pytest.fixture
def mock_console():
    return Mock()


@pytest.fixture
def mock_session():
    return Mock()


def test_permission_check_single_line(mock_console, mock_session):
    mock_console.input.return_value = "y"
    result = permission_check_callback(
        mock_console, "read", "file.txt", SandboxMode.REMEMBER_PER_RESOURCE
    )
    assert result


def test_permission_check_multi_line(mock_console, mock_session):
    mock_console.input.return_value = "This is a\nmulti-line\ninput\ny"
    result = permission_check_callback(
        mock_console, "write", "file.txt", SandboxMode.REMEMBER_PER_RESOURCE
    )
    assert not result


def test_permission_check_negative_response(mock_console, mock_session):
    mock_console.input.return_value = "n"
    result = permission_check_callback(
        mock_console, "delete", "file.txt", SandboxMode.REMEMBER_PER_RESOURCE
    )
    assert not result
