import unittest
from unittest.mock import patch
import os
import tempfile
import json
import time

from heare.developer.clients.plane_cache import (
    get_cache_path,
    cache_is_valid,
    read_cache,
    write_cache,
    fetch_and_cache_states,
    get_state_id_by_name,
    get_state_name_by_id,
    refresh_all_caches,
    clear_cache,
    CACHE_TTL,
)


class TestPlaneCache(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_slug = "test-workspace"
        self.project_id = "test-project"
        self.api_key = "test-api-key"

        # Mock cache directory
        self.original_cache_dir = os.environ.get("HDEV_CACHE_DIR")
        os.environ["HDEV_CACHE_DIR"] = self.temp_dir

    def tearDown(self):
        # Clean up the temporary directory
        import shutil

        shutil.rmtree(self.temp_dir)

        # Restore original cache directory
        if self.original_cache_dir:
            os.environ["HDEV_CACHE_DIR"] = self.original_cache_dir
        else:
            os.environ.pop("HDEV_CACHE_DIR", None)

    def test_get_cache_path(self):
        """Test that cache path is correctly generated"""
        with patch("heare.developer.clients.plane_cache.CACHE_DIR", self.temp_dir):
            path = get_cache_path(self.workspace_slug, self.project_id, "states")
            expected_path = os.path.join(
                self.temp_dir, f"{self.workspace_slug}_{self.project_id}_states.json"
            )
            self.assertEqual(path, expected_path)

    def test_cache_is_valid(self):
        """Test cache validity check"""
        with patch("heare.developer.clients.plane_cache.CACHE_DIR", self.temp_dir):
            # Create a test cache file
            cache_path = os.path.join(self.temp_dir, "test_cache.json")
            with open(cache_path, "w") as f:
                json.dump({"test": "data"}, f)

            # Should be valid as it was just created
            self.assertTrue(cache_is_valid(cache_path))

            # Modify file time to make it older than TTL
            old_time = time.time() - (CACHE_TTL + 60)  # 60 seconds older than TTL
            os.utime(cache_path, (old_time, old_time))

            # Should now be invalid
            self.assertFalse(cache_is_valid(cache_path))

            # Non-existent file should be invalid
            self.assertFalse(
                cache_is_valid(os.path.join(self.temp_dir, "nonexistent.json"))
            )

    def test_write_and_read_cache(self):
        """Test writing to and reading from cache"""
        with patch("heare.developer.clients.plane_cache.CACHE_DIR", self.temp_dir):
            test_data = {"id1": "value1", "id2": "value2"}

            write_cache(self.workspace_slug, self.project_id, "test_entity", test_data)

            # Read back the data
            cached_data = read_cache(
                self.workspace_slug, self.project_id, "test_entity"
            )

            self.assertEqual(cached_data, test_data)

            # Test reading non-existent cache
            self.assertIsNone(
                read_cache(self.workspace_slug, self.project_id, "nonexistent")
            )

    @patch("heare.developer.clients.plane_cache._make_plane_request")
    def test_fetch_and_cache_states(self, mock_request):
        """Test fetching and caching states"""
        mock_response = {
            "results": [
                {
                    "id": "state1",
                    "name": "To Do",
                    "group": "backlog",
                    "color": "#ff0000",
                    "slug": "to-do",
                },
                {
                    "id": "state2",
                    "name": "In Progress",
                    "group": "started",
                    "color": "#00ff00",
                    "slug": "in-progress",
                },
                {
                    "id": "state3",
                    "name": "Done",
                    "group": "completed",
                    "color": "#0000ff",
                    "slug": "done",
                },
            ]
        }
        mock_request.return_value = mock_response

        with patch("heare.developer.clients.plane_cache.CACHE_DIR", self.temp_dir):
            # Fetch and cache states
            states = fetch_and_cache_states(
                self.workspace_slug, self.project_id, self.api_key
            )

            # Verify the request was made correctly
            mock_request.assert_called_once()

            # Verify the cached data
            self.assertEqual(len(states["raw_results"]), 3)
            self.assertEqual(
                len(states["name_to_id"]), 6
            )  # Both lowercase and original case
            self.assertEqual(len(states["id_to_details"]), 3)

            # Verify mappings
            self.assertEqual(states["name_to_id"]["to do"], "state1")
            self.assertEqual(states["name_to_id"]["To Do"], "state1")
            self.assertEqual(states["id_to_details"]["state1"]["name"], "To Do")

            # Test using the cached data without making a new request
            mock_request.reset_mock()

            # This should use cache
            states = fetch_and_cache_states(
                self.workspace_slug, self.project_id, self.api_key
            )

            # Verify no new request was made
            mock_request.assert_not_called()

            # Force refresh should make a new request
            states = fetch_and_cache_states(
                self.workspace_slug, self.project_id, self.api_key, force_refresh=True
            )

            # Verify a new request was made
            mock_request.assert_called_once()

    @patch("heare.developer.clients.plane_cache.fetch_and_cache_states")
    def test_get_state_id_by_name(self, mock_fetch):
        """Test getting state ID by name"""
        mock_states = {
            "name_to_id": {
                "to do": "state1",
                "To Do": "state1",
                "in progress": "state2",
                "In Progress": "state2",
                "done": "state3",
                "Done": "state3",
                "backlog": "state4",
                "Backlog": "state4",
                "todo": "state5",
                "Todo": "state5",
                "cancelled": "state6",
                "Cancelled": "state6",
            }
        }
        mock_fetch.return_value = mock_states

        # Exact match (case-insensitive)
        state_id = get_state_id_by_name(
            self.workspace_slug, self.project_id, "To Do", self.api_key
        )
        self.assertEqual(state_id, "state1")

        # Partial match
        state_id = get_state_id_by_name(
            self.workspace_slug, self.project_id, "progress", self.api_key
        )
        self.assertEqual(state_id, "state2")

        # Test all required states with different case variations
        test_cases = [
            ("Done", "state3"),
            ("done", "state3"),
            ("DONE", "state3"),
            ("In Progress", "state2"),
            ("in progress", "state2"),
            ("IN PROGRESS", "state2"),
            ("Backlog", "state4"),
            ("backlog", "state4"),
            ("BACKLOG", "state4"),
            ("Todo", "state5"),
            ("todo", "state5"),
            ("TODO", "state5"),
            ("Cancelled", "state6"),
            ("cancelled", "state6"),
            ("CANCELLED", "state6"),
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

        # Non-existent state
        state_id = get_state_id_by_name(
            self.workspace_slug, self.project_id, "nonexistent", self.api_key
        )
        self.assertIsNone(state_id)

    @patch("heare.developer.clients.plane_cache.fetch_and_cache_states")
    def test_get_state_name_by_id(self, mock_fetch):
        """Test getting state name by ID"""
        mock_states = {
            "id_to_details": {
                "state1": {
                    "name": "To Do",
                    "group": "backlog",
                    "color": "#ff0000",
                    "slug": "to-do",
                },
                "state2": {
                    "name": "In Progress",
                    "group": "started",
                    "color": "#00ff00",
                    "slug": "in-progress",
                },
                "state3": {
                    "name": "Done",
                    "group": "completed",
                    "color": "#0000ff",
                    "slug": "done",
                },
                "state4": {
                    "name": "Backlog",
                    "group": "backlog",
                    "color": "#ffff00",
                    "slug": "backlog",
                },
                "state5": {
                    "name": "Todo",
                    "group": "backlog",
                    "color": "#ff00ff",
                    "slug": "todo",
                },
                "state6": {
                    "name": "Cancelled",
                    "group": "cancelled",
                    "color": "#888888",
                    "slug": "cancelled",
                },
            }
        }
        mock_fetch.return_value = mock_states

        # Valid state ID
        state_name = get_state_name_by_id(
            self.workspace_slug, self.project_id, "state2", self.api_key
        )
        self.assertEqual(state_name, "In Progress")

        # Test all required states
        test_cases = [
            ("state1", "To Do"),
            ("state2", "In Progress"),
            ("state3", "Done"),
            ("state4", "Backlog"),
            ("state5", "Todo"),
            ("state6", "Cancelled"),
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

        # Non-existent state ID
        state_name = get_state_name_by_id(
            self.workspace_slug, self.project_id, "nonexistent", self.api_key
        )
        self.assertIsNone(state_name)

    @patch("heare.developer.clients.plane_cache.fetch_and_cache_states")
    def test_bidirectional_lookups(self, mock_fetch):
        """Test that state lookups work bidirectionally (name->ID->name and ID->name->ID)"""
        # Set up the mock state data
        mock_states = {
            "name_to_id": {
                "done": "state3",
                "Done": "state3",
                "in progress": "state2",
                "In Progress": "state2",
                "backlog": "state4",
                "Backlog": "state4",
                "todo": "state5",
                "Todo": "state5",
                "cancelled": "state6",
                "Cancelled": "state6",
            },
            "id_to_details": {
                "state2": {
                    "name": "In Progress",
                    "group": "started",
                    "color": "#00ff00",
                    "slug": "in-progress",
                },
                "state3": {
                    "name": "Done",
                    "group": "completed",
                    "color": "#0000ff",
                    "slug": "done",
                },
                "state4": {
                    "name": "Backlog",
                    "group": "backlog",
                    "color": "#ffff00",
                    "slug": "backlog",
                },
                "state5": {
                    "name": "Todo",
                    "group": "backlog",
                    "color": "#ff00ff",
                    "slug": "todo",
                },
                "state6": {
                    "name": "Cancelled",
                    "group": "cancelled",
                    "color": "#888888",
                    "slug": "cancelled",
                },
            },
        }
        mock_fetch.return_value = mock_states

        # Test name -> ID -> name
        test_cases = ["Done", "In Progress", "Backlog", "Todo", "Cancelled"]

        for original_name in test_cases:
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

        # Test ID -> name -> ID (using a variant of the name that's different case)
        test_cases = [
            ("state3", "done"),  # Using lowercase for the reverse lookup
            ("state2", "in progress"),
            ("state4", "backlog"),
            ("state5", "todo"),
            ("state6", "cancelled"),
        ]

        for original_id, lookup_name_variant in test_cases:
            with self.subTest(direction="ID->name->ID", original=original_id):
                # Convert ID to name
                state_name = get_state_name_by_id(
                    self.workspace_slug, self.project_id, original_id, self.api_key
                )
                self.assertIsNotNone(
                    state_name, f"Could not find name for ID '{original_id}'"
                )

                # Convert a variant of the name back to ID
                state_id = get_state_id_by_name(
                    self.workspace_slug,
                    self.project_id,
                    lookup_name_variant,
                    self.api_key,
                )
                self.assertEqual(
                    state_id,
                    original_id,
                    f"ID did not match after bidirectional lookup. Expected '{original_id}', got '{state_id}'",
                )

    @patch("heare.developer.clients.plane_cache.fetch_and_cache_states")
    @patch("heare.developer.clients.plane_cache.fetch_and_cache_priorities")
    def test_refresh_all_caches(self, mock_fetch_priorities, mock_fetch_states):
        """Test refreshing all caches"""
        mock_fetch_states.return_value = {"mock": "states"}
        mock_fetch_priorities.return_value = {"mock": "priorities"}

        results = refresh_all_caches(self.workspace_slug, self.project_id, self.api_key)

        self.assertTrue(results["states"])
        self.assertTrue(results["priorities"])

        # Test handling exceptions
        mock_fetch_states.side_effect = Exception("Test error")

        results = refresh_all_caches(self.workspace_slug, self.project_id, self.api_key)

        self.assertFalse(results["states"])
        self.assertTrue("states_error" in results)
        self.assertTrue(results["priorities"])

    def test_clear_cache(self):
        """Test clearing cache"""
        with patch("heare.developer.clients.plane_cache.CACHE_DIR", self.temp_dir):
            # Create test cache files
            write_cache("ws1", "proj1", "states", {"data": "test1"})
            write_cache("ws1", "proj1", "priorities", {"data": "test2"})
            write_cache("ws2", "proj2", "states", {"data": "test3"})

            # Clear specific file
            clear_cache("ws1", "proj1", "states")

            # Verify file was deleted
            self.assertIsNone(read_cache("ws1", "proj1", "states"))
            self.assertIsNotNone(read_cache("ws1", "proj1", "priorities"))
            self.assertIsNotNone(read_cache("ws2", "proj2", "states"))

            # Clear by pattern (workspace)
            clear_cache("ws1")

            # Verify files were deleted
            self.assertIsNone(read_cache("ws1", "proj1", "priorities"))
            self.assertIsNotNone(read_cache("ws2", "proj2", "states"))

            # Clear all
            clear_cache()

            # Verify all files were deleted
            self.assertIsNone(read_cache("ws2", "proj2", "states"))


if __name__ == "__main__":
    unittest.main()
