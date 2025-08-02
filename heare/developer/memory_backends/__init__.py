"""Memory backend implementations for different storage types."""

from .base import MemoryBackend
from .filesystem import FilesystemMemoryBackend
from .factory import create_memory_backend, create_memory_manager_with_config

# HTTP backend is optional and imported on demand
try:
    from .http import HTTPMemoryBackend
    __all__ = ["MemoryBackend", "FilesystemMemoryBackend", "HTTPMemoryBackend", "create_memory_backend", "create_memory_manager_with_config"]
except ImportError:
    __all__ = ["MemoryBackend", "FilesystemMemoryBackend", "create_memory_backend", "create_memory_manager_with_config"]