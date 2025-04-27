#!/usr/bin/env python3
"""
Unit tests for the conversation compaction functionality.
"""

import json
import unittest
from unittest import mock
from pathlib import Path
import tempfile
import shutil


from heare.developer.compacter import ConversationCompacter
from heare.developer.context import AgentContext
from heare.developer.sandbox import Sandbox, SandboxMode
from heare.developer.user_interface import UserInterface


class MockAnthropicClient:
    """Mock for the Anthropic client."""

    def __init__(self, token_counts=None, response_content=None):
        """Initialize the mock client.

        Args:
            token_counts: Dictionary mapping input text to token counts
            response_content: Content to return in the response
        """
        self.token_counts = token_counts or {"Hello": 1, "Hello world": 2}
        self.response_content = response_content or "Summary of the conversation"
        self.count_tokens_called = False
        self.messages_create_called = False

    def count_tokens(self, model, prompt):
        """Mock for the count_tokens method."""
        self.count_tokens_called = True

        # Return a token count based on text length if not in token_counts
        token_count = self.token_counts.get(prompt, len(prompt.split()) // 3 + 1)

        # Create a response object with a token_count attribute
        class TokenResponse:
            def __init__(self, count):
                self.token_count = count

        return TokenResponse(token_count)

    def messages(self):
        """Mock for the messages object."""
        return self


class MockUserInterface(UserInterface):
    """Mock for the user interface."""

    def __init__(self):
        self.system_messages = []

    def handle_system_message(self, message, markdown=True):
        """Record system messages."""
        self.system_messages.append(message)

    def permission_callback(self, action, resource, sandbox_mode, action_arguments):
        """Always allow."""
        return True

    def permission_rendering_callback(self, action, resource, action_arguments):
        """Do nothing."""


class TestConversationCompaction(unittest.TestCase):
    """Tests for the conversation compaction functionality."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()

        # Create sample messages
        self.sample_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there! How can I help you today?"},
            {"role": "user", "content": "Tell me about conversation compaction"},
            {
                "role": "assistant",
                "content": "Conversation compaction is a technique...",
            },
        ]

        # Create a mock client
        self.mock_client = MockAnthropicClient()

        # Create a model spec
        self.model_spec = {
            "title": "claude-3-5-sonnet-latest",
            "pricing": {"input": 3.00, "output": 15.00},
            "cache_pricing": {"write": 3.75, "read": 0.30},
            "max_tokens": 8192,
        }

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)

    @mock.patch("anthropic.Client")
    def test_count_tokens(self, mock_client_class):
        """Test token counting."""
        # Setup mock
        mock_client_class.return_value = self.mock_client

        # Create compacter
        compacter = ConversationCompacter()

        # Count tokens
        tokens = compacter.count_tokens(
            self.sample_messages, "claude-3-5-sonnet-latest"
        )

        # Assert token count was called
        self.assertTrue(self.mock_client.count_tokens_called)

        # Token count should be positive
        self.assertGreater(tokens, 0)

    @mock.patch("anthropic.Client")
    def test_should_compact(self, mock_client_class):
        """Test should_compact method."""
        # Setup mock with high token count
        high_token_client = MockAnthropicClient(token_counts={"any": 200000})
        mock_client_class.return_value = high_token_client

        # Create compacter with low threshold
        compacter = ConversationCompacter(token_threshold=1000)

        # Should compact should return True
        self.assertTrue(
            compacter.should_compact(self.sample_messages, "claude-3-5-sonnet-latest")
        )

        # Setup mock with low token count
        low_token_client = MockAnthropicClient(token_counts={"any": 500})
        mock_client_class.return_value = low_token_client

        # Create new compacter instance
        compacter = ConversationCompacter(token_threshold=1000)

        # Should compact should return False
        self.assertFalse(
            compacter.should_compact(self.sample_messages, "claude-3-5-sonnet-latest")
        )

    @mock.patch("anthropic.Client")
    def test_context_flush_with_compaction(self, mock_client_class):
        """Test context flush with compaction."""

        # Create response mock
        class MockResponse:
            def __init__(self):
                self.content = [
                    type(
                        "obj",
                        (object,),
                        {"text": "This is a summary of the conversation."},
                    )
                ]

        messages_method = mock.MagicMock()
        messages_method.create.return_value = MockResponse()

        # Setup mock client to return messages_method for messages
        mock_client_instance = mock.MagicMock()
        mock_client_instance.messages = messages_method
        mock_client_instance.count_tokens.side_effect = lambda model, prompt: type(
            "obj", (object,), {"token_count": 50000 if len(prompt) > 100 else 100}
        )

        mock_client_class.return_value = mock_client_instance

        # Create user interface
        ui = MockUserInterface()

        # Create sandbox
        sandbox = Sandbox(self.test_dir, mode=SandboxMode.ALLOW_ALL)

        # Create agent context
        context = AgentContext(
            parent_session_id=None,
            session_id="test-session",
            model_spec=self.model_spec,
            sandbox=sandbox,
            user_interface=ui,
            usage=[],
            memory_manager=None,
        )

        # Create long messages to trigger compaction
        long_messages = []
        for i in range(100):
            long_messages.append(
                {
                    "role": "user",
                    "content": f"Message {i} with some content that takes up space",
                }
            )
            long_messages.append(
                {
                    "role": "assistant",
                    "content": f"Response {i} with more content to increase token count",
                }
            )

        # Setup temporary history directory
        history_dir = Path(self.test_dir) / ".hdev" / "history" / context.session_id
        history_dir.mkdir(parents=True, exist_ok=True)

        # Monkeypatch the home directory function to use our test directory
        with mock.patch("pathlib.Path.home", return_value=Path(self.test_dir)):
            # Flush with compaction
            context.flush(long_messages, compact=True)

            # Check for system message about compaction
            compaction_messages = [
                msg for msg in ui.system_messages if "Conversation compacted" in msg
            ]
            self.assertTrue(
                len(compaction_messages) > 0, "No compaction message was displayed"
            )

            # Check that the file was created
            history_file = history_dir / "root.json"
            self.assertTrue(history_file.exists(), "History file wasn't created")

            # Load the file and check for compaction metadata
            with open(history_file, "r") as f:
                data = json.load(f)
                self.assertIn("compaction", data, "Compaction metadata not present")


if __name__ == "__main__":
    unittest.main()
