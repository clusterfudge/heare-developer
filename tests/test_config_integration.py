"""Tests for configuration integration with memory backends."""

import pytest
import os
import tempfile
from pathlib import Path

from heare.developer.config import ConfigManager, MemoryConfig
from heare.developer.memory_backends.factory import create_memory_backend
from heare.developer.memory_backends.filesystem import FilesystemMemoryBackend
from heare.developer.memory_backends.http import HTTPMemoryBackend


def test_filesystem_backend_config():
    """Test creating filesystem backend from config."""
    config = MemoryConfig(
        backend="filesystem",
        filesystem_path=Path("/tmp/test-memory")
    )
    
    backend = create_memory_backend(config)
    
    assert isinstance(backend, FilesystemMemoryBackend)
    assert backend.base_dir == Path("/tmp/test-memory")


def test_http_backend_config():
    """Test creating HTTP backend from config."""
    config = MemoryConfig(
        backend="http",
        http_url="https://memory.example.com",
        http_api_key="test-key",
        http_timeout=60
    )
    
    backend = create_memory_backend(config)
    
    assert isinstance(backend, HTTPMemoryBackend)
    assert backend.base_url == "https://memory.example.com"
    assert backend.api_key == "test-key"  
    assert backend.timeout == 60


def test_http_backend_config_missing_url():
    """Test HTTP backend config validation."""
    config = MemoryConfig(
        backend="http",
        # Missing http_url
        http_api_key="test-key"
    )
    
    with pytest.raises(ValueError, match="HTTP backend requires http_url"):
        create_memory_backend(config)


def test_unsupported_backend():
    """Test error for unsupported backend."""
    config = MemoryConfig(backend="unsupported")
    
    with pytest.raises(ValueError, match="Unsupported memory backend"):
        create_memory_backend(config)


def test_config_manager_env_overrides():
    """Test environment variable overrides in config manager."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.yaml"
        
        # Set environment variables
        env_vars = {
            "HDEV_MEMORY_BACKEND": "http",
            "HDEV_MEMORY_HTTP_URL": "https://env-override.com",
            "HDEV_MEMORY_HTTP_API_KEY": "env-key",
            "HDEV_MEMORY_HTTP_TIMEOUT": "120"
        }
        
        # Apply env vars
        for key, value in env_vars.items():
            os.environ[key] = value
        
        try:
            # Create config manager
            config_manager = ConfigManager(config_path)
            config = config_manager.load_config()
            
            # Verify environment overrides
            assert config.memory.backend == "http"
            assert config.memory.http_url == "https://env-override.com"
            assert config.memory.http_api_key == "env-key"
            assert config.memory.http_timeout == 120
            
        finally:
            # Clean up environment variables
            for key in env_vars:
                os.environ.pop(key, None)


def test_config_file_loading():
    """Test loading configuration from YAML file."""
    config_content = """
memory:
  backend: http
  filesystem:
    path: /custom/path
  http:
    url: https://config-file.com
    api_key: file-key
    timeout: 90
  s3:
    bucket: test-bucket
    region: us-west-2
"""
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "config.yaml"
        config_path.write_text(config_content)
        
        config_manager = ConfigManager(config_path)
        config = config_manager.load_config()
        
        assert config.memory.backend == "http"
        assert config.memory.filesystem_path == Path("/custom/path")
        assert config.memory.http_url == "https://config-file.com"
        assert config.memory.http_api_key == "file-key"
        assert config.memory.http_timeout == 90
        assert config.memory.s3_bucket == "test-bucket"
        assert config.memory.s3_region == "us-west-2"