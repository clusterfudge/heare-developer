"""Tests for interactive bash command timeout functionality."""

import pytest

from heare.developer.context import AgentContext
from heare.developer.sandbox import SandboxMode
from heare.developer.user_interface import UserInterface
from heare.developer.tools.repl import (
    run_bash_command,
    _run_bash_command_with_interactive_timeout,
)


class MockUserInterface(UserInterface):
    """Mock user interface for testing."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.response_index = 0
        self.messages = []

    def handle_assistant_message(self, message: str) -> None:
        pass

    def handle_system_message(self, message: str, markdown=True) -> None:
        self.messages.append(("system", message))

    def permission_callback(
        self, action: str, resource: str, sandbox_mode: SandboxMode, action_arguments
    ):
        return True

    def permission_rendering_callback(
        self, action: str, resource: str, action_arguments
    ):
        pass

    def handle_tool_use(self, tool_name: str, tool_params):
        pass

    def handle_tool_result(self, name: str, result):
        pass

    async def get_user_input(self, prompt: str = "") -> str:
        if self.response_index < len(self.responses):
            response = self.responses[self.response_index]
            self.response_index += 1
            return response
        return "C"  # Default to continue

    def handle_user_input(self, user_input: str) -> str:
        return user_input

    def display_token_count(self, *args, **kwargs):
        pass

    def display_welcome_message(self):
        pass

    def status(self, message: str, spinner: str = None):
        class DummyContext:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        return DummyContext()

    def bare(self, message):
        pass


class TestInteractiveBashTimeout:
    """Test suite for interactive bash timeout functionality."""

    def create_test_context(self, responses=None):
        """Create a test context with mock UI."""
        ui = MockUserInterface(responses)
        return AgentContext.create(
            model_spec={},
            sandbox_mode=SandboxMode.ALLOW_ALL,
            sandbox_contents=[],
            user_interface=ui,
        )

    @pytest.mark.asyncio
    async def test_quick_command_completion(self):
        """Test that quick commands complete without timeout."""
        context = self.create_test_context()

        result = await run_bash_command(context, "echo 'hello world'")

        assert "Exit code: 0" in result
        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_timeout_kill_process(self):
        """Test killing a process when timeout occurs."""
        context = self.create_test_context(responses=["K"])

        result = await _run_bash_command_with_interactive_timeout(
            context, "sleep 2", initial_timeout=0.1
        )

        assert "Command was killed by user" in result
        assert "Execution time:" in result

    @pytest.mark.asyncio
    async def test_timeout_background_process(self):
        """Test backgrounding a process when timeout occurs."""
        context = self.create_test_context(responses=["B"])

        result = await _run_bash_command_with_interactive_timeout(
            context, "sleep 2", initial_timeout=0.1
        )

        assert "Command backgrounded" in result
        assert "PID:" in result
        assert "Process continues running" in result

    @pytest.mark.asyncio
    async def test_timeout_continue_then_kill(self):
        """Test continuing wait then killing process."""
        context = self.create_test_context(responses=["C", "K"])

        # Need a longer sleep to ensure it doesn't complete between timeouts
        result = await _run_bash_command_with_interactive_timeout(
            context, "sleep 3", initial_timeout=0.1
        )

        assert "Command was killed by user" in result

    @pytest.mark.asyncio
    async def test_output_capture_during_timeout(self):
        """Test that output is captured properly during timeout."""
        context = self.create_test_context(responses=["K"])

        # Create a command that produces output then sleeps
        command = "echo 'line1'; echo 'line2'; sleep 2"

        result = await _run_bash_command_with_interactive_timeout(
            context, command, initial_timeout=0.1
        )

        assert "Command was killed by user" in result
        assert "line1" in result
        assert "line2" in result

    @pytest.mark.asyncio
    async def test_dangerous_command_blocked(self):
        """Test that dangerous commands are blocked."""
        context = self.create_test_context()

        result = await run_bash_command(context, "sudo rm -rf /")

        assert "Error: This command is not allowed for safety reasons" in result

    @pytest.mark.asyncio
    async def test_system_message_on_timeout(self):
        """Test that system messages are shown on timeout."""
        ui = MockUserInterface(responses=["K"])
        context = AgentContext.create(
            model_spec={},
            sandbox_mode=SandboxMode.ALLOW_ALL,
            sandbox_contents=[],
            user_interface=ui,
        )

        await _run_bash_command_with_interactive_timeout(
            context, "sleep 2", initial_timeout=0.1
        )

        # Check that system messages were sent
        system_messages = [msg for msg in ui.messages if msg[0] == "system"]
        assert len(system_messages) > 0
        assert any("Command has been running for" in msg[1] for msg in system_messages)
