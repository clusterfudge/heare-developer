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
import shlex


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

    def _validate_and_sanitize_command(self, command: str) -> Tuple[bool, str]:
        """Validate and sanitize a command for safe shell execution.

        Returns:
            Tuple of (is_valid, sanitized_command_or_error_message)
        """
        # Check for unbalanced quotes
        if not self._check_quote_balance(command):
            return False, f"Command has unbalanced quotes: {command}"

        # For commands with quotes, use a safer execution method
        if self._has_complex_quotes(command):
            return True, self._sanitize_complex_command(command)

        return True, command

    def _check_quote_balance(self, command: str) -> bool:
        """Check if quotes are properly balanced in a command."""
        try:
            # Use shlex to parse and validate quote balance
            shlex.split(command)
            return True
        except ValueError:
            # shlex.split raises ValueError for unbalanced quotes
            # However, some valid shell constructs like 'It\'s' fail shlex
            # So let's do a simpler manual check for our use case
            return self._manual_quote_check(command)

    def _manual_quote_check(self, command: str) -> bool:
        """Manual quote balance check for edge cases."""
        single_quotes = 0
        double_quotes = 0
        i = 0

        while i < len(command):
            char = command[i]

            if char == "'" and (i == 0 or command[i - 1] != "\\"):
                single_quotes += 1
            elif char == '"' and (i == 0 or command[i - 1] != "\\"):
                double_quotes += 1

            i += 1

        # For our purposes, we consider quotes balanced if they appear in pairs
        # or if we have shell-style quote structures
        return single_quotes % 2 == 0 and double_quotes % 2 == 0

    def _has_complex_quotes(self, command: str) -> bool:
        """Check if command has complex quote usage that needs special handling."""
        # Check for escaped quotes within quotes
        if re.search(
            r"'[^']*\\'[^']*'", command
        ):  # Single quotes with escaped single quotes
            return True
        if re.search(
            r'"[^"]*\\"[^"]*"', command
        ):  # Double quotes with escaped double quotes
            return True
        if "\n" in command:  # Multi-line commands
            return True
        return False

    def _sanitize_complex_command(self, command: str) -> str:
        """Sanitize complex commands with quotes for safe execution."""
        # For single quotes with escaped single quotes, convert to double quotes
        if re.search(r"'[^']*\\'[^']*'", command):
            # Convert echo 'It\'s working' to echo "It's working"
            # This is a more precise regex replacement
            def replace_escaped_single_quotes(match):
                content = match.group(1) + "'" + match.group(2)
                return f'"{content}"'

            command = re.sub(
                r"'([^']*)\\'([^']*)'", replace_escaped_single_quotes, command
            )

        # For multi-line strings, ensure proper escaping
        if "\n" in command:
            # Replace literal newlines with proper shell escaping
            command = command.replace("\n", "\\n")

        return command

    def _detect_shell_stuck_state(self, output: str) -> Optional[str]:
        """Detect if shell is stuck in an incomplete state.

        Returns:
            The stuck state type if detected (e.g., 'quote>', 'dquote>'), None otherwise
        """
        lines = output.strip().split("\n")
        if not lines:
            return None

        # Check the last line first (most recent state)
        last_line = lines[-1].strip()

        # Check for common stuck states in order of specificity
        stuck_states = [
            "dquote>",
            "quote>",
            "heredoc>",
            "cmdsubst>",
            "for>",
            "while>",
            "if>",
        ]
        for state in stuck_states:
            if last_line.endswith(state):
                return state

        # If last line doesn't show stuck state, check previous lines
        if len(lines) > 1:
            for line in reversed(lines[-3:-1]):  # Check 2nd and 3rd to last lines
                line = line.strip()
                for state in stuck_states:
                    if line.endswith(state):
                        return state

        return None

    def _recover_from_stuck_state(
        self, tmux_session_name: str, stuck_state: str
    ) -> Tuple[bool, str]:
        """Attempt to recover from a stuck shell state.

        Args:
            tmux_session_name: Name of the tmux session
            stuck_state: The type of stuck state detected

        Returns:
            Tuple of (success, message)
        """
        recovery_commands = {
            "quote>": ["'", "Enter"],  # Close single quote
            "dquote>": ['"', "Enter"],  # Close double quote
            "heredoc>": ["EOF", "Enter"],  # Close heredoc
            "cmdsubst>": [")", "Enter"],  # Close command substitution
        }

        # For other states or as fallback, send Ctrl+C
        if stuck_state not in recovery_commands:
            recovery_commands[stuck_state] = ["C-c"]

        commands = recovery_commands[stuck_state]

        for cmd in commands:
            exit_code, stdout, stderr = self._run_tmux_command(
                ["tmux", "send-keys", "-t", tmux_session_name, cmd]
            )
            if exit_code != 0:
                return False, f"Failed to send recovery command '{cmd}': {stderr}"

        # Give a moment for the recovery to take effect
        time.sleep(0.2)

        return True, f"Attempted recovery from {stuck_state} state"

    def _send_command_to_session(
        self, tmux_session_name: str, command: str
    ) -> Tuple[bool, str]:
        """Send a command to a tmux session with quote handling and recovery."""
        # Validate and sanitize the command
        is_valid, sanitized_command = self._validate_and_sanitize_command(command)
        if not is_valid:
            return False, sanitized_command  # sanitized_command contains error message

        # Send the sanitized command
        exit_code, stdout, stderr = self._run_tmux_command(
            ["tmux", "send-keys", "-t", tmux_session_name, sanitized_command, "Enter"]
        )

        if exit_code != 0:
            return False, f"Failed to send command: {stderr}"

        # Check for stuck shell state after command execution
        time.sleep(0.1)  # Brief pause to let command execute

        # Capture current shell state
        capture_exit_code, capture_output, capture_stderr = self._run_tmux_command(
            ["tmux", "capture-pane", "-t", tmux_session_name, "-p"]
        )

        if capture_exit_code == 0:
            stuck_state = self._detect_shell_stuck_state(capture_output)
            if stuck_state:
                # Attempt recovery
                recovery_success, recovery_msg = self._recover_from_stuck_state(
                    tmux_session_name, stuck_state
                )
                if recovery_success:
                    return (
                        True,
                        f"Command sent successfully (recovered from {stuck_state})",
                    )
                else:
                    return (
                        False,
                        f"Command sent but shell stuck in {stuck_state}. Recovery failed: {recovery_msg}",
                    )

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
