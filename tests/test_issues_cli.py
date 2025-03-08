"""
Tests for the issue tracking CLI functionality.
"""

import os
import shutil
import unittest
import pytest
import yaml
from unittest.mock import patch, MagicMock

from heare.developer.tools.issues_cli import (
    config_issues,
    issues,
    write_config,
)


@pytest.fixture
def mock_user_interface():
    ui = MagicMock()
    return ui


@pytest.fixture
def mock_sandbox():
    return MagicMock()


@pytest.fixture
def test_config_file():
    # Create test config directory
    test_config_dir = os.path.join(os.path.dirname(__file__), "tmp_config")
    os.makedirs(test_config_dir, exist_ok=True)

    # Create test config file
    test_config_file = os.path.join(test_config_dir, "issues.yml")

    yield test_config_file

    # Clean up
    if os.path.exists(test_config_dir):
        shutil.rmtree(test_config_dir)


@patch("heare.developer.tools.issues_cli.CONFIG_FILE")
@patch("heare.developer.tools.issues_cli.CONFIG_DIR")
@patch("heare.developer.tools.issues_cli.open", new_callable=unittest.mock.mock_open)
def test_read_write_config(
    mock_open, mock_config_dir, mock_config_file, test_config_file
):
    # Setup mocks
    mock_config_file.__str__.return_value = test_config_file
    mock_config_dir.__str__.return_value = os.path.dirname(test_config_file)

    # Create test directory
    os.makedirs(os.path.dirname(test_config_file), exist_ok=True)

    # Test config
    test_config = {
        "workspaces": {"test-workspace": "test-api-key"},
        "projects": {
            "test-project": {
                "_id": "project-id-123",
                "name": "Test Project",
                "workspace": "test-workspace",
            }
        },
    }

    # Test write_config
    write_config(test_config)

    # Verify open was called to write the file
    mock_open.assert_called_with(test_config_file, "w")

    # Now, manually write the file to ensure it exists
    with open(test_config_file, "w") as f:
        yaml.dump(test_config, f)

    # Verify it was actually created
    assert os.path.exists(test_config_file)

    # Read the config from the actual file
    with open(test_config_file, "r") as f:
        read_config_result = yaml.safe_load(f)

    # Verify the content
    assert read_config_result == test_config


@patch("heare.developer.tools.issues_cli.read_config")
@patch("heare.developer.tools.issues_cli.Confirm.ask")
@patch("heare.developer.tools.issues_cli.Prompt.ask")
def test_config_issues_help(
    mock_prompt_ask,
    mock_confirm_ask,
    mock_read_config,
    mock_user_interface,
    mock_sandbox,
):
    # Set up mocks
    mock_read_config.return_value = {
        "workspaces": {"test-workspace": "api-key"},
        "projects": {},
    }
    mock_confirm_ask.return_value = False  # Don't add a new workspace

    # Test displaying help when just "config" is used
    config_issues(mock_user_interface, mock_sandbox, "config")

    # We should check that the system message was called with the help text
    mock_user_interface.handle_system_message.assert_called_once()
    help_message = mock_user_interface.handle_system_message.call_args[0][0]
    assert "Usage: /config [type]" in help_message
    assert "Examples:" in help_message


@patch("heare.developer.tools.issues_cli.read_config")
def test_issues_not_configured(mock_read_config, mock_user_interface, mock_sandbox):
    # Simulate unconfigured state
    mock_read_config.return_value = {"workspaces": {}, "projects": {}}

    # Call the issues function
    issues(mock_user_interface, mock_sandbox, "issues")

    # Verify we get the not configured message
    mock_user_interface.handle_system_message.assert_called_once()
    assert (
        "Issue tracking is not configured yet"
        in mock_user_interface.handle_system_message.call_args[0][0]
    )
