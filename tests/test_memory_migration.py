"""Tests for memory migration functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from heare.developer.tools.memory_migrate import (
    MemoryMigrator,
    migrate_memory,
    _parse_backend_config,
)
from heare.developer.memory_backends.filesystem import FilesystemMemoryBackend
from heare.developer.memory_backends.http import HTTPMemoryBackend


@pytest.fixture
def source_backend(tmp_path):
    """Create a filesystem backend with test data."""
    backend = FilesystemMemoryBackend(tmp_path / "source")
    return backend


@pytest.fixture
def target_backend(tmp_path):
    """Create an empty filesystem backend for target."""
    backend = FilesystemMemoryBackend(tmp_path / "target")
    return backend


@pytest.fixture
async def populated_source_backend(source_backend):
    """Create source backend with test data."""
    # Add some test entries (note: global already exists in filesystem backend)
    await source_backend.write_entry(
        "global", "Updated global memory content", {"type": "global"}
    )
    await source_backend.write_entry(
        "projects/project1", "Project 1 content", {"type": "project"}
    )
    await source_backend.write_entry(
        "projects/frontend/react", "React notes", {"type": "notes"}
    )
    await source_backend.write_entry(
        "personal/todos", "My todo list", {"type": "personal"}
    )

    return source_backend


@pytest.mark.asyncio
async def test_migrator_discover_entries(populated_source_backend, target_backend):
    """Test discovering entries in source backend."""
    migrator = MemoryMigrator(populated_source_backend, target_backend)
    entries = await migrator._discover_entries()

    # Should find all 4 entries
    assert len(entries) == 4
    assert "global" in entries
    assert "projects/project1" in entries
    assert "projects/frontend/react" in entries
    assert "personal/todos" in entries


@pytest.mark.asyncio
async def test_migrator_migrate_entry_success(populated_source_backend, target_backend):
    """Test successful migration of a single entry."""
    migrator = MemoryMigrator(populated_source_backend, target_backend)

    # Test with a non-global entry that doesn't exist by default
    result = await migrator._migrate_entry(
        "projects/project1", overwrite=False, dry_run=False
    )

    assert result["success"] is True
    assert result["action"] == "copied"

    # Verify entry was copied
    target_result = await target_backend.read_entry("projects/project1")
    assert target_result["success"] is True
    assert target_result["content"] == "Project 1 content"
    assert target_result["metadata"]["type"] == "project"


@pytest.mark.asyncio
async def test_migrator_skip_existing_entry(populated_source_backend, target_backend):
    """Test skipping existing entries when overwrite is False."""
    migrator = MemoryMigrator(populated_source_backend, target_backend)

    # First create an entry in target
    await target_backend.write_entry("global", "Existing content", {"existing": True})

    result = await migrator._migrate_entry("global", overwrite=False, dry_run=False)

    assert result["success"] is True
    assert result["action"] == "skipped"

    # Verify original content is preserved
    target_result = await target_backend.read_entry("global")
    assert target_result["content"] == "Existing content"
    assert target_result["metadata"]["existing"] is True


@pytest.mark.asyncio
async def test_migrator_overwrite_existing_entry(
    populated_source_backend, target_backend
):
    """Test overwriting existing entries when overwrite is True."""
    migrator = MemoryMigrator(populated_source_backend, target_backend)

    # First create an entry in target
    await target_backend.write_entry("global", "Existing content", {"existing": True})

    result = await migrator._migrate_entry("global", overwrite=True, dry_run=False)

    assert result["success"] is True
    assert result["action"] == "copied"

    # Verify content was overwritten
    target_result = await target_backend.read_entry("global")
    assert target_result["content"] == "Updated global memory content"
    assert target_result["metadata"]["type"] == "global"


@pytest.mark.asyncio
async def test_migrator_dry_run(populated_source_backend, target_backend):
    """Test dry run mode doesn't actually copy entries."""
    migrator = MemoryMigrator(populated_source_backend, target_backend)

    result = await migrator._migrate_entry(
        "projects/project1", overwrite=False, dry_run=True
    )

    assert result["success"] is True
    assert result["action"] == "copied"  # For stats counting

    # Verify entry was NOT copied (should not exist)
    target_result = await target_backend.read_entry("projects/project1")
    assert target_result["success"] is False


@pytest.mark.asyncio
async def test_migrate_all_success(populated_source_backend, target_backend):
    """Test migrating all entries successfully."""
    migrator = MemoryMigrator(populated_source_backend, target_backend)

    result = await migrator.migrate_all(overwrite=False, dry_run=False)

    assert result["success"] is True
    assert result["stats"]["total_entries"] == 4
    # Global entry will be skipped because it already exists in target
    assert result["stats"]["copied_entries"] == 3  # 3 new entries
    assert result["stats"]["skipped_entries"] == 1  # global entry
    assert result["stats"]["failed_entries"] == 0

    # Verify the new entries were copied
    for entry_path in [
        "projects/project1",
        "projects/frontend/react",
        "personal/todos",
    ]:
        target_result = await target_backend.read_entry(entry_path)
        assert target_result["success"] is True


@pytest.mark.asyncio
async def test_migrate_all_dry_run(populated_source_backend, target_backend):
    """Test dry run migration."""
    migrator = MemoryMigrator(populated_source_backend, target_backend)

    result = await migrator.migrate_all(overwrite=False, dry_run=True)

    assert result["success"] is True
    assert result["stats"]["total_entries"] == 4
    # In dry run, global is skipped (exists), others are counted as "would copy"
    assert result["stats"]["copied_entries"] == 3  # 3 would be copied, 1 skipped
    assert "simulation" in result["message"]

    # Verify no new entries were actually copied (global exists by default)
    target_result = await target_backend.read_entry("projects/project1")
    assert target_result["success"] is False  # This should not exist


@pytest.mark.asyncio
async def test_migrate_all_with_existing_entries(
    populated_source_backend, target_backend
):
    """Test migration with some existing entries."""
    # Add another existing entry to target (global already exists by default)
    await target_backend.write_entry(
        "projects/project1", "Existing project", {"existing": True}
    )

    migrator = MemoryMigrator(populated_source_backend, target_backend)
    result = await migrator.migrate_all(overwrite=False, dry_run=False)

    assert result["success"] is True
    assert result["stats"]["total_entries"] == 4
    assert result["stats"]["copied_entries"] == 2  # 2 new entries
    assert (
        result["stats"]["skipped_entries"] == 2
    )  # 2 existing entries (global + project1)
    assert result["stats"]["failed_entries"] == 0


@pytest.mark.asyncio
async def test_parse_backend_config_filesystem():
    """Test parsing filesystem backend config."""
    backend = await _parse_backend_config("filesystem")
    assert isinstance(backend, FilesystemMemoryBackend)


@pytest.mark.asyncio
async def test_parse_backend_config_http():
    """Test parsing HTTP backend config."""
    with patch("heare.developer.tools.memory_migrate.get_config") as mock_config:
        mock_config.return_value.memory.http_api_key = "test-key"

        backend = await _parse_backend_config("http:https://memory.example.com")
        assert isinstance(backend, HTTPMemoryBackend)
        assert backend.base_url == "https://memory.example.com"
        assert backend.api_key == "test-key"


@pytest.mark.asyncio
async def test_parse_backend_config_invalid():
    """Test parsing invalid backend config."""
    with pytest.raises(ValueError, match="Unknown backend config"):
        await _parse_backend_config("invalid-config")


@pytest.mark.asyncio
async def test_migrate_memory_tool_success():
    """Test the migrate_memory tool function."""
    # Mock context
    mock_context = MagicMock()
    mock_source_backend = AsyncMock()
    mock_target_backend = AsyncMock()
    mock_context.memory_manager.backend = mock_source_backend

    # Mock migrator
    with patch(
        "heare.developer.tools.memory_migrate.MemoryMigrator"
    ) as mock_migrator_class:
        mock_migrator = AsyncMock()
        mock_migrator_class.return_value = mock_migrator
        mock_migrator.migrate_all.return_value = {
            "success": True,
            "message": "Migration completed successfully",
            "stats": {
                "total_entries": 5,
                "copied_entries": 5,
                "skipped_entries": 0,
                "failed_entries": 0,
                "errors": [],
            },
        }

        with patch(
            "heare.developer.tools.memory_migrate._parse_backend_config"
        ) as mock_parse:
            mock_parse.return_value = mock_target_backend

            result = await migrate_memory(
                mock_context,
                target_config="http:https://memory.example.com",
                overwrite=False,
                dry_run=False,
            )

            assert "Migration completed successfully" in result
            assert "Total entries found: 5" in result
            assert "Entries copied: 5" in result


@pytest.mark.asyncio
async def test_migrate_memory_tool_missing_target():
    """Test migrate_memory tool with missing target config."""
    mock_context = MagicMock()

    result = await migrate_memory(mock_context)

    assert "Error: target_config is required" in result


@pytest.mark.asyncio
async def test_migrate_memory_tool_with_errors():
    """Test migrate_memory tool with some errors."""
    mock_context = MagicMock()
    mock_context.memory_manager.backend = AsyncMock()

    with patch(
        "heare.developer.tools.memory_migrate.MemoryMigrator"
    ) as mock_migrator_class:
        mock_migrator = AsyncMock()
        mock_migrator_class.return_value = mock_migrator
        mock_migrator.migrate_all.return_value = {
            "success": False,
            "message": "Migration completed with errors",
            "stats": {
                "total_entries": 5,
                "copied_entries": 3,
                "skipped_entries": 0,
                "failed_entries": 2,
                "errors": [
                    {"path": "error1", "error": "Network timeout"},
                    {"path": "error2", "error": "Permission denied"},
                ],
            },
        }

        with patch("heare.developer.tools.memory_migrate._parse_backend_config"):
            result = await migrate_memory(
                mock_context, target_config="http:https://memory.example.com"
            )

            assert "Migration completed with errors" in result
            assert "Entries failed: 2" in result
            assert "error1: Network timeout" in result
            assert "error2: Permission denied" in result


def test_empty_source_backend():
    """Test migration with empty source backend."""

    async def run_test():
        source_backend = AsyncMock()
        source_backend.get_tree.return_value = {"success": True, "items": {}}

        target_backend = AsyncMock()

        migrator = MemoryMigrator(source_backend, target_backend)
        result = await migrator.migrate_all()

        assert result["success"] is True
        assert result["message"] == "No entries found to migrate"
        assert result["stats"]["total_entries"] == 0

    import asyncio

    asyncio.run(run_test())
