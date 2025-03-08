"""
Tests for the issue tracking CLI functionality.
"""

import os
import shutil
import pytest
from unittest.mock import patch, MagicMock

from heare.developer.tools.issues_cli import (
    config_issues,
    issues,
    read_config,
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
def test_read_write_config(mock_config_dir, mock_config_file, test_config_file):
    mock_config_file.__str__.return_value = test_config_file
    mock_config_dir.__str__.return_value = os.path.dirname(test_config_file)

    # Test writing config
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

    write_config(test_config)
    assert os.path.exists(test_config_file)

    # Test reading config
    read_config_result = read_config()
    assert read_config_result == test_config


@patch("heare.developer.tools.issues_cli.read_config")
def test_config_issues_help(mock_read_config, mock_user_interface, mock_sandbox):
    # Test displaying help when just "config" is used
    config_issues(mock_user_interface, mock_sandbox, "config")
    mock_user_interface.handle_system_message.assert_called_once()
    assert (
        "Usage: /config [type]"
        in mock_user_interface.handle_system_message.call_args[0][0]
    )


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
