"""Test the memory migration script."""

import json
import shutil
import tempfile
import sys
from pathlib import Path
import pytest
from unittest.mock import patch

# Add the scripts directory to the path so we can import the migrate_memory module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from migrate_memory import migrate_file


@pytest.fixture
def temp_dirs():
    """Create temporary directories for migration testing."""
    with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
        source_path = Path(source_dir)
        target_path = Path(target_dir)
        yield source_path, target_path


def test_migrate_file(temp_dirs):
    """Test that a single file is migrated correctly."""
    source_dir, target_dir = temp_dirs

    # Create a test memory entry in the old format
    test_data = {
        "content": "This is test content with *markdown* formatting",
        "metadata": {
            "created": "1713456789.123456",
            "updated": "1713456789.123456",
            "version": 3,
        },
    }

    # Create the directory structure
    memory_path = source_dir / "test" / "example.json"
    memory_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the test memory entry
    with open(memory_path, "w") as f:
        json.dump(test_data, f, indent=2)

    # Set up the home path mock
    with patch("pathlib.Path.home") as mock_home:
        mock_home.return_value = source_dir.parent
        # Create the .hdev/memory-backup directory structure for the relative path computation
        backup_dir = source_dir.parent / ".hdev" / "memory-backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        # Copy the test data to the backup directory
        test_backup_path = backup_dir / "test" / "example.json"
        test_backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(memory_path, test_backup_path)

        # Migrate the file
        migrate_file(test_backup_path, target_dir)

    # Check that the migrated files exist
    assert (target_dir / "test" / "example.md").exists()
    assert (target_dir / "test" / "example.metadata.json").exists()

    # Check the content of the migrated files
    with open(target_dir / "test" / "example.md", "r") as f:
        content = f.read()
    assert content == "This is test content with *markdown* formatting"

    with open(target_dir / "test" / "example.metadata.json", "r") as f:
        metadata = json.load(f)
    assert metadata["created"] == "1713456789.123456"
    assert metadata["updated"] == "1713456789.123456"
    assert metadata["version"] == 3
