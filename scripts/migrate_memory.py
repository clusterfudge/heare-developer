#!/usr/bin/env python3
"""
Migration script for the memory system.

This script migrates memory from the old format (single JSON files with content and metadata)
to the new format (separate .md files for content and .metadata.json files for metadata).
"""

import json
import shutil
from pathlib import Path
from datetime import datetime


def migrate_memory():
    """Migrate memory from old format to new format."""
    # Define paths
    base_dir = Path.home() / ".hdev" / "memory"
    backup_dir = Path.home() / ".hdev" / "memory-backup"

    # Create backup of current memory
    if backup_dir.exists():
        print(f"Backup directory {backup_dir} already exists. Using it for migration.")
    else:
        print(f"Creating backup of memory at {backup_dir}")
        shutil.copytree(base_dir, backup_dir)

    # Find all JSON files in the backup directory
    json_files = list(backup_dir.glob("**/*.json"))
    print(f"Found {len(json_files)} memory entries to migrate")

    # Process each file
    for file_path in json_files:
        migrate_file(file_path, base_dir)

    print("Migration completed successfully!")


def migrate_file(file_path, target_base_dir):
    """Migrate a single memory file to the new format.

    Args:
        file_path: Path to the JSON file to migrate
        target_base_dir: Base directory for the new memory format
    """
    try:
        # Read the existing file
        with open(file_path, "r") as f:
            data = json.load(f)

        # Extract content and metadata
        content = data.get("content", "")
        metadata = data.get("metadata", {})

        # Calculate relative path from backup dir to the file
        relative_path = file_path.relative_to(Path.home() / ".hdev" / "memory-backup")

        # Create the target directory
        target_dir = target_base_dir / relative_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        # Create the markdown file
        md_file = target_dir / f"{file_path.stem}.md"
        with open(md_file, "w") as f:
            f.write(content)

        # Create the metadata file
        metadata_file = target_dir / f"{file_path.stem}.metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        print(
            f"Migrated: {file_path.relative_to(Path.home() / '.hdev' / 'memory-backup')}"
        )

    except Exception as e:
        print(f"Error migrating {file_path}: {str(e)}")


if __name__ == "__main__":
    print(f"Starting memory migration at {datetime.now().isoformat()}")
    migrate_memory()
    print(f"Finished memory migration at {datetime.now().isoformat()}")
