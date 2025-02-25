import unittest
from unittest.mock import patch, mock_open
from heare.developer.context import AgentContext


class TestAgentContext(unittest.TestCase):
    @patch("heare.developer.context.open", new_callable=mock_open)
    def test_flush_creates_root_json(self, mock_file):
        context = AgentContext(session_id=None)
        context.flush()
        mock_file.assert_called_with("root.json", "w")

    @patch("heare.developer.context.open", new_callable=mock_open)
    def test_flush_creates_session_json(self, mock_file):
        context = AgentContext(session_id="abc123")
        context.flush()
        mock_file.assert_called_with("abc123.json", "w")

    @patch("heare.developer.context.open", new_callable=mock_open)
    def test_flush_writes_context_data(self, mock_file):
        context = AgentContext(session_id="test")
        context.result_data = {"foo": "bar"}
        mock_file.return_value = mock_context_file = mock_open().return_value
        context.flush()

        mock_context_file.write.assert_called_once_with('{"foo": "bar"}')

    # Add tests for flush being called in agent loop


if __name__ == "__main__":
    unittest.main()
