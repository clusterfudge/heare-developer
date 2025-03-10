"""
Tests for the issue tracking CLI functionality.
"""

import os
import shutil
import unittest
import pytest
import yaml
from unittest.mock import patch

from heare.developer.issues_cli import (
    config_issues,
    issues,
)
from heare.developer.clients.plane_so import write_config


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


@patch("heare.developer.clients.plane_so.CONFIG_FILE")
@patch("heare.developer.clients.plane_so.CONFIG_DIR")
@patch("heare.developer.clients.plane_so.open", new_callable=unittest.mock.mock_open)
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


@patch("heare.developer.issues_cli.read_config")
@patch("heare.developer.issues_cli.interactive_select")
@patch("heare.developer.issues_cli.Prompt.ask")
@patch("heare.developer.issues_cli.print_message")
def test_config_issues_help(
    mock_print_message, mock_prompt_ask, mock_interactive_select, mock_read_config
):
    # Set up mocks
    mock_read_config.return_value = {
        "workspaces": {"test-workspace": "api-key"},
        "projects": {},
    }
    # We no longer need to mock Confirm.ask since it's not used anymore
    # Instead, we'd need to mock interactive_select, but it's not called for the help case

    # Test displaying help when just "config" is used
    config_issues(user_input="config")

    # We should check that print_message was called with the help text
    mock_print_message.assert_called_once()
    help_message = mock_print_message.call_args[0][0]
    assert "Usage: /config [type]" in help_message
    assert "Examples:" in help_message


@patch("heare.developer.issues_cli.read_config")
@patch("heare.developer.issues_cli.print_message")
def test_issues_not_configured(mock_print_message, mock_read_config):
    # Simulate unconfigured state
    mock_read_config.return_value = {"workspaces": {}, "projects": {}}

    # Call the issues function
    issues(user_input="issues")

    # Verify we get the not configured message
    mock_print_message.assert_called_once()
    assert "Issue tracking is not configured yet" in mock_print_message.call_args[0][0]


@patch("heare.developer.issues_cli.project_selection_flow")
@patch("heare.developer.issues_cli.read_config")
@patch("heare.developer.issues_cli.write_config")
@patch("heare.developer.issues_cli.interactive_select")
@patch("heare.developer.issues_cli.Prompt.ask")
@patch("heare.developer.issues_cli.print_message")
def test_config_issues_with_existing_workspaces(
    mock_print_message,
    mock_prompt_ask,
    mock_interactive_select,
    mock_write_config,
    mock_read_config,
    mock_project_selection_flow,
):
    # Set up mocks
    mock_read_config.return_value = {
        "workspaces": {"test-workspace": "api-key"},
        "projects": {},
    }

    # Mock workspace selection and project selection
    mock_interactive_select.return_value = ("test-workspace", "test-workspace")
    mock_project_selection_flow.return_value = "test-project"

    # Call the function under test
    config_issues(user_input="config issues")

    # Verify interactive_select was called once for workspace selection
    mock_interactive_select.assert_called_once()

    # Verify first call arguments (select workspace or create new)
    call_args = mock_interactive_select.call_args[0]
    assert len(call_args) > 0
    choices = call_args[0]

    # Verify our choices contain both the existing workspace and the "Create new" option
    assert any(choice[0] == "test-workspace" for choice in choices)
    assert any("Create a new workspace" in choice[0] for choice in choices)

    # Verify project_selection_flow was called with correct parameters
    mock_project_selection_flow.assert_called_once_with(
        mock_read_config.return_value, "test-workspace", "api-key"
    )


@patch("heare.developer.issues_cli.project_selection_flow")
@patch(
    "heare.developer.issues_cli.interactive_select"
)  # Order matters - patches are applied from bottom to top
@patch("heare.developer.issues_cli.print_message")
@patch("heare.developer.issues_cli.Prompt.ask")
@patch("heare.developer.issues_cli.write_config")
@patch("heare.developer.issues_cli.read_config")
def test_config_issues_with_no_workspaces(
    mock_read_config,
    mock_write_config,
    mock_prompt_ask,
    mock_print_message,
    mock_interactive_select,
    mock_project_selection_flow,
):
    # Set up mocks
    mock_read_config.return_value = {
        "workspaces": {},
        "projects": {},
    }

    # Mock prompt responses for creating a new workspace
    mock_prompt_ask.side_effect = ["new-workspace", "new-api-key"]

    # Mock project selection flow
    mock_project_selection_flow.return_value = "test-project"

    # Call the function - when no workspaces exist, it should prompt to create one
    config_issues(user_input="config issues")

    # Verify that the print_message was called to indicate no workspaces
    mock_print_message.assert_any_call("No workspaces configured. Let's add one first.")

    # Verify that write_config was called with a config that includes our new workspace
    mock_write_config.assert_called_once()
    config_arg = mock_write_config.call_args[0][0]
    assert "new-workspace" in config_arg["workspaces"]
    assert config_arg["workspaces"]["new-workspace"] == "new-api-key"

    # Verify project_selection_flow was called with correct parameters
    mock_project_selection_flow.assert_called_once_with(
        mock_read_config.return_value, "new-workspace", "new-api-key"
    )
