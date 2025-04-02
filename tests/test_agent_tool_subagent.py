import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from heare.developer.context import AgentContext
from heare.developer.tools.subagent import agent


class JsonSerializableMock:
    """A mock object that can be JSON serialized"""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestAgentToolSubagent(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.home_dir_patch = patch("pathlib.Path.home")
        self.mock_home = self.home_dir_patch.start()
        self.mock_home.return_value = Path(self.temp_dir.name)

        # Create a mock sandbox
        self.mock_sandbox = JsonSerializableMock(
            check_permissions=lambda *args: True,
            read_file=lambda path: f"Content of {path}",
            write_file=lambda path, content: None,
            get_directory_listing=lambda path, recursive: [path],
        )

        # Create a mock user interface
        self.mock_user_interface = JsonSerializableMock(
            get_user_input=lambda prompt: "",
            display_welcome_message=lambda: None,
            handle_system_message=lambda msg: None,
            handle_user_input=lambda msg: None,
            handle_assistant_message=lambda msg: None,
            handle_tool_use=lambda name, input: None,
            handle_tool_result=lambda name, result: None,
            display_token_count=lambda *args: None,
            permission_callback=lambda *args: True,
            permission_rendering_callback=lambda *args: True,
            bare=lambda *args: None,
        )

        # Add a status method that returns a context manager
        class DummyStatus:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def update(self, *args, **kwargs):
                pass

        self.mock_user_interface.status = lambda *args, **kwargs: DummyStatus()

        # Create a model specification
        self.model_spec = {
            "title": "test-model",
            "pricing": {"input": 3.00, "output": 15.00},
            "cache_pricing": {"write": 3.75, "read": 0.30},
        }

    def tearDown(self):
        self.home_dir_patch.stop()
        self.temp_dir.cleanup()

    def create_test_context(self, parent_id=None):
        """Helper to create a test context with proper serialization"""
        return AgentContext(
            session_id=str(uuid4()),
            parent_session_id=parent_id,
            model_spec=self.model_spec,
            sandbox=self.mock_sandbox,
            user_interface=self.mock_user_interface,
            usage=[],
        )

    def test_agent_tool_nested_context_save(self):
        """Test that the agent tool properly saves nested context"""
        # Create a simple chat history
        chat_history = [
            {"role": "user", "content": "Do something"},
            {"role": "assistant", "content": "Task completed"},
        ]

        # Create a parent context
        parent_context = self.create_test_context()

        # Create a capture interface mock
        capture_interface_mock = MagicMock()

        # Patch CaptureInterface constructor
        with patch(
            "heare.developer.tools.subagent.CaptureInterface"
        ) as mock_capture_class:
            mock_capture_class.return_value = capture_interface_mock

            # Mock agent.run to capture the agent_context and return chat history
            with patch("heare.developer.agent.run") as mock_run:
                # Setup mock to save the passed context and return chat history
                def capture_and_return(agent_context, **kwargs):
                    # Save the agent_context for later inspection
                    self.captured_agent_context = agent_context
                    # IMPORTANT: Manually flush the chat history since our mock doesn't run the real agent.run
                    # which would normally handle flushing in its finally block
                    agent_context.flush(chat_history)
                    # Return the chat history
                    return chat_history

                mock_run.side_effect = capture_and_return

                # Call the agent tool
                agent(parent_context, "Do a sub task", "read_file")

                # Verify a sub-agent context was created with parent's session ID
                self.assertIsNotNone(
                    getattr(self, "captured_agent_context", None),
                    "agent.run was not called with an agent_context",
                )
                self.assertEqual(
                    self.captured_agent_context.parent_session_id,
                    parent_context.session_id,
                )

                # Verify the chat history was flushed correctly
                history_dir = (
                    Path(self.temp_dir.name)
                    / ".hdev"
                    / "history"
                    / parent_context.session_id
                )
                sub_agent_file = (
                    history_dir / f"{self.captured_agent_context.session_id}.json"
                )

                self.assertTrue(
                    sub_agent_file.exists(),
                    f"Sub-agent history file not found at {sub_agent_file}",
                )

                # Read the content of the file to verify
                with open(sub_agent_file, "r") as f:
                    saved_data = json.load(f)

                self.assertEqual(
                    saved_data["session_id"], self.captured_agent_context.session_id
                )
                self.assertEqual(
                    saved_data["parent_session_id"], parent_context.session_id
                )
                self.assertEqual(saved_data["messages"], chat_history)
