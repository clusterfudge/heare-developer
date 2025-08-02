"""Abstract base class for memory backends."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List


class MemoryBackend(ABC):
    """Abstract base class for memory storage backends.

    This class defines the interface that all memory backends must implement.
    Backends can be filesystem-based, HTTP-based, or any other storage mechanism.
    """

    @abstractmethod
    async def get_tree(
        self, prefix: Optional[Path] = None, depth: int = -1
    ) -> Dict[str, Any]:
        """Get the memory tree structure starting from the given prefix.

        Args:
            prefix: The prefix path to start from (None for root)
            depth: How deep to traverse (-1 for unlimited)

        Returns:
            A dictionary representing the memory tree structure:
            {
                "type": "tree",
                "path": str,
                "items": dict,
                "success": bool,
                "error": str|None
            }
        """

    @abstractmethod
    async def read_entry(self, path: str) -> Dict[str, Any]:
        """Read a memory entry.

        Args:
            path: Path to the memory entry

        Returns:
            A dictionary containing the memory entry details:
            - For files: {"type": "file", "path": str, "content": str, "metadata": dict, "success": bool, "error": str|None}
            - For directories: {"type": "directory", "path": str, "items": list, "success": bool, "error": str|None}
        """

    @abstractmethod
    async def write_entry(
        self, path: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Write a memory entry.

        Args:
            path: Path to the memory entry
            content: Content to write
            metadata: Optional metadata

        Returns:
            A dictionary with operation results:
            {"path": str, "success": bool, "message": str, "error": str|None}
        """

    @abstractmethod
    async def delete_entry(self, path: str) -> Dict[str, Any]:
        """Delete a memory entry.

        Args:
            path: Path to the memory entry or directory to delete

        Returns:
            A dictionary with operation results:
            {"path": str, "success": bool, "message": str, "error": str|None}
        """

    @abstractmethod
    async def search(
        self, query: str, prefix: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for memory entries matching the query.

        Args:
            query: Search query
            prefix: Optional path prefix to limit search scope

        Returns:
            List of dictionaries containing search results:
            [{"path": str, "snippet": str, "score": float}, ...]
        """

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the backend.

        Returns:
            A dictionary with health status:
            {"healthy": bool, "message": str, "details": dict}
        """
        try:
            # Simple health check - try to get the root tree
            result = await self.get_tree(depth=0)
            return {
                "healthy": result.get("success", False),
                "message": "Backend is healthy"
                if result.get("success")
                else "Backend unhealthy",
                "details": {"backend_type": self.__class__.__name__},
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Health check failed: {str(e)}",
                "details": {"backend_type": self.__class__.__name__, "error": str(e)},
            }
