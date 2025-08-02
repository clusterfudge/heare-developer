"""Tests for HTTP memory backend."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from heare.developer.memory_backends.http import HTTPMemoryBackend


@pytest.fixture
def http_backend():
    """Create an HTTP backend for testing."""
    return HTTPMemoryBackend(
        base_url="https://memory.example.com",
        api_key="test-key",
        timeout=10
    )


@pytest.mark.asyncio
async def test_get_tree(http_backend):
    """Test getting memory tree via HTTP."""
    mock_response_data = {
        "type": "tree",
        "path": "",
        "items": {"global": {}, "projects": {}},
        "success": True,
        "error": None
    }
    
    with patch.object(http_backend, '_make_request') as mock_request:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        result = await http_backend.get_tree()
        
        assert result["success"] is True
        assert result["type"] == "tree"
        assert "global" in result["items"]
        
        mock_request.assert_called_once_with(
            "GET", "/api/memory/tree", params={"depth": -1}
        )


@pytest.mark.asyncio
async def test_get_tree_with_prefix(http_backend):
    """Test getting memory tree with prefix."""
    mock_response_data = {
        "type": "tree",
        "path": "projects",
        "items": {"project1": {}},
        "success": True,
        "error": None
    }
    
    with patch.object(http_backend, '_make_request') as mock_request:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        result = await http_backend.get_tree(Path("projects"), depth=2)
        
        assert result["success"] is True
        assert result["path"] == "projects"
        
        mock_request.assert_called_once_with(
            "GET", "/api/memory/tree", params={"depth": 2, "prefix": "projects"}
        )


@pytest.mark.asyncio
async def test_read_entry(http_backend):
    """Test reading memory entry via HTTP."""
    mock_response_data = {
        "type": "file",
        "path": "test/entry",
        "content": "Test content",
        "metadata": {"version": 1},
        "success": True,
        "error": None
    }
    
    with patch.object(http_backend, '_make_request') as mock_request:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        result = await http_backend.read_entry("test/entry")
        
        assert result["success"] is True
        assert result["content"] == "Test content"
        assert result["metadata"]["version"] == 1
        
        mock_request.assert_called_once_with("GET", "/api/memory/entry/test/entry")


@pytest.mark.asyncio
async def test_write_entry(http_backend):
    """Test writing memory entry via HTTP."""
    mock_response_data = {
        "path": "test/entry",
        "success": True,
        "message": "Entry written successfully",
        "error": None
    }
    
    with patch.object(http_backend, '_make_request') as mock_request:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        result = await http_backend.write_entry(
            "test/entry", 
            "Test content", 
            {"version": 1}
        )
        
        assert result["success"] is True
        assert result["path"] == "test/entry"
        
        mock_request.assert_called_once_with(
            "PUT", 
            "/api/memory/entry/test/entry",
            json={"content": "Test content", "metadata": {"version": 1}}
        )


@pytest.mark.asyncio
async def test_delete_entry(http_backend):
    """Test deleting memory entry via HTTP."""
    mock_response_data = {
        "path": "test/entry",
        "success": True,
        "message": "Entry deleted successfully",
        "error": None
    }
    
    with patch.object(http_backend, '_make_request') as mock_request:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        result = await http_backend.delete_entry("test/entry")
        
        assert result["success"] is True
        assert result["path"] == "test/entry"
        
        mock_request.assert_called_once_with("DELETE", "/api/memory/entry/test/entry")


@pytest.mark.asyncio
async def test_search(http_backend):
    """Test searching memory via HTTP."""
    mock_response_data = {
        "query": "test",
        "results": [
            {"path": "test/entry", "snippet": "Test content", "score": 0.9}
        ],
        "success": True,
        "error": None
    }
    
    with patch.object(http_backend, '_make_request') as mock_request:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        result = await http_backend.search("test", prefix="projects")
        
        assert len(result) == 1
        assert result[0]["path"] == "test/entry"
        assert result[0]["score"] == 0.9
        
        mock_request.assert_called_once_with(
            "GET", "/api/memory/search", params={"q": "test", "prefix": "projects"}
        )


@pytest.mark.asyncio
async def test_health_check(http_backend):
    """Test health check via HTTP."""
    mock_response_data = {
        "healthy": True,
        "message": "Backend is healthy",
        "details": {"backend_type": "FilesystemMemoryBackend"},
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    with patch.object(http_backend, '_make_request') as mock_request:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_request.return_value = mock_response
        
        result = await http_backend.health_check()
        
        assert result["healthy"] is True
        assert result["details"]["backend_type"] == "HTTPMemoryBackend"
        assert result["details"]["base_url"] == "https://memory.example.com"
        
        mock_request.assert_called_once_with("GET", "/api/health")


@pytest.mark.asyncio
async def test_request_error_handling(http_backend):
    """Test error handling in HTTP requests."""
    with patch.object(http_backend, '_make_request') as mock_request:
        mock_request.side_effect = httpx.HTTPError("Connection failed")
        
        result = await http_backend.get_tree()
        
        assert result["success"] is False
        assert "HTTP request failed" in result["error"]


@pytest.mark.asyncio
async def test_retry_logic():
    """Test the retry logic in _make_request."""
    backend = HTTPMemoryBackend(
        base_url="https://memory.example.com",
        max_retries=2
    )
    
    with patch.object(backend.client, 'request') as mock_request:
        # Create proper mock responses
        error_response1 = AsyncMock()
        error_response1.side_effect = httpx.ConnectError("Connection failed")
        
        error_response2 = AsyncMock()
        error_response2.side_effect = httpx.TimeoutException("Timeout")
        
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.raise_for_status = MagicMock()
        
        # First two calls fail, third succeeds
        mock_request.side_effect = [
            httpx.ConnectError("Connection failed"),
            httpx.TimeoutException("Timeout"),
            success_response
        ]
        
        response = await backend._make_request("GET", "/api/health")
        
        assert mock_request.call_count == 3
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_context_manager():
    """Test using HTTP backend as async context manager."""
    async with HTTPMemoryBackend("https://memory.example.com") as backend:
        assert backend.client is not None
    
    # Client should be closed after exiting context


def test_initialization():
    """Test HTTP backend initialization."""
    backend = HTTPMemoryBackend(
        base_url="https://memory.example.com/",  # Note trailing slash
        api_key="test-key",
        timeout=60
    )
    
    assert backend.base_url == "https://memory.example.com"  # Trailing slash removed
    assert backend.api_key == "test-key"
    assert backend.timeout == 60
    assert "Authorization" in backend.headers
    assert backend.headers["Authorization"] == "Bearer test-key"