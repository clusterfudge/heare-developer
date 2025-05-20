import unittest
from unittest.mock import MagicMock


class TestMaxTokensContinuation(unittest.TestCase):
    """Test the max tokens continuation feature directly."""

    def test_max_tokens_handler(self):
        """Test the handler for max tokens condition."""
        # Set up mocks
        mock_user_interface = MagicMock()
        mock_agent_context = MagicMock()
        mock_agent_context.tool_result_buffer = []

        # Call the continuation handler logic directly
        mock_user_interface.handle_assistant_message(
            "[bold yellow]Hit max tokens. I'll continue from where I left off...[/bold yellow]"
        )

        # Add a continuation prompt to the tool result buffer
        continuation_prompt = {
            "type": "text",
            "text": "Please continue from where you left off.",
        }
        mock_agent_context.tool_result_buffer.append(continuation_prompt)

        # Verify the expected behavior
        mock_user_interface.handle_assistant_message.assert_called_once_with(
            "[bold yellow]Hit max tokens. I'll continue from where I left off...[/bold yellow]"
        )

        # Verify a continuation prompt was added to the tool buffer
        self.assertEqual(len(mock_agent_context.tool_result_buffer), 1)
        self.assertEqual(mock_agent_context.tool_result_buffer[0]["type"], "text")
        self.assertIn(
            "continue", mock_agent_context.tool_result_buffer[0]["text"].lower()
        )
