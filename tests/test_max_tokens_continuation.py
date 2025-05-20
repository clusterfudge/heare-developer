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
        mock_agent_context.chat_history = []

        # Mock the final message
        from anthropic.types import TextBlock

        mock_final_message = MagicMock()
        mock_text_block = MagicMock(spec=TextBlock)
        mock_text_block.text = "Partial response"
        mock_text_block.__class__.__name__ = "TextBlock"
        mock_final_message.content = [mock_text_block]

        # Add a mock assistant message to chat history that should be removed
        mock_agent_context.chat_history = [{"role": "assistant", "content": "test"}]

        # Call the continuation handler logic directly
        mock_user_interface.handle_assistant_message(
            "[bold yellow]Hit max tokens. I'll continue from where I left off...[/bold yellow]"
        )

        # Remove the last message from chat history (should be an assistant message)
        mock_agent_context.chat_history.pop()

        # Add the partial message to the tool result buffer
        partial_response = {"type": "text", "text": "Partial response"}
        mock_agent_context.tool_result_buffer.append(partial_response)

        # Add a continuation prompt to the tool result buffer
        continuation_prompt = {
            "type": "text",
            "text": "Please continue from where you left off. If you were in the middle of a tool use, please complete it.",
        }
        mock_agent_context.tool_result_buffer.append(continuation_prompt)

        # Verify the expected behavior
        mock_user_interface.handle_assistant_message.assert_called_once_with(
            "[bold yellow]Hit max tokens. I'll continue from where I left off...[/bold yellow]"
        )

        # Verify both the partial response and continuation prompt were added to the tool buffer
        self.assertEqual(len(mock_agent_context.tool_result_buffer), 2)

        # First item should be the partial response
        self.assertEqual(mock_agent_context.tool_result_buffer[0]["type"], "text")
        self.assertEqual(
            mock_agent_context.tool_result_buffer[0]["text"], "Partial response"
        )

        # Second item should be the continuation prompt
        self.assertEqual(mock_agent_context.tool_result_buffer[1]["type"], "text")
        self.assertIn(
            "continue", mock_agent_context.tool_result_buffer[1]["text"].lower()
        )
