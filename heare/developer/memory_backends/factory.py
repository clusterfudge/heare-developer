"""Factory for creating memory backends based on configuration."""

from pathlib import Path
from typing import Optional

from .base import MemoryBackend
from .filesystem import FilesystemMemoryBackend
from ..config import MemoryConfig, get_config


def create_memory_backend(config: Optional[MemoryConfig] = None) -> MemoryBackend:
    """Create a memory backend based on configuration.
    
    Args:
        config: Memory configuration. If None, loads from global config.
        
    Returns:
        Configured memory backend instance.
        
    Raises:
        ValueError: If backend type is not supported.
    """
    if config is None:
        config = get_config().memory
    
    if config.backend == "filesystem":
        # Use configured path or default
        base_dir = config.filesystem_path or Path.home() / ".hdev" / "memory"
        return FilesystemMemoryBackend(base_dir)
    
    elif config.backend == "http":
        # Import here to avoid circular imports and allow HTTP backend to be optional
        try:
            from .http import HTTPMemoryBackend
            if not config.http_url:
                raise ValueError("HTTP backend requires http_url to be configured")
            return HTTPMemoryBackend(
                base_url=config.http_url,
                api_key=config.http_api_key,
                timeout=config.http_timeout
            )
        except ImportError:
            raise ValueError("HTTP backend not available. Install httpx dependency.")
    
    else:
        raise ValueError(f"Unsupported memory backend: {config.backend}")


def create_memory_manager_with_config(config: Optional[MemoryConfig] = None):
    """Create a MemoryManager with the specified backend configuration.
    
    Args:
        config: Memory configuration. If None, loads from global config.
        
    Returns:
        MemoryManager instance with configured backend.
    """
    from ..memory import MemoryManager
    backend = create_memory_backend(config)
    return MemoryManager(backend=backend)