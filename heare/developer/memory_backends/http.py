"""HTTP-based memory backend implementation."""

import httpx
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

from .base import MemoryBackend

logger = logging.getLogger(__name__)


class HTTPMemoryBackend(MemoryBackend):
    """HTTP-based implementation of the memory backend.
    
    This backend communicates with a remote memory server via REST API.
    """

    def __init__(
        self, 
        base_url: str, 
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """Initialize the HTTP memory backend.
        
        Args:
            base_url: Base URL of the memory server (e.g., "https://memory.example.com")
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Prepare headers
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        
        # Create HTTP client with retry logic
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers=self.headers,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )

    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> httpx.Response:
        """Make an HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments to pass to httpx
            
        Returns:
            HTTP response
            
        Raises:
            httpx.HTTPError: If request fails after all retries
        """
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}")
                if attempt == self.max_retries:
                    raise
                # Simple exponential backoff
                import asyncio
                await asyncio.sleep(2 ** attempt)
        
        # This should never be reached, but just in case
        raise httpx.HTTPError(f"Failed to make request after {self.max_retries + 1} attempts")

    async def get_tree(
        self, prefix: Optional[Path] = None, depth: int = -1
    ) -> Dict[str, Any]:
        """Get the memory tree structure starting from the given prefix.

        Args:
            prefix: The prefix path to start from (None for root)
            depth: How deep to traverse (-1 for unlimited)

        Returns:
            A dictionary representing the memory tree structure
        """
        try:
            params = {"depth": depth}
            if prefix:
                params["prefix"] = str(prefix)
            
            response = await self._make_request("GET", "/api/memory/tree", params=params)
            return response.json()
            
        except Exception as e:
            logger.error(f"Error getting memory tree: {e}")
            return {
                "type": "tree",
                "path": str(prefix) if prefix else "",
                "items": {},
                "success": False,
                "error": f"HTTP request failed: {str(e)}",
            }

    async def read_entry(self, path: str) -> Dict[str, Any]:
        """Read a memory entry.

        Args:
            path: Path to the memory entry

        Returns:
            A dictionary containing the memory entry details
        """
        try:
            response = await self._make_request("GET", f"/api/memory/entry/{path}")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error reading memory entry {path}: {e}")
            return {
                "type": "error",
                "path": path,
                "content": None,
                "metadata": None,
                "success": False,
                "error": f"HTTP request failed: {str(e)}",
            }

    async def write_entry(
        self, path: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Write a memory entry.

        Args:
            path: Path to the memory entry
            content: Content to write
            metadata: Optional metadata

        Returns:
            A dictionary with operation results
        """
        try:
            data = {"content": content}
            if metadata:
                data["metadata"] = metadata
            
            response = await self._make_request(
                "PUT", f"/api/memory/entry/{path}", json=data
            )
            return response.json()
            
        except Exception as e:
            logger.error(f"Error writing memory entry {path}: {e}")
            return {
                "path": path,
                "success": False,
                "message": None,
                "error": f"HTTP request failed: {str(e)}",
            }

    async def delete_entry(self, path: str) -> Dict[str, Any]:
        """Delete a memory entry.

        Args:
            path: Path to the memory entry or directory to delete

        Returns:
            A dictionary with operation results
        """
        try:
            response = await self._make_request("DELETE", f"/api/memory/entry/{path}")
            return response.json()
            
        except Exception as e:
            logger.error(f"Error deleting memory entry {path}: {e}")
            return {
                "path": path,
                "success": False,
                "message": None,
                "error": f"HTTP request failed: {str(e)}",
            }

    async def search(self, query: str, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for memory entries matching the query.

        Args:
            query: Search query
            prefix: Optional path prefix to limit search scope

        Returns:
            List of dictionaries containing search results
        """
        try:
            params = {"q": query}
            if prefix:
                params["prefix"] = prefix
            
            response = await self._make_request("GET", "/api/memory/search", params=params)
            data = response.json()
            
            # Convert from API response format to expected format
            return data.get("results", [])
            
        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the backend.

        Returns:
            A dictionary with health status
        """
        try:
            response = await self._make_request("GET", "/api/health")
            data = response.json()
            return {
                "healthy": data.get("healthy", False),
                "message": data.get("message", "Unknown status"),
                "details": {
                    "backend_type": self.__class__.__name__,
                    "server_details": data.get("details", {}),
                    "base_url": self.base_url,
                }
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "message": f"Health check failed: {str(e)}",
                "details": {
                    "backend_type": self.__class__.__name__,
                    "base_url": self.base_url,
                    "error": str(e)
                }
            }

    async def close(self):
        """Close the HTTP client connection."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()