"""
Unit tests for Plane.so state cache functionality.

These tests verify that cached states like "done", "in progress", "backlog", "todo", and "cancelled"
work properly in both directions (name -> ID and ID -> name) with case insensitivity.
"""

import os
import json
import unittest
from unittest.mock import patch

from heare.developer.clients.plane_cache import (
    get_state_id_by_name,
    get_state_name_by_id,
    fetch_and_cache_states,
    get_cache_path,
)


class TestPlaneStateCache(unittest.TestCase):
    """Test case for Plane.so state cache functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock cache directory
        self.test_cache_dir = "/tmp/test_hdev_plane_cache"
        os.makedirs(self.test_cache_dir, exist_ok=True)

        # Sample workspace and project for testing
        self.workspace_slug = "test-workspace"
        self.project_id = "test-project"
        self.api_key = "test-api-key"

        # Sample states that would typically come from the API
        self.mock_states_response = {
            "results": [
                {
                    "id": "done-id",
                    "name": "Done",
                    "group": "completed",
                    "color": "#00FF00",
                    "slug": "done",
                },
                {
                    "id": "in-progress-id",
                    "name": "In Progress",
                    "group": "started",
                    "color": "#0000FF",
                    "slug": "in-progress",
                },
                {
                    "id": "backlog-id",
                    "name": "Backlog",
                    "group": "unstarted",
                    "color": "#FF0000",
                    "slug": "backlog",
                },
                {
                    "id": "todo-id",
                    "name": "Todo",
                    "group": "unstarted",
                    "color": "#FFFF00",
                    "slug": "todo",
                },
                {
                    "id": "cancelled-id",
                    "name": "Cancelled",
                    "group": "cancelled",
                    "color": "#888888",
                    "slug": "cancelled",
                },
            ]
        }

        # Patch the cache directory path
        self.cache_dir_patch = patch(
            "heare.developer.clients.plane_cache.CACHE_DIR", self.test_cache_dir
        )
        self.cache_dir_patch.start()

    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the test cache directory and its contents
        for filename in os.listdir(self.test_cache_dir):
            os.remove(os.path.join(self.test_cache_dir, filename))
        os.rmdir(self.test_cache_dir)

        # Stop all patches
        self.cache_dir_patch.stop()

    @patch("heare.developer.clients.plane_cache._make_plane_request")
    def test_fetch_and_cache_states(self, mock_make_request):
        """Test that states are properly fetched and cached."""
        # Set up the mock API response
        mock_make_request.return_value = self.mock_states_response

        # Call the function that fetches and caches states
        result = fetch_and_cache_states(
            self.workspace_slug, self.project_id, self.api_key
        )

        # Verify that the API was called
        mock_make_request.assert_called_once()

        # Verify that result contains all expected mappings
        self.assertIn("raw_results", result)
        self.assertIn("name_to_id", result)
        self.assertIn("id_to_details", result)

        # Verify that cache file was created
        cache_path = get_cache_path(self.workspace_slug, self.project_id, "states")
        self.assertTrue(os.path.exists(cache_path))

        # Verify cache content
        with open(cache_path, "r") as f:
            cached_data = json.load(f)

        self.assertEqual(
            cached_data["raw_results"], self.mock_states_response["results"]
        )
        self.assertEqual(len(cached_data["name_to_id"]), 10)  # 5 original + 5 lowercase
        self.assertEqual(len(cached_data["id_to_details"]), 5)

    @patch("heare.developer.clients.plane_cache._make_plane_request")
    def test_get_state_id_by_name_case_insensitive(self, mock_make_request):
        """Test that state IDs can be retrieved by name with case insensitivity."""
        # Set up the mock API response
        mock_make_request.return_value = self.mock_states_response

        # Test with different case variations
        test_cases = [
            ("Done", "done-id"),
            ("done", "done-id"),
            ("DONE", "done-id"),
            ("In Progress", "in-progress-id"),
            ("in progress", "in-progress-id"),
            ("IN PROGRESS", "in-progress-id"),
            ("Backlog", "backlog-id"),
            ("backlog", "backlog-id"),
            ("BACKLOG", "backlog-id"),
            ("Todo", "todo-id"),
            ("todo", "todo-id"),
            ("TODO", "todo-id"),
            ("Cancelled", "cancelled-id"),
            ("cancelled", "cancelled-id"),
            ("CANCELLED", "cancelled-id"),
        ]

        for state_name, expected_id in test_cases:
            with self.subTest(state_name=state_name, expected_id=expected_id):
                state_id = get_state_id_by_name(
                    self.workspace_slug, self.project_id, state_name, self.api_key
                )
                self.assertEqual(
                    state_id,
                    expected_id,
                    f"Failed for state name '{state_name}', got ID '{state_id}' instead of '{expected_id}'",
                )

    @patch("heare.developer.clients.plane_cache._make_plane_request")
    def test_get_state_name_by_id(self, mock_make_request):
        """Test that state names can be retrieved by ID."""
        # Set up the mock API response
        mock_make_request.return_value = self.mock_states_response

        # Test with different IDs
        test_cases = [
            ("done-id", "Done"),
            ("in-progress-id", "In Progress"),
            ("backlog-id", "Backlog"),
            ("todo-id", "Todo"),
            ("cancelled-id", "Cancelled"),
        ]

        for state_id, expected_name in test_cases:
            with self.subTest(state_id=state_id, expected_name=expected_name):
                state_name = get_state_name_by_id(
                    self.workspace_slug, self.project_id, state_id, self.api_key
                )
                self.assertEqual(
                    state_name,
                    expected_name,
                    f"Failed for state ID '{state_id}', got name '{state_name}' instead of '{expected_name}'",
                )

    @patch("heare.developer.clients.plane_cache._make_plane_request")
    def test_bidirectional_lookups(self, mock_make_request):
        """Test that lookups work bidirectionally (name->ID->name and ID->name->ID)."""
        # Set up the mock API response
        mock_make_request.return_value = self.mock_states_response

        # Test name -> ID -> name
        for original_name in ["Done", "In Progress", "Backlog", "Todo", "Cancelled"]:
            with self.subTest(direction="name->ID->name", original=original_name):
                # Convert name to ID
                state_id = get_state_id_by_name(
                    self.workspace_slug, self.project_id, original_name, self.api_key
                )
                self.assertIsNotNone(
                    state_id, f"Could not find ID for state '{original_name}'"
                )

                # Convert ID back to name
                state_name = get_state_name_by_id(
                    self.workspace_slug, self.project_id, state_id, self.api_key
                )
                self.assertEqual(
                    state_name,
                    original_name,
                    f"Name did not match after bidirectional lookup. Expected '{original_name}', got '{state_name}'",
                )

        # Test ID -> name -> ID
        for original_id in [
            "done-id",
            "in-progress-id",
            "backlog-id",
            "todo-id",
            "cancelled-id",
        ]:
            with self.subTest(direction="ID->name->ID", original=original_id):
                # Convert ID to name
                state_name = get_state_name_by_id(
                    self.workspace_slug, self.project_id, original_id, self.api_key
                )
                self.assertIsNotNone(
                    state_name, f"Could not find name for ID '{original_id}'"
                )

                # Convert name back to ID
                state_id = get_state_id_by_name(
                    self.workspace_slug, self.project_id, state_name, self.api_key
                )
                self.assertEqual(
                    state_id,
                    original_id,
                    f"ID did not match after bidirectional lookup. Expected '{original_id}', got '{state_id}'",
                )


if __name__ == "__main__":
    unittest.main()
