"""Tests for the memory server."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from heare.developer.memory_server.server import create_app
from heare.developer.memory_backends.filesystem import FilesystemMemoryBackend


@pytest.fixture
def test_backend(tmp_path):
    """Create a test memory backend."""
    return FilesystemMemoryBackend(tmp_path / "memory")


@pytest.fixture
def test_app(test_backend):
    """Create a test FastAPI app."""
    return create_app(backend=test_backend, enable_web_ui=True)


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["healthy"] is True
    assert "timestamp" in data


def test_get_memory_tree(client):
    """Test getting the memory tree."""
    response = client.get("/api/memory/tree")
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "tree"
    assert data["success"] is True
    assert "items" in data


def test_write_and_read_entry(client):
    """Test writing and reading memory entries."""
    # Write an entry
    write_data = {
        "content": "Test content",
        "metadata": {"test": True}
    }
    response = client.put("/api/memory/entry/test/entry", json=write_data)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["path"] == "test/entry"
    
    # Read the entry back
    response = client.get("/api/memory/entry/test/entry")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["content"] == "Test content"
    assert data["metadata"]["test"] is True


def test_delete_entry(client):
    """Test deleting memory entries."""
    # First create an entry
    write_data = {"content": "To be deleted"}
    client.put("/api/memory/entry/delete/me", json=write_data)
    
    # Delete it
    response = client.delete("/api/memory/entry/delete/me")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    # Verify it's gone
    response = client.get("/api/memory/entry/delete/me")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False


def test_search_memory(client):
    """Test searching memory entries."""
    # Create some test entries
    client.put("/api/memory/entry/search/test1", json={"content": "Python programming"})
    client.put("/api/memory/entry/search/test2", json={"content": "JavaScript coding"})
    
    # Search for "programming"
    response = client.get("/api/memory/search?q=programming")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "programming"
    assert len(data["results"]) >= 1
    assert any("search/test1" in result["path"] for result in data["results"])


def test_web_ui_root(client):
    """Test the web UI root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Hdev Memory Server" in response.text


def test_api_key_authentication():
    """Test API key authentication."""
    from heare.developer.memory_backends.filesystem import FilesystemMemoryBackend
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        backend = FilesystemMemoryBackend(Path(tmp_dir) / "memory")
        app = create_app(backend=backend, api_key="test-key")
        client = TestClient(app)
        
        # Request without API key should fail
        response = client.get("/api/memory/tree")
        assert response.status_code == 401
        
        # Request with wrong API key should fail
        response = client.get(
            "/api/memory/tree",
            headers={"Authorization": "Bearer wrong-key"}
        )
        assert response.status_code == 401
        
        # Request with correct API key should succeed
        response = client.get(
            "/api/memory/tree",
            headers={"Authorization": "Bearer test-key"}
        )
        assert response.status_code == 200


def test_backup_restore_placeholders(client):
    """Test backup and restore placeholder endpoints."""
    # Backup
    response = client.post("/api/memory/backup")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "not yet implemented" in data["message"]
    
    # Restore
    response = client.post("/api/memory/restore")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "not yet implemented" in data["message"]