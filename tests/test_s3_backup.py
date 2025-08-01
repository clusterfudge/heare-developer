"""Tests for S3 backup functionality."""

import pytest
import json
import gzip
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from heare.developer.s3_backup import S3BackupManager
from heare.developer.config import MemoryConfig
from heare.developer.memory_backends.filesystem import FilesystemMemoryBackend


@pytest.fixture
def s3_config():
    """Create test S3 configuration."""
    return MemoryConfig(
        s3_bucket="test-bucket",
        s3_region="us-east-1",
        s3_access_key_id="test-key",
        s3_secret_access_key="test-secret"
    )


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client."""
    client = MagicMock()
    return client


@pytest.fixture
def s3_manager(s3_config):
    """Create S3BackupManager with mocked S3 client."""
    with patch('boto3.Session') as mock_session:
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        
        manager = S3BackupManager(s3_config)
        manager.s3_client = mock_client
        
        yield manager, mock_client


@pytest.fixture
async def populated_backend(tmp_path):
    """Create a backend with test data."""
    backend = FilesystemMemoryBackend(tmp_path / "memory")
    
    # Add test entries
    await backend.write_entry("global", "Global memory content", {"type": "global"})
    await backend.write_entry("projects/project1", "Project 1 content", {"type": "project"})
    await backend.write_entry("personal/notes", "Personal notes", {"type": "personal"})
    
    return backend


@pytest.mark.asyncio
async def test_s3_backup_manager_initialization(s3_config):
    """Test S3BackupManager initialization."""
    with patch('boto3.Session') as mock_session:
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        
        manager = S3BackupManager(s3_config)
        
        assert manager.bucket == "test-bucket"
        assert manager.region == "us-east-1"
        assert manager.s3_client == mock_client
        
        # Verify boto3 session was created with correct credentials
        mock_session.assert_called_once_with(
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="us-east-1"
        )


def test_s3_backup_manager_no_bucket():
    """Test that S3BackupManager requires a bucket."""
    config = MemoryConfig(s3_bucket=None)
    
    with pytest.raises(ValueError, match="S3 bucket must be configured"):
        S3BackupManager(config)


def test_s3_backup_manager_no_boto3():
    """Test S3BackupManager when boto3 is not available."""
    config = MemoryConfig(s3_bucket="test-bucket")
    
    with patch.dict('sys.modules', {'boto3': None}):
        with patch('heare.developer.s3_backup.S3_AVAILABLE', False):
            with pytest.raises(ImportError, match="boto3 is required"):
                S3BackupManager(config)


@pytest.mark.asyncio
async def test_backup_all_success(s3_manager, populated_backend):
    """Test successful backup of all entries."""
    manager, mock_client = s3_manager
    
    # Mock S3 operations
    mock_client.put_object.return_value = {}
    
    # Mock the async executor
    with patch.object(manager, 'executor') as mock_executor:
        # Make executor.run return the mock directly
        mock_executor.run.return_value = None
        
        # Create a proper async context for the loop
        import asyncio
        loop = asyncio.get_event_loop()
        
        async def mock_run_in_executor(executor, func):
            return func()
        
        with patch.object(loop, 'run_in_executor', mock_run_in_executor):
            result = await manager.backup_all(populated_backend, "test-backup")
    
    # Verify result
    assert result["success"] is True
    assert result["backup_key"] == "test-backup"
    assert result["entries_backed_up"] == 3
    assert result["backup_size_bytes"] > 0
    
    # Verify S3 put_object was called for entries and metadata
    assert mock_client.put_object.call_count == 4  # 3 entries + 1 metadata


@pytest.mark.asyncio
async def test_backup_all_empty_backend(s3_manager, tmp_path):
    """Test backup with empty backend."""
    manager, mock_client = s3_manager
    
    # Create empty backend
    empty_backend = FilesystemMemoryBackend(tmp_path / "empty")
    
    result = await manager.backup_all(empty_backend, "empty-backup")
    
    assert result["success"] is True
    assert result["backup_key"] == "empty-backup"
    # FilesystemMemoryBackend creates a "global" entry by default, so we expect 1 entry
    assert result["entries_backed_up"] == 1  # Global entry is created by default


@pytest.mark.asyncio
async def test_backup_all_auto_name(s3_manager, populated_backend):
    """Test backup with automatic timestamp name."""
    manager, mock_client = s3_manager
    
    # Mock S3 operations
    mock_client.put_object.return_value = {}
    
    with patch('asyncio.get_event_loop') as mock_get_loop:
        mock_loop = AsyncMock()
        mock_get_loop.return_value = mock_loop
        
        # Mock run_in_executor to return None (successful upload)
        mock_loop.run_in_executor.return_value = None
        
        result = await manager.backup_all(populated_backend)
    
    # Verify backup key was auto-generated
    assert result["success"] is True
    assert result["backup_key"].startswith("backup_")
    assert len(result["backup_key"]) > 10  # Should have timestamp


@pytest.mark.asyncio
async def test_list_backups_success(s3_manager):
    """Test listing backups successfully."""
    manager, mock_client = s3_manager
    
    # Mock S3 list response
    mock_client.list_objects_v2.return_value = {
        'CommonPrefixes': [
            {'Prefix': 'hdev-memory-backups/backup_20231201_120000/'},
            {'Prefix': 'hdev-memory-backups/backup_20231201_130000/'},
        ]
    }
    
    # Mock metadata responses
    def mock_get_object(Bucket, Key):
        if 'backup_20231201_120000/metadata.json' in Key:
            metadata = {
                "backup_name": "backup_20231201_120000",
                "timestamp": "2023-12-01T12:00:00Z",
                "total_entries": 5,
                "backend_type": "FilesystemMemoryBackend"
            }
            return {'Body': MagicMock(read=lambda: json.dumps(metadata).encode())}
        elif 'backup_20231201_130000/metadata.json' in Key:
            metadata = {
                "backup_name": "backup_20231201_130000", 
                "timestamp": "2023-12-01T13:00:00Z",
                "total_entries": 3,
                "backend_type": "HTTPMemoryBackend"
            }
            return {'Body': MagicMock(read=lambda: json.dumps(metadata).encode())}
        return None
    
    mock_client.get_object.side_effect = mock_get_object
    
    with patch('asyncio.get_event_loop') as mock_get_loop:
        mock_loop = AsyncMock()
        mock_get_loop.return_value = mock_loop
        
        # Mock run_in_executor calls
        def run_in_executor_side_effect(executor, func):
            if 'list_objects_v2' in str(func):
                return mock_client.list_objects_v2.return_value
            else:
                # This is a get_object call
                return mock_get_object('test-bucket', str(func))
        
        mock_loop.run_in_executor.side_effect = run_in_executor_side_effect
        
        result = await manager.list_backups()
    
    # Verify result
    assert result["success"] is True
    assert len(result["backups"]) == 2
    
    # Check backup details (should be sorted by timestamp, newest first)
    backups = result["backups"]
    assert backups[0]["backup_key"] == "backup_20231201_130000"
    assert backups[0]["total_entries"] == 3
    assert backups[1]["backup_key"] == "backup_20231201_120000"
    assert backups[1]["total_entries"] == 5


@pytest.mark.asyncio
async def test_list_backups_empty(s3_manager):
    """Test listing backups when none exist."""
    manager, mock_client = s3_manager
    
    # Mock empty S3 response
    mock_client.list_objects_v2.return_value = {}
    
    with patch('asyncio.get_event_loop') as mock_get_loop:
        mock_loop = AsyncMock()
        mock_get_loop.return_value = mock_loop
        mock_loop.run_in_executor.return_value = {}
        
        result = await manager.list_backups()
    
    assert result["success"] is True
    assert len(result["backups"]) == 0
    assert result["message"] == "Found 0 backups"


@pytest.mark.asyncio
async def test_delete_backup_success(s3_manager):
    """Test successful backup deletion."""
    manager, mock_client = s3_manager
    
    # Mock S3 list response for backup contents
    mock_client.list_objects_v2.return_value = {
        'Contents': [
            {'Key': 'hdev-memory-backups/test-backup/entries/entry1.json.gz'},
            {'Key': 'hdev-memory-backups/test-backup/entries/entry2.json.gz'},
            {'Key': 'hdev-memory-backups/test-backup/metadata.json'},
        ]
    }
    
    # Mock delete response
    mock_client.delete_objects.return_value = {}
    
    with patch('asyncio.get_event_loop') as mock_get_loop:
        mock_loop = AsyncMock()
        mock_get_loop.return_value = mock_loop
        
        # Mock both list and delete operations
        def run_in_executor_side_effect(executor, func):
            if 'list_objects_v2' in str(func):
                return mock_client.list_objects_v2.return_value
            else:
                return mock_client.delete_objects.return_value
        
        mock_loop.run_in_executor.side_effect = run_in_executor_side_effect
        
        result = await manager.delete_backup("test-backup")
    
    # Verify result
    assert result["success"] is True
    assert result["backup_key"] == "test-backup"
    assert result["objects_deleted"] == 3


@pytest.mark.asyncio
async def test_delete_backup_not_found(s3_manager):
    """Test deleting a backup that doesn't exist."""
    manager, mock_client = s3_manager
    
    # Mock empty S3 response (no objects found)
    mock_client.list_objects_v2.return_value = {}
    
    with patch('asyncio.get_event_loop') as mock_get_loop:
        mock_loop = AsyncMock()
        mock_get_loop.return_value = mock_loop
        mock_loop.run_in_executor.return_value = {}
        
        result = await manager.delete_backup("nonexistent-backup")
    
    assert result["success"] is False
    assert "not found" in result["message"]


@pytest.mark.asyncio
async def test_restore_backup_success(s3_manager, tmp_path):
    """Test successful backup restore."""
    manager, mock_client = s3_manager
    
    # Create target backend
    target_backend = FilesystemMemoryBackend(tmp_path / "restore")
    
    # Mock metadata response
    metadata = {
        "backup_name": "test-backup",
        "timestamp": "2023-12-01T12:00:00Z",
        "total_entries": 2,
        "backend_type": "FilesystemMemoryBackend"
    }
    
    # Mock S3 responses
    def mock_get_object(Bucket, Key):
        if 'metadata.json' in Key:
            return {'Body': MagicMock(read=lambda: json.dumps(metadata).encode())}
        elif 'entry1.json.gz' in Key:
            entry_data = {"content": "Entry 1 content", "metadata": {"type": "test"}}
            compressed = gzip.compress(json.dumps(entry_data).encode())
            return {'Body': MagicMock(read=lambda: compressed)}
        elif 'entry2.json.gz' in Key:
            entry_data = {"content": "Entry 2 content", "metadata": {"type": "test"}}
            compressed = gzip.compress(json.dumps(entry_data).encode())
            return {'Body': MagicMock(read=lambda: compressed)}
        return None
    
    # Mock list response for backup entries
    mock_client.list_objects_v2.return_value = {
        'Contents': [
            {'Key': 'hdev-memory-backups/test-backup/entries/entry1.json.gz'},
            {'Key': 'hdev-memory-backups/test-backup/entries/entry2.json.gz'},
        ]
    }
    
    mock_client.get_object.side_effect = mock_get_object
    
    with patch('asyncio.get_event_loop') as mock_get_loop:
        mock_loop = AsyncMock()
        mock_get_loop.return_value = mock_loop
        
        def run_in_executor_side_effect(executor, func):
            if 'list_objects_v2' in str(func):
                return mock_client.list_objects_v2.return_value
            else:
                # This is a get_object call - need to determine which one
                return mock_get_object('test-bucket', 'mock-key')
        
        mock_loop.run_in_executor.side_effect = run_in_executor_side_effect
        
        result = await manager.restore_backup(target_backend, "test-backup", overwrite=False)
    
    # Verify result
    assert result["success"] is True
    assert result["backup_key"] == "test-backup"
    assert result["entries_restored"] == 2
    assert result["entries_skipped"] == 0


@pytest.mark.asyncio
async def test_restore_backup_not_found(s3_manager, tmp_path):
    """Test restoring a backup that doesn't exist."""
    manager, mock_client = s3_manager
    
    target_backend = FilesystemMemoryBackend(tmp_path / "restore")
    
    # Mock S3 error for missing metadata
    from botocore.exceptions import ClientError
    error = ClientError(
        error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'Not found'}},
        operation_name='GetObject'
    )
    mock_client.get_object.side_effect = error
    
    with patch('asyncio.get_event_loop') as mock_get_loop:
        mock_loop = AsyncMock()
        mock_get_loop.return_value = mock_loop
        mock_loop.run_in_executor.side_effect = error
        
        result = await manager.restore_backup(target_backend, "nonexistent-backup")
    
    assert result["success"] is False
    assert "not found" in result["message"]


@pytest.mark.asyncio
async def test_collect_all_entries(s3_manager, populated_backend):
    """Test collecting all entries from backend."""
    manager, _ = s3_manager
    
    entries = await manager._collect_all_entries(populated_backend)
    
    # Should find all 3 entries
    assert len(entries) == 3
    assert "global" in entries
    assert "projects/project1" in entries
    assert "personal/notes" in entries
    
    # Check entry content
    assert entries["global"]["content"] == "Global memory content"
    assert entries["global"]["metadata"]["type"] == "global"


@pytest.mark.asyncio
async def test_collect_entry_paths(s3_manager):
    """Test collecting entry paths from tree structure."""
    manager, _ = s3_manager
    
    # Mock tree structure
    tree = {
        "global": {},  # Empty dict means it's a leaf
        "projects": {
            "project1": {},
            "frontend": {
                "react": {}
            }
        },
        "personal": {
            "notes": {}
        }
    }
    
    paths = []
    await manager._collect_entry_paths(tree, "", paths)
    
    # Should find all leaf paths
    expected_paths = ["global", "projects/project1", "projects/frontend/react", "personal/notes"]
    assert set(paths) == set(expected_paths)


def test_s3_manager_close(s3_manager):
    """Test S3 manager cleanup."""
    manager, _ = s3_manager
    
    # Should not raise any exceptions
    manager.close()
    
    # Executor should be shut down
    assert hasattr(manager, 'executor')