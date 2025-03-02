"""
Tests for the Plane.so API integration tools.
"""

import unittest
from unittest.mock import patch, MagicMock
import json

from heare.developer.context import AgentContext
from heare.developer.user_interface import UserInterface
import sys
import os

# Add the project root to the path to ensure imports work correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from heare.developer.tools.issues import (
    list_plane_workspaces,
    list_plane_projects,
    list_plane_issues,
    get_plane_issue_details,
    create_plane_issue,
    update_plane_issue,
)


class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data) if json_data else ""

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests import HTTPError

            raise HTTPError(f"HTTP Error: {self.status_code}")


class TestPlaneTools(unittest.TestCase):
    def setUp(self):
        # Mock the UI
        self.ui = MagicMock(spec=UserInterface)

        # Mock the context
        self.context = MagicMock(spec=AgentContext)
        self.context.user_interface = self.ui

    @patch("heare.developer.tools.issues._make_plane_request")
    def test_list_plane_workspaces(self, mock_make_request):
        # Setup
        mock_response = [
            {
                "id": "workspace-1",
                "name": "Test Workspace",
                "slug": "test-workspace",
                "created_at": "2023-01-01T00:00:00Z",
            }
        ]
        mock_make_request.return_value = mock_response

        # Test
        result = list_plane_workspaces(self.context)

        # Verify
        self.assertIn("Test Workspace", result)
        self.assertIn("test-workspace", result)
        mock_make_request.assert_called_with("GET", "/api/v1/workspaces/")

    @patch("heare.developer.tools.issues._make_plane_request")
    def test_list_plane_projects(self, mock_make_request):
        # Setup
        mock_response = [
            {
                "id": "project-1",
                "name": "Test Project",
                "identifier": "PRJ",
                "description": "A test project",
            }
        ]
        mock_make_request.return_value = mock_response

        # Test
        result = list_plane_projects(self.context, "test-workspace")

        # Verify
        self.assertIn("Test Project", result)
        self.assertIn("PRJ", result)
        mock_make_request.assert_called_with(
            "GET", "/api/v1/workspaces/test-workspace/projects/"
        )

    @patch("heare.developer.tools.issues._make_plane_request")
    def test_list_plane_issues(self, mock_make_request):
        # Setup
        mock_response = [
            {
                "id": "issue-1",
                "name": "Test Issue",
                "state_detail": {"name": "Todo"},
                "priority": "high",
                "assignee_detail": {"display_name": "John Doe"},
                "created_at": "2023-01-01T00:00:00Z",
            }
        ]
        mock_make_request.return_value = mock_response

        # Test
        result = list_plane_issues(self.context, "test-workspace", "project-1")

        # Verify
        self.assertIn("Test Issue", result)
        self.assertIn("Todo", result)
        self.assertIn("high", result)
        mock_make_request.assert_called_with(
            "GET",
            "/api/v1/workspaces/test-workspace/projects/project-1/issues/",
            params={},
        )

    @patch("heare.developer.tools.issues._make_plane_request")
    def test_get_plane_issue_details(self, mock_make_request):
        # Setup for main issue request
        mock_issue_response = {
            "id": "issue-1",
            "name": "Test Issue",
            "description": "Test description",
            "state_detail": {"name": "Todo"},
            "priority": "high",
            "assignee_detail": {"display_name": "John Doe"},
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-02T00:00:00Z",
            "link_count": 0,
            "sub_issues_count": 0,
        }

        # Configure mock to return different responses for different endpoints
        def side_effect(method, endpoint, **kwargs):
            if endpoint.endswith("issues/issue-1/"):
                return mock_issue_response
            return None

        mock_make_request.side_effect = side_effect

        # Test
        result = get_plane_issue_details(
            self.context, "test-workspace", "project-1", "issue-1"
        )

        # Verify
        self.assertIn("Test Issue", result)
        self.assertIn("Test description", result)
        self.assertIn("Todo", result)
        self.assertIn("high", result)
        mock_make_request.assert_called_with(
            "GET",
            "/api/v1/workspaces/test-workspace/projects/project-1/issues/issue-1/",
        )

    @patch("heare.developer.tools.issues._make_plane_request")
    def test_create_plane_issue(self, mock_make_request):
        # Setup
        mock_response = {"id": "new-issue-1", "name": "New Test Issue"}
        mock_make_request.return_value = mock_response

        # Test
        result = create_plane_issue(
            self.context,
            "test-workspace",
            "project-1",
            "New Test Issue",
            description="Test description",
            priority="high",
        )

        # Verify
        self.assertIn("Issue created successfully", result)
        self.assertIn("New Test Issue", result)

        # Check that the API was called with the correct data
        mock_make_request.assert_called_with(
            "POST",
            "/api/v1/workspaces/test-workspace/projects/project-1/issues/",
            data={
                "name": "New Test Issue",
                "description": "Test description",
                "priority": "high",
            },
        )

    @patch("heare.developer.tools.issues._make_plane_request")
    def test_update_plane_issue(self, mock_make_request):
        # Setup
        mock_response = {"id": "issue-1", "name": "Updated Test Issue"}
        mock_make_request.return_value = mock_response

        # Test
        result = update_plane_issue(
            self.context,
            "test-workspace",
            "project-1",
            "issue-1",
            name="Updated Test Issue",
            priority="medium",
        )

        # Verify
        self.assertIn("Issue updated successfully", result)
        self.assertIn("Updated Test Issue", result)

        # Check that the API was called with the correct data
        mock_make_request.assert_called_with(
            "PATCH",
            "/api/v1/workspaces/test-workspace/projects/project-1/issues/issue-1/",
            data={"name": "Updated Test Issue", "priority": "medium"},
        )


if __name__ == "__main__":
    unittest.main()
