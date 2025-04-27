import unittest
import tempfile
from pathlib import Path
from heare.developer.compacter import ConversationCompacter
from heare.developer.agent import _inline_latest_file_mentions


class MockAnthropicClient:
    """Mock Anthropic client for testing."""

    def __init__(self):
        self.messages = MockMessagesAPI()


class MockMessagesAPI:
    """Mock Messages API for the Anthropic client."""

    def count_tokens(self, model, messages):
        """Mock token counting that returns a fixed value."""
        # Return different token counts for with/without file mentions to verify behavior
        message_content = messages[0]["content"]
        if "<mentioned_file" in message_content:
            return MockTokenCountResponse(100)  # With file content
        else:
            return MockTokenCountResponse(50)  # Without file content

    def create(self, model, system, messages, max_tokens):
        """Mock message creation that returns a fixed summary."""
        return MockMessageResponse("This is a test summary.")


class MockTokenCountResponse:
    """Mock response for token counting."""

    def __init__(self, token_count):
        self.token_count = token_count


class MockMessageResponse:
    """Mock response for message creation."""

    def __init__(self, summary):
        self.content = [MockTextBlock(summary)]
        self.usage = {"input_tokens": 50, "output_tokens": 20}


class MockTextBlock:
    """Mock text block for message response."""

    def __init__(self, text):
        self.text = text


class TestFileMentionSummary(unittest.TestCase):
    """Test file mention handling in summaries."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary file with test content
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file_path = Path(self.temp_dir.name) / "test_file.txt"

        # Write test content to the file
        with open(self.test_file_path, "w") as f:
            f.write("This is test file content.\nIt has multiple lines.\n")

        # Create a mock compacter with a mock client
        self.compacter = ConversationCompacter(client=MockAnthropicClient())

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_file_mention_token_counting(self):
        """Test that file mentions are included in token counting."""
        # Create a message with a file mention
        messages = [
            {"role": "user", "content": f"Check this file @{self.test_file_path}"}
        ]

        # Process the messages to inline file mentions
        processed_messages = _inline_latest_file_mentions(messages)

        # Verify the processed message has the file content
        self.assertIn("<mentioned_file", str(processed_messages[0]["content"]))

        # Count tokens with file content included
        token_count = self.compacter.count_tokens(
            processed_messages, "claude-3-opus-20240229"
        )

        # Our mock returns 100 when file content is present
        self.assertEqual(token_count, 100)

    def test_file_mention_summary_exclusion(self):
        """Test that file mentions are excluded from summaries."""
        # Create a message with a file mention
        messages = [
            {"role": "user", "content": f"Check this file @{self.test_file_path}"}
        ]

        # Process the messages to inline file mentions
        processed_messages = _inline_latest_file_mentions(messages)

        # Get the summary string that would be used for summarization
        summary_string = self.compacter._messages_to_string(
            processed_messages, for_summary=True
        )

        # Verify the summary string does not include the file content
        self.assertNotIn("This is test file content", summary_string)

        # Verify the summary string includes a reference to the file
        self.assertIn("[Referenced file:", summary_string)

        # Get the full string that would be used for token counting
        full_string = self.compacter._messages_to_string(
            processed_messages, for_summary=False
        )

        # Verify the full string includes the file content
        self.assertIn("This is test file content", full_string)

    def test_generate_summary(self):
        """Test that generate_summary correctly handles file mentions."""
        # Create a message with a file mention
        messages = [
            {"role": "user", "content": f"Check this file @{self.test_file_path}"}
        ]

        # Process the messages to inline file mentions
        processed_messages = _inline_latest_file_mentions(messages)

        # Generate a summary
        summary = self.compacter.generate_summary(
            processed_messages, "claude-3-opus-20240229"
        )

        # Verify the summary has the expected token counts
        # Original should be 100 (mock value with file content)
        self.assertEqual(summary.original_token_count, 100)

        # Summary should be 50 (mock value without file content)
        self.assertEqual(summary.summary_token_count, 50)

        # Verify the compaction ratio
        self.assertEqual(summary.compaction_ratio, 0.5)  # 50/100


if __name__ == "__main__":
    unittest.main()
