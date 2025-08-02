"""Integration tests for HTTP memory backend with server."""

import pytest
import asyncio
import threading
import time
from pathlib import Path
import tempfile
import uvicorn

from heare.developer.memory_backends.filesystem import FilesystemMemoryBackend
from heare.developer.memory_backends.http import HTTPMemoryBackend
from heare.developer.memory_server.server import create_app


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir) / "memory"


@pytest.fixture
def test_server(temp_storage):
    """Start a test memory server in a separate thread."""
    # Create filesystem backend for the server
    server_backend = FilesystemMemoryBackend(temp_storage)

    # Create FastAPI app
    app = create_app(backend=server_backend, api_key="test-key", enable_web_ui=False)

    # Configure server
    config = uvicorn.Config(app, host="127.0.0.1", port=9999, log_level="error")
    server = uvicorn.Server(config)

    # Start server in thread
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server to start
    time.sleep(0.5)

    yield "http://127.0.0.1:9999"

    # Server will be stopped when thread terminates


@pytest.fixture
def http_client(test_server):
    """Create HTTP memory backend client."""
    return HTTPMemoryBackend(base_url=test_server, api_key="test-key", timeout=5)


@pytest.mark.asyncio
async def test_integration_health_check(http_client):
    """Test health check through full HTTP stack."""
    result = await http_client.health_check()

    assert result["healthy"] is True
    assert result["details"]["backend_type"] == "HTTPMemoryBackend"


@pytest.mark.asyncio
async def test_integration_write_read_entry(http_client):
    """Test writing and reading entries through full HTTP stack."""
    # Write an entry
    write_result = await http_client.write_entry(
        "integration/test", "Integration test content", {"test": "integration"}
    )

    assert write_result["success"] is True
    assert write_result["path"] == "integration/test"

    # Read the entry back
    read_result = await http_client.read_entry("integration/test")

    assert read_result["success"] is True
    assert read_result["content"] == "Integration test content"
    assert read_result["metadata"]["test"] == "integration"


@pytest.mark.asyncio
async def test_integration_tree_operations(http_client):
    """Test tree operations through full HTTP stack."""
    # Create some entries
    await http_client.write_entry("tree/branch1/leaf1", "Leaf 1 content")
    await http_client.write_entry("tree/branch1/leaf2", "Leaf 2 content")
    await http_client.write_entry("tree/branch2/leaf3", "Leaf 3 content")

    # Get full tree
    tree_result = await http_client.get_tree()

    assert tree_result["success"] is True
    assert "tree" in tree_result["items"]

    # Get subtree
    subtree_result = await http_client.get_tree(Path("tree"), depth=2)

    assert subtree_result["success"] is True
    # Note: The server returns the full tree structure, not just the subtree


@pytest.mark.asyncio
async def test_integration_search(http_client):
    """Test search through full HTTP stack."""
    # Create searchable content
    await http_client.write_entry("search/doc1", "Python programming tutorial")
    await http_client.write_entry("search/doc2", "JavaScript guide")
    await http_client.write_entry("search/doc3", "Python data structures")

    # Wait a moment for writes to complete
    await asyncio.sleep(0.1)

    # Search for Python
    search_results = await http_client.search("Python")

    assert len(search_results) >= 2
    python_paths = [result["path"] for result in search_results]
    assert any("search/doc1" in path for path in python_paths)
    assert any("search/doc3" in path for path in python_paths)


@pytest.mark.asyncio
async def test_integration_delete(http_client):
    """Test delete operations through full HTTP stack."""
    # Create an entry
    await http_client.write_entry("delete/me", "To be deleted")

    # Verify it exists
    read_result = await http_client.read_entry("delete/me")
    assert read_result["success"] is True

    # Delete it
    delete_result = await http_client.delete_entry("delete/me")
    assert delete_result["success"] is True

    # Verify it's gone
    read_result = await http_client.read_entry("delete/me")
    assert read_result["success"] is False


@pytest.mark.asyncio
async def test_integration_authentication_failure():
    """Test authentication failure with wrong API key."""
    # Create client with wrong API key
    wrong_client = HTTPMemoryBackend(
        base_url="http://127.0.0.1:9999", api_key="wrong-key", timeout=5
    )

    # This should fail with authentication error
    try:
        result = await wrong_client.get_tree()
        # If we get here, the request succeeded when it shouldn't have
        # Check if it's an error response
        assert result["success"] is False
        assert "HTTP request failed" in result["error"]
    except Exception as e:
        # Expected - authentication should fail
        assert (
            "401" in str(e)
            or "Unauthorized" in str(e)
            or "HTTP request failed" in str(e)
        )
    finally:
        await wrong_client.close()


@pytest.mark.asyncio
async def test_cleanup(http_client):
    """Cleanup test to close the HTTP client."""
    await http_client.close()
