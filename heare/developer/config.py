"""Configuration management for hdev."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class MemoryConfig:
    """Configuration for memory backend."""
    backend: str = "filesystem"  # "filesystem" or "http"
    
    # Filesystem backend config
    filesystem_path: Optional[Path] = None
    
    # HTTP backend config
    http_url: Optional[str] = None
    http_api_key: Optional[str] = None
    http_timeout: int = 30
    
    # S3 backup config
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
    s3_endpoint_url: Optional[str] = None  # For S3-compatible services like MinIO


@dataclass
class HdevConfig:
    """Main configuration for hdev."""
    memory: MemoryConfig = field(default_factory=MemoryConfig)


class ConfigManager:
    """Manages configuration loading and saving."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the config manager.
        
        Args:
            config_path: Path to config file. If None, uses default location.
        """
        self.config_path = config_path or Path.home() / ".hdev" / "config.yaml"
        self._config: Optional[HdevConfig] = None
    
    def load_config(self) -> HdevConfig:
        """Load configuration from file or return defaults."""
        if self._config is not None:
            return self._config
            
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = yaml.safe_load(f) or {}
                
                # Parse memory config
                memory_data = data.get('memory', {})
                memory_config = MemoryConfig(
                    backend=memory_data.get('backend', 'filesystem'),
                    filesystem_path=Path(memory_data['filesystem']['path']) if memory_data.get('filesystem', {}).get('path') else None,
                    http_url=memory_data.get('http', {}).get('url'),
                    http_api_key=memory_data.get('http', {}).get('api_key'),
                    http_timeout=memory_data.get('http', {}).get('timeout', 30),
                    s3_bucket=memory_data.get('s3', {}).get('bucket'),
                    s3_region=memory_data.get('s3', {}).get('region', 'us-east-1'),
                    s3_access_key_id=memory_data.get('s3', {}).get('access_key_id'),
                    s3_secret_access_key=memory_data.get('s3', {}).get('secret_access_key'),
                    s3_endpoint_url=memory_data.get('s3', {}).get('endpoint_url'),
                )
                
                self._config = HdevConfig(memory=memory_config)
                
            except Exception as e:
                print(f"Warning: Error loading config from {self.config_path}: {e}")
                self._config = HdevConfig()
        else:
            self._config = HdevConfig()
        
        # Override with environment variables
        self._apply_env_overrides()
        
        return self._config
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides to config."""
        if not self._config:
            return
            
        # Memory backend overrides
        if os.getenv('HDEV_MEMORY_BACKEND'):
            self._config.memory.backend = os.getenv('HDEV_MEMORY_BACKEND')
        
        if os.getenv('HDEV_MEMORY_FILESYSTEM_PATH'):
            self._config.memory.filesystem_path = Path(os.getenv('HDEV_MEMORY_FILESYSTEM_PATH'))
        
        if os.getenv('HDEV_MEMORY_HTTP_URL'):
            self._config.memory.http_url = os.getenv('HDEV_MEMORY_HTTP_URL')
        
        if os.getenv('HDEV_MEMORY_HTTP_API_KEY'):
            self._config.memory.http_api_key = os.getenv('HDEV_MEMORY_HTTP_API_KEY')
        
        if os.getenv('HDEV_MEMORY_HTTP_TIMEOUT'):
            try:
                self._config.memory.http_timeout = int(os.getenv('HDEV_MEMORY_HTTP_TIMEOUT'))
            except ValueError:
                pass
        
        # S3 overrides
        if os.getenv('HDEV_S3_BUCKET'):
            self._config.memory.s3_bucket = os.getenv('HDEV_S3_BUCKET')
        
        if os.getenv('HDEV_S3_REGION'):
            self._config.memory.s3_region = os.getenv('HDEV_S3_REGION')
        
        if os.getenv('HDEV_S3_ACCESS_KEY_ID'):
            self._config.memory.s3_access_key_id = os.getenv('HDEV_S3_ACCESS_KEY_ID')
        
        if os.getenv('HDEV_S3_SECRET_ACCESS_KEY'):
            self._config.memory.s3_secret_access_key = os.getenv('HDEV_S3_SECRET_ACCESS_KEY')
        
        if os.getenv('HDEV_S3_ENDPOINT_URL'):
            self._config.memory.s3_endpoint_url = os.getenv('HDEV_S3_ENDPOINT_URL')
    
    def save_config(self, config: HdevConfig):
        """Save configuration to file.
        
        Args:
            config: Configuration to save
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'memory': {
                'backend': config.memory.backend,
                'filesystem': {
                    'path': str(config.memory.filesystem_path) if config.memory.filesystem_path else None
                },
                'http': {
                    'url': config.memory.http_url,
                    'api_key': config.memory.http_api_key,
                    'timeout': config.memory.http_timeout,
                },
                's3': {
                    'bucket': config.memory.s3_bucket,
                    'region': config.memory.s3_region,
                    'access_key_id': config.memory.s3_access_key_id,
                    'secret_access_key': config.memory.s3_secret_access_key,
                    'endpoint_url': config.memory.s3_endpoint_url,
                }
            }
        }
        
        # Remove None values to keep config clean
        data = self._remove_none_values(data)
        
        with open(self.config_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        
        self._config = config
    
    def _remove_none_values(self, data):
        """Recursively remove None values from dict."""
        if isinstance(data, dict):
            return {k: self._remove_none_values(v) for k, v in data.items() if v is not None}
        elif isinstance(data, list):
            return [self._remove_none_values(item) for item in data if item is not None]
        else:
            return data


# Global config manager instance
_config_manager = None

def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def get_config() -> HdevConfig:
    """Get the current configuration."""
    return get_config_manager().load_config()