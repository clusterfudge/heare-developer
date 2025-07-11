"""
Tmux session management classes for the TmuxTool.

This module provides the core session management functionality for persistent
shell sessions using tmux.
"""

import subprocess
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import atexit
import re


class TmuxSession:
    """Represents a single tmux session with output buffering and state tracking."""

    def __init__(self, name: str, tmux_session_name: str, max_buffer_size: int = 1000):
        self.name = name
        self.tmux_session_name = tmux_session_name
        self.created_at = datetime.now()
        self.last_activity = self.created_at
        self.commands_executed = []
        self.status = "active"  # active, inactive, error
        self.max_buffer_size = max_buffer_size

        # Output buffering with circular buffer
        self.output_buffer = deque(maxlen=max_buffer_size)
        self.error_buffer = deque(maxlen=max_buffer_size)

        # Threading for output capture
        self._output_thread = None
        self._stop_output_capture = False

    def add_command(self, command: str):
        """Record a command execution."""
        self.commands_executed.append(
            {
                "command": command,
                "timestamp": datetime.now(),
            }
        )
        self.last_activity = datetime.now()

    def add_output(self, output: str, is_error: bool = False):
        """Add output to the appropriate buffer."""
        timestamp = datetime.now()
        buffer = self.error_buffer if is_error else self.output_buffer

        # Split output into lines and add each with timestamp
        for line in output.splitlines():
            buffer.append(
                {
                    "timestamp": timestamp,
                    "content": line,
                }
            )

        self.last_activity = timestamp

    def get_recent_output(self, lines: int = 50, include_errors: bool = True) -> str:
        """Get recent output from the session."""
        result = []

        # Combine and sort output by timestamp
        all_output = []

        # Add regular output
        for entry in self.output_buffer:
            all_output.append(("stdout", entry))

        # Add error output if requested
        if include_errors:
            for entry in self.error_buffer:
                all_output.append(("stderr", entry))

        # Sort by timestamp
        all_output.sort(key=lambda x: x[1]["timestamp"])

        # Take the most recent entries
        recent_output = all_output[-lines:] if lines > 0 else all_output

        # Format output
        for output_type, entry in recent_output:
            timestamp_str = entry["timestamp"].strftime("%H:%M:%S")
            prefix = "[ERR]" if output_type == "stderr" else "[OUT]"
            result.append(f"{timestamp_str} {prefix} {entry['content']}")

        return "\n".join(result) if result else "No output available"

    def get_session_info(self) -> Dict:
        """Get session information for display."""
        return {
            "name": self.name,
            "tmux_session_name": self.tmux_session_name,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "commands_executed": len(self.commands_executed),
            "output_lines": len(self.output_buffer),
            "error_lines": len(self.error_buffer),
        }


class TmuxSessionManager:
    """Manages multiple tmux sessions with cleanup and monitoring."""

    def __init__(self, session_prefix: str = "hdev", max_sessions: int = 10):
        self.session_prefix = session_prefix
        self.max_sessions = max_sessions
        self.sessions: Dict[str, TmuxSession] = {}
        self.cleanup_registered = False

        # Register cleanup handler
        if not self.cleanup_registered:
            atexit.register(self.cleanup_all_sessions)
            self.cleanup_registered = True

    def _generate_tmux_session_name(self, user_name: str) -> str:
        """Generate a unique tmux session name."""
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        return f"{self.session_prefix}_{user_name}_{timestamp}_{unique_id}"

    def _validate_session_name(self, name: str) -> bool:
        """Validate session name contains only allowed characters."""
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", name))

    def _run_tmux_command(self, command: List[str]) -> Tuple[int, str, str]:
        """Run a tmux command and return exit code, stdout, stderr."""
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)

    def create_session(
        self, session_name: str, initial_command: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Create a new tmux session."""
        if not self._validate_session_name(session_name):
            return (
                False,
                "Invalid session name. Use only alphanumeric characters, underscores, and hyphens.",
            )

        if session_name in self.sessions:
            return False, f"Session '{session_name}' already exists."

        if len(self.sessions) >= self.max_sessions:
            return False, f"Maximum number of sessions ({self.max_sessions}) reached."

        # Generate unique tmux session name
        tmux_session_name = self._generate_tmux_session_name(session_name)

        # Create tmux session
        command = ["tmux", "new-session", "-d", "-s", tmux_session_name]
        if initial_command:
            command.extend(["-c", initial_command])

        exit_code, stdout, stderr = self._run_tmux_command(command)

        if exit_code != 0:
            return False, f"Failed to create tmux session: {stderr}"

        # Create session object
        session = TmuxSession(session_name, tmux_session_name)
        self.sessions[session_name] = session

        # Execute initial command if provided
        if initial_command:
            session.add_command(initial_command)
            self._send_command_to_session(tmux_session_name, initial_command)

        return True, f"Session '{session_name}' created successfully."

    def destroy_session(self, session_name: str) -> Tuple[bool, str]:
        """Destroy a tmux session."""
        if session_name not in self.sessions:
            return False, f"Session '{session_name}' not found."

        session = self.sessions[session_name]

        # Kill the tmux session
        exit_code, stdout, stderr = self._run_tmux_command(
            ["tmux", "kill-session", "-t", session.tmux_session_name]
        )

        # Remove from our tracking (even if tmux command failed)
        del self.sessions[session_name]

        if exit_code != 0:
            return (
                True,
                f"Session '{session_name}' removed (tmux cleanup may have failed: {stderr})",
            )

        return True, f"Session '{session_name}' destroyed successfully."

    def list_sessions(self) -> List[Dict]:
        """List all active sessions."""
        # Update session statuses by checking tmux
        self._update_session_statuses()

        return [session.get_session_info() for session in self.sessions.values()]

    def get_session(self, session_name: str) -> Optional[TmuxSession]:
        """Get a specific session by name."""
        return self.sessions.get(session_name)

    def execute_command(self, session_name: str, command: str) -> Tuple[bool, str]:
        """Execute a command in a specific session."""
        if session_name not in self.sessions:
            return False, f"Session '{session_name}' not found."

        session = self.sessions[session_name]

        # Send command to tmux session
        success, message = self._send_command_to_session(
            session.tmux_session_name, command
        )

        if success:
            session.add_command(command)
            return True, f"Command executed in session '{session_name}'"
        else:
            return False, message

    def _send_command_to_session(
        self, tmux_session_name: str, command: str
    ) -> Tuple[bool, str]:
        """Send a command to a tmux session."""
        exit_code, stdout, stderr = self._run_tmux_command(
            ["tmux", "send-keys", "-t", tmux_session_name, command, "Enter"]
        )

        if exit_code != 0:
            return False, f"Failed to send command: {stderr}"

        return True, "Command sent successfully"

    def capture_session_output(
        self, session_name: str, lines: int = 50
    ) -> Tuple[bool, str]:
        """Capture recent output from a session."""
        if session_name not in self.sessions:
            return False, f"Session '{session_name}' not found."

        session = self.sessions[session_name]

        # Capture output from tmux
        exit_code, stdout, stderr = self._run_tmux_command(
            ["tmux", "capture-pane", "-t", session.tmux_session_name, "-p"]
        )

        if exit_code != 0:
            return False, f"Failed to capture output: {stderr}"

        # Update session output buffer
        if stdout:
            session.add_output(stdout)

        # Return recent output
        return True, session.get_recent_output(lines)

    def _update_session_statuses(self):
        """Update session statuses by checking tmux."""
        # Get list of active tmux sessions
        exit_code, stdout, stderr = self._run_tmux_command(["tmux", "list-sessions"])

        if exit_code != 0:
            # If tmux command fails, mark all sessions as inactive
            for session in self.sessions.values():
                session.status = "inactive"
            return

        # Parse tmux session list
        active_sessions = set()
        for line in stdout.splitlines():
            if ":" in line:
                session_name = line.split(":")[0]
                active_sessions.add(session_name)

        # Update session statuses
        for session in self.sessions.values():
            if session.tmux_session_name in active_sessions:
                session.status = "active"
            else:
                session.status = "inactive"

    def cleanup_all_sessions(self):
        """Clean up all managed sessions."""
        for session_name in list(self.sessions.keys()):
            try:
                self.destroy_session(session_name)
            except Exception as e:
                print(f"Error cleaning up session {session_name}: {e}")


# Global session manager instance
_session_manager = None


def get_session_manager() -> TmuxSessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = TmuxSessionManager()
    return _session_manager
