"""Tests for TmuxSession and TmuxSessionManager classes."""

import pytest
import time
import subprocess
from unittest.mock import Mock, patch

from heare.developer.tools.tmux_session import TmuxSession, TmuxSessionManager


class TestTmuxSession:
    """Test suite for TmuxSession class."""

    def test_session_creation(self):
        """Test basic session creation."""
        session = TmuxSession("test_session", "hdev_test_session_123")

        assert session.name == "test_session"
        assert session.tmux_session_name == "hdev_test_session_123"
        assert session.status == "active"
        assert len(session.commands_executed) == 0
        assert len(session.output_buffer) == 0
        assert len(session.error_buffer) == 0

    def test_add_command(self):
        """Test adding commands to session."""
        session = TmuxSession("test", "hdev_test")

        initial_time = session.last_activity
        time.sleep(0.01)  # Small delay to ensure timestamp difference

        session.add_command("echo hello")

        assert len(session.commands_executed) == 1
        assert session.commands_executed[0]["command"] == "echo hello"
        assert session.last_activity > initial_time

    def test_add_output(self):
        """Test adding output to session buffers."""
        session = TmuxSession("test", "hdev_test")

        session.add_output("stdout line 1\nstdout line 2")
        session.add_output("stderr line 1", is_error=True)

        assert len(session.output_buffer) == 2
        assert len(session.error_buffer) == 1
        assert session.output_buffer[0]["content"] == "stdout line 1"
        assert session.error_buffer[0]["content"] == "stderr line 1"

    def test_get_recent_output(self):
        """Test retrieving recent output."""
        session = TmuxSession("test", "hdev_test")

        session.add_output("line 1")
        session.add_output("line 2")
        session.add_output("error line", is_error=True)

        output = session.get_recent_output(lines=10)

        assert "line 1" in output
        assert "line 2" in output
        assert "error line" in output
        assert "[OUT]" in output
        assert "[ERR]" in output

    def test_get_recent_output_no_errors(self):
        """Test retrieving output without errors."""
        session = TmuxSession("test", "hdev_test")

        session.add_output("line 1")
        session.add_output("error line", is_error=True)

        output = session.get_recent_output(lines=10, include_errors=False)

        assert "line 1" in output
        assert "error line" not in output

    def test_output_buffer_limit(self):
        """Test that output buffer respects maximum size."""
        session = TmuxSession("test", "hdev_test", max_buffer_size=5)

        # Add more lines than buffer size
        for i in range(10):
            session.add_output(f"line {i}")

        # Should only keep the last 5 lines
        assert len(session.output_buffer) == 5
        assert session.output_buffer[-1]["content"] == "line 9"

    def test_get_session_info(self):
        """Test session info retrieval."""
        session = TmuxSession("test", "hdev_test")
        session.add_command("echo hello")
        session.add_output("output line")

        info = session.get_session_info()

        assert info["name"] == "test"
        assert info["status"] == "active"
        assert info["commands_executed"] == 1
        assert info["output_lines"] == 1
        assert "created_at" in info
        assert "last_activity" in info


class TestTmuxSessionManager:
    """Test suite for TmuxSessionManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = TmuxSessionManager(session_prefix="test_hdev", max_sessions=3)

    def test_session_manager_creation(self):
        """Test session manager initialization."""
        assert self.manager.session_prefix == "test_hdev"
        assert self.manager.max_sessions == 3
        assert len(self.manager.sessions) == 0

    def test_validate_session_name(self):
        """Test session name validation."""
        assert self.manager._validate_session_name("valid_name-123")
        assert self.manager._validate_session_name("simple")
        assert not self.manager._validate_session_name("invalid name")
        assert not self.manager._validate_session_name("invalid@name")
        assert not self.manager._validate_session_name("invalid.name")

    def test_generate_tmux_session_name(self):
        """Test tmux session name generation."""
        name = self.manager._generate_tmux_session_name("test")

        assert name.startswith("test_hdev_test_")
        assert len(name.split("_")) == 5  # prefix_user_timestamp_uuid

    @patch("heare.developer.tools.tmux_session.subprocess.run")
    def test_run_tmux_command(self, mock_run):
        """Test tmux command execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        exit_code, stdout, stderr = self.manager._run_tmux_command(
            ["tmux", "list-sessions"]
        )

        assert exit_code == 0
        assert stdout == "success"
        assert stderr == ""
        mock_run.assert_called_once()

    @patch("heare.developer.tools.tmux_session.subprocess.run")
    def test_run_tmux_command_timeout(self, mock_run):
        """Test tmux command timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired(["tmux"], 30)

        exit_code, stdout, stderr = self.manager._run_tmux_command(
            ["tmux", "list-sessions"]
        )

        assert exit_code == -1
        assert stdout == ""
        assert stderr == "Command timed out"

    @patch("heare.developer.tools.tmux_session.TmuxSessionManager._run_tmux_command")
    def test_create_session_success(self, mock_run_command):
        """Test successful session creation."""
        mock_run_command.return_value = (0, "", "")

        success, message = self.manager.create_session("test_session")

        assert success is True
        assert "successfully" in message
        assert "test_session" in self.manager.sessions
        assert len(self.manager.sessions) == 1

    @patch("heare.developer.tools.tmux_session.TmuxSessionManager._run_tmux_command")
    def test_create_session_failure(self, mock_run_command):
        """Test session creation failure."""
        mock_run_command.return_value = (1, "", "tmux error")

        success, message = self.manager.create_session("test_session")

        assert success is False
        assert "Failed to create" in message
        assert "test_session" not in self.manager.sessions

    def test_create_session_invalid_name(self):
        """Test session creation with invalid name."""
        success, message = self.manager.create_session("invalid name")

        assert success is False
        assert "Invalid session name" in message

    def test_create_session_duplicate_name(self):
        """Test creating session with duplicate name."""
        with patch(
            "heare.developer.tools.tmux_session.TmuxSessionManager._run_tmux_command"
        ) as mock_run:
            mock_run.return_value = (0, "", "")

            # Create first session
            success1, _ = self.manager.create_session("duplicate")
            assert success1 is True

            # Try to create second session with same name
            success2, message = self.manager.create_session("duplicate")
            assert success2 is False
            assert "already exists" in message

    def test_create_session_max_limit(self):
        """Test session creation limit enforcement."""
        with patch(
            "heare.developer.tools.tmux_session.TmuxSessionManager._run_tmux_command"
        ) as mock_run:
            mock_run.return_value = (0, "", "")

            # Create sessions up to limit
            for i in range(3):
                success, _ = self.manager.create_session(f"session{i}")
                assert success is True

            # Try to create one more
            success, message = self.manager.create_session("overflow")
            assert success is False
            assert "Maximum number of sessions" in message

    @patch("heare.developer.tools.tmux_session.TmuxSessionManager._run_tmux_command")
    def test_destroy_session(self, mock_run_command):
        """Test session destruction."""
        mock_run_command.return_value = (0, "", "")

        # Create a session first
        self.manager.create_session("test_session")
        assert "test_session" in self.manager.sessions

        # Destroy it
        success, message = self.manager.destroy_session("test_session")

        assert success is True
        assert "destroyed successfully" in message
        assert "test_session" not in self.manager.sessions

    def test_destroy_nonexistent_session(self):
        """Test destroying non-existent session."""
        success, message = self.manager.destroy_session("nonexistent")

        assert success is False
        assert "not found" in message

    @patch("heare.developer.tools.tmux_session.TmuxSessionManager._run_tmux_command")
    def test_execute_command(self, mock_run_command):
        """Test command execution in session."""
        mock_run_command.return_value = (0, "", "")

        # Create a session
        self.manager.create_session("test_session")

        # Execute command
        success, message = self.manager.execute_command("test_session", "echo hello")

        assert success is True
        assert "executed" in message

        # Check command was recorded
        session = self.manager.sessions["test_session"]
        assert len(session.commands_executed) == 1
        assert session.commands_executed[0]["command"] == "echo hello"

    def test_execute_command_nonexistent_session(self):
        """Test command execution in non-existent session."""
        success, message = self.manager.execute_command("nonexistent", "echo hello")

        assert success is False
        assert "not found" in message

    @patch("heare.developer.tools.tmux_session.TmuxSessionManager._run_tmux_command")
    def test_capture_session_output(self, mock_run_command):
        """Test output capture from session."""
        mock_run_command.return_value = (0, "captured output", "")

        # Create a session
        self.manager.create_session("test_session")

        # Capture output
        success, output = self.manager.capture_session_output("test_session")

        assert success is True
        assert "captured output" in output or "No output available" in output

    def test_capture_output_nonexistent_session(self):
        """Test output capture from non-existent session."""
        success, message = self.manager.capture_session_output("nonexistent")

        assert success is False
        assert "not found" in message

    @patch("heare.developer.tools.tmux_session.TmuxSessionManager._run_tmux_command")
    def test_list_sessions(self, mock_run_command):
        """Test session listing."""
        mock_run_command.return_value = (0, "", "")

        # Create some sessions
        self.manager.create_session("session1")
        self.manager.create_session("session2")

        sessions = self.manager.list_sessions()

        assert len(sessions) == 2
        assert any(s["name"] == "session1" for s in sessions)
        assert any(s["name"] == "session2" for s in sessions)

    @patch("heare.developer.tools.tmux_session.TmuxSessionManager._run_tmux_command")
    def test_update_session_statuses(self, mock_run_command):
        """Test session status updates."""
        # Mock tmux list-sessions to return one active session
        mock_run_command.return_value = (0, "hdev_test_session_123: 1 windows", "")

        # Create sessions
        self.manager.create_session("active_session")
        self.manager.create_session("inactive_session")

        # Manually set tmux names for testing
        self.manager.sessions[
            "active_session"
        ].tmux_session_name = "hdev_test_session_123"
        self.manager.sessions[
            "inactive_session"
        ].tmux_session_name = "hdev_other_session"

        # Update statuses
        self.manager._update_session_statuses()

        assert self.manager.sessions["active_session"].status == "active"
        assert self.manager.sessions["inactive_session"].status == "inactive"

    @patch("heare.developer.tools.tmux_session.TmuxSessionManager._run_tmux_command")
    def test_cleanup_all_sessions(self, mock_run_command):
        """Test cleanup of all sessions."""
        mock_run_command.return_value = (0, "", "")

        # Create some sessions
        self.manager.create_session("session1")
        self.manager.create_session("session2")

        assert len(self.manager.sessions) == 2

        # Cleanup all
        self.manager.cleanup_all_sessions()

        assert len(self.manager.sessions) == 0


class TestTmuxSessionManagerIntegration:
    """Integration tests that require tmux to be available."""

    @pytest.fixture(autouse=True)
    def check_tmux_available(self):
        """Skip integration tests if tmux is not available."""
        try:
            subprocess.run(["tmux", "-V"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("tmux not available")

    def test_create_and_destroy_real_session(self):
        """Test creating and destroying a real tmux session."""
        manager = TmuxSessionManager(session_prefix="test_integration")

        # Create session
        success, message = manager.create_session("real_test")
        assert success is True

        # Verify session exists in tmux
        result = subprocess.run(
            ["tmux", "list-sessions"], capture_output=True, text=True
        )
        assert any(
            "test_integration_real_test" in line for line in result.stdout.split("\n")
        )

        # Destroy session
        success, message = manager.destroy_session("real_test")
        assert success is True

        # Verify session no longer exists
        result = subprocess.run(
            ["tmux", "list-sessions"], capture_output=True, text=True
        )
        assert not any(
            "test_integration_real_test" in line for line in result.stdout.split("\n")
        )

    def test_execute_command_in_real_session(self):
        """Test executing commands in a real session."""
        manager = TmuxSessionManager(session_prefix="test_integration")

        # Create session
        success, message = manager.create_session("cmd_test")
        assert success is True

        try:
            # Execute command
            success, message = manager.execute_command(
                "cmd_test", "echo 'integration test'"
            )
            assert success is True

            # Give command time to execute
            time.sleep(0.5)

            # Capture output
            success, output = manager.capture_session_output("cmd_test")
            assert success is True
            assert "integration test" in output

        finally:
            # Cleanup
            manager.destroy_session("cmd_test")
