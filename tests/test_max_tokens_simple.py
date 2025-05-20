import unittest
from unittest.mock import patch, MagicMock

from anthropic.types import TextBlock
from heare.developer.agent import run


class TestMaxTokensContinuation(unittest.TestCase):
    """Simple test for max tokens continuation."""

    def test_max_tokens_check(self):
        """Test that the max_tokens branch is correctly implemented."""
        # Create a mock final_message with stop_reason="max_tokens"
        mock_final_message = MagicMock()
        mock_final_message.stop_reason = "max_tokens"

        # Mock the content of the final message
        mock_final_message.content = [
            MagicMock(spec=TextBlock, text="This is an incomplete response")
        ]
        # Ensure text attribute is properly accessible
        mock_final_message.content[0].text = "This is an incomplete response"
        mock_final_message.content[0].__class__.__name__ = "TextBlock"
        # Initialize other essential attributes that might be accessed
        mock_final_message.usage = MagicMock()

        # Create a mock agent_context
        mock_agent_context = MagicMock()
        mock_agent_context.tool_result_buffer = []

        # Create a mock user_interface
        mock_user_interface = MagicMock()

        # Create a mock stream with the final_message
        mock_stream = MagicMock()
        mock_stream.get_final_message.return_value = mock_final_message

        # Create a mock client
        mock_client = MagicMock()
        mock_client.messages.stream.return_value.__enter__.return_value = mock_stream

        # Create other mocks needed by the run function
        mock_load_dotenv = MagicMock()
        mock_os_getenv = MagicMock(return_value="test-key")
        mock_create_system_message = MagicMock(return_value="Test system message")
        mock_toolbox = MagicMock()
        mock_toolbox.agent_schema = []
        mock_inline = MagicMock(return_value=[])

        # Patch all necessary functions
        with patch("anthropic.Client", return_value=mock_client), patch(
            "heare.developer.agent.load_dotenv", mock_load_dotenv
        ), patch("os.getenv", mock_os_getenv), patch(
            "heare.developer.agent.create_system_message", mock_create_system_message
        ), patch("heare.developer.agent.Toolbox", return_value=mock_toolbox), patch(
            "heare.developer.agent._inline_latest_file_mentions", mock_inline
        ):
            # Set user_interface in agent_context
            mock_agent_context.user_interface = mock_user_interface

            # Call the function
            run(
                agent_context=mock_agent_context,
                single_response=True,
                initial_prompt="test prompt",
            )

            # Check if user_interface.handle_assistant_message was called with a message about max tokens
            found_max_tokens_message = False
            for call in mock_user_interface.handle_assistant_message.call_args_list:
                args, kwargs = call
                if "Hit max tokens" in args[0]:
                    found_max_tokens_message = True
                    break

            self.assertTrue(found_max_tokens_message, "Max tokens message not found")

            # Check if the last message was removed from chat history if it was added
            mock_agent_context.chat_history.pop.assert_called_once()

            # Check if content from the final message plus continuation prompt was added to the tool_result_buffer
            # We expect 2 items: the original text and the continuation prompt
            self.assertEqual(len(mock_agent_context.tool_result_buffer), 2)

            # First item should be the content from the final message
            self.assertEqual(mock_agent_context.tool_result_buffer[0]["type"], "text")
            self.assertEqual(
                mock_agent_context.tool_result_buffer[0]["text"],
                "This is an incomplete response",
            )

            # Second item should be the continuation prompt
            self.assertEqual(mock_agent_context.tool_result_buffer[1]["type"], "text")
            self.assertIn(
                "continue", mock_agent_context.tool_result_buffer[1]["text"].lower()
            )
