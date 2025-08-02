import json
from pathlib import Path
from typing import Optional, Dict, Any, List
import asyncio

from .memory_backends.base import MemoryBackend
from .memory_backends.filesystem import FilesystemMemoryBackend


class MemoryManager:
    """Memory manager for persistent memory storage.

    This class now serves as a wrapper around different memory backends (filesystem, HTTP, etc.)
    while maintaining backward compatibility with the original interface.
    """

    def __init__(self, base_dir: Path | None = None, backend: MemoryBackend | None = None):
        """Initialize the memory manager.
        
        Args:
            base_dir: Legacy parameter for backward compatibility with filesystem backend
            backend: Optional memory backend instance. If not provided, uses FilesystemMemoryBackend
        """
        if backend is not None:
            self.backend = backend
        else:
            # Use filesystem backend for backward compatibility
            self.backend = FilesystemMemoryBackend(base_dir)
        
        # Maintain backward compatibility - expose base_dir if using filesystem backend
        if isinstance(self.backend, FilesystemMemoryBackend):
            self.base_dir = self.backend.base_dir
        else:
            self.base_dir = None

        # Default memory settings (kept for compatibility)
        self.MAX_MEMORY_TOKENS = 100000
        self.CRITIQUE_THRESHOLD = 0.75
        self.CRITIQUE_INTERVAL = 10
        self.CRITIQUE_IN_SUMMARY = True

    def _run_async(self, coro):
        """Helper method to run async operations synchronously for backward compatibility."""
        # For filesystem backend, we can run synchronously if needed
        if isinstance(self.backend, FilesystemMemoryBackend):
            # Create a synchronous version of the operation for filesystem backend
            import inspect
            if inspect.iscoroutine(coro):
                # The filesystem backend methods are async but they don't actually need to be
                # For now, let's run them in the event loop
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context, schedule the coroutine  
                    import concurrent.futures
                    import threading
                    
                    def run_in_thread():
                        return asyncio.run(coro)
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_in_thread)
                        return future.result()
                        
                except RuntimeError:
                    # No event loop running, create a new one
                    return asyncio.run(coro)
        
        # For other backends, try to run normally
        try:
            return asyncio.run(coro)
        except RuntimeError:
            # Already in async context, this is a limitation
            raise RuntimeError(
                "Cannot run synchronous memory operations from within an async context. "
                "Use the async methods directly."
            )

    def get_tree(
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
        return self._run_async(self.backend.get_tree(prefix, depth))

    def read_entry(self, path: str) -> Dict[str, Any]:
        """Read a memory entry.

        Args:
            path: Path to the memory entry

        Returns:
            A dictionary containing the memory entry details:
            - For files: {"type": "file", "path": str, "content": str, "metadata": dict, "success": bool, "error": str|None}
            - For directories: {"type": "directory", "path": str, "items": list, "success": bool, "error": str|None}
        """
        return self._run_async(self.backend.read_entry(path))

    def write_entry(
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
        return self._run_async(self.backend.write_entry(path, content, metadata))

    def delete_entry(self, path: str) -> Dict[str, Any]:
        """Delete a memory entry.

        Args:
            path: Path to the memory entry or directory to delete

        Returns:
            A dictionary with operation results:
            {"path": str, "success": bool, "message": str, "error": str|None}
        """
        return self._run_async(self.backend.delete_entry(path))

    # Async methods for direct backend access
    async def get_tree_async(
        self, prefix: Optional[Path] = None, depth: int = -1
    ) -> Dict[str, Any]:
        """Async version of get_tree."""
        return await self.backend.get_tree(prefix, depth)

    async def read_entry_async(self, path: str) -> Dict[str, Any]:
        """Async version of read_entry."""
        return await self.backend.read_entry(path)

    async def write_entry_async(
        self, path: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Async version of write_entry."""
        return await self.backend.write_entry(path, content, metadata)

    async def delete_entry_async(self, path: str) -> Dict[str, Any]:
        """Async version of delete_entry."""
        return await self.backend.delete_entry(path)

    async def search_async(self, query: str, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for memory entries matching the query."""
        return await self.backend.search(query, prefix)
