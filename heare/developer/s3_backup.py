"""S3 backup and restore functionality for memory server."""

import json
import gzip
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

from .memory_backends.base import MemoryBackend
from .config import MemoryConfig

logger = logging.getLogger(__name__)


class S3BackupManager:
    """Manages S3 backup and restore operations for memory backends."""
    
    def __init__(self, config: MemoryConfig):
        """Initialize S3 backup manager.
        
        Args:
            config: Memory configuration with S3 settings
        """
        if not S3_AVAILABLE:
            raise ImportError("boto3 is required for S3 backup functionality. Install with: pip install boto3")
        
        self.config = config
        self.bucket = config.s3_bucket
        self.region = config.s3_region
        
        if not self.bucket:
            raise ValueError("S3 bucket must be configured for backup operations")
        
        # Create S3 client
        session = boto3.Session(
            aws_access_key_id=config.s3_access_key_id,
            aws_secret_access_key=config.s3_secret_access_key,
            region_name=config.s3_region
        )
        
        client_config = {}
        if config.s3_endpoint_url:
            client_config['endpoint_url'] = config.s3_endpoint_url
        
        self.s3_client = session.client('s3', **client_config)
        
        # Thread pool for async S3 operations
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def backup_all(self, backend: MemoryBackend, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """Backup all memory entries to S3.
        
        Args:
            backend: Memory backend to backup
            backup_name: Optional custom backup name. If None, uses timestamp.
            
        Returns:
            Dictionary with backup results
        """
        try:
            # Generate backup name if not provided
            if backup_name is None:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{timestamp}"
            
            logger.info(f"Starting backup '{backup_name}' to S3 bucket '{self.bucket}'")
            
            # Get all entries from backend
            entries = await self._collect_all_entries(backend)
            
            if not entries:
                return {
                    "success": True,
                    "backup_key": backup_name,
                    "message": "No entries found to backup",
                    "entries_backed_up": 0,
                    "backup_size_bytes": 0
                }
            
            # Create backup metadata
            backup_metadata = {
                "backup_name": backup_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_entries": len(entries),
                "backend_type": type(backend).__name__,
                "version": "1.0"
            }
            
            # Backup entries in batches
            backup_size = 0
            success_count = 0
            errors = []
            
            for entry_path, entry_data in entries.items():
                try:
                    await self._backup_entry(backup_name, entry_path, entry_data)
                    success_count += 1
                    backup_size += len(json.dumps(entry_data).encode('utf-8'))
                except Exception as e:
                    logger.error(f"Failed to backup entry {entry_path}: {e}")
                    errors.append({"path": entry_path, "error": str(e)})
            
            # Upload metadata
            await self._upload_metadata(backup_name, backup_metadata)
            
            success = len(errors) == 0
            message = f"Backup completed. {success_count} entries backed up"
            if errors:
                message += f", {len(errors)} failed"
            
            return {
                "success": success,
                "backup_key": backup_name,
                "message": message,
                "entries_backed_up": success_count,
                "backup_size_bytes": backup_size,
                "errors": errors[:5]  # Limit error list
            }
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {
                "success": False,
                "backup_key": backup_name,
                "message": f"Backup failed: {str(e)}",
                "error": str(e)
            }
    
    async def restore_backup(
        self, 
        backend: MemoryBackend, 
        backup_key: str, 
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """Restore memory entries from S3 backup.
        
        Args:
            backend: Memory backend to restore to
            backup_key: S3 backup key to restore from
            overwrite: Whether to overwrite existing entries
            
        Returns:
            Dictionary with restore results
        """
        try:
            logger.info(f"Starting restore from backup '{backup_key}'")
            
            # Get backup metadata
            metadata = await self._get_backup_metadata(backup_key)
            if not metadata:
                return {
                    "success": False,
                    "message": f"Backup '{backup_key}' not found or metadata missing",
                    "error": "Backup not found"
                }
            
            # List all entries in the backup
            backup_entries = await self._list_backup_entries(backup_key)
            
            if not backup_entries:
                return {
                    "success": True,
                    "backup_key": backup_key,
                    "message": "No entries found in backup",
                    "entries_restored": 0
                }
            
            # Restore entries
            success_count = 0
            skipped_count = 0
            errors = []
            
            for entry_path in backup_entries:
                try:
                    # Check if entry exists in target
                    if not overwrite:
                        existing_result = await backend.read_entry(entry_path)
                        if existing_result["success"]:
                            skipped_count += 1
                            continue
                    
                    # Download and restore entry
                    entry_data = await self._download_entry(backup_key, entry_path)
                    if entry_data:
                        result = await backend.write_entry(
                            entry_path,
                            entry_data["content"],
                            entry_data["metadata"]
                        )
                        if result["success"]:
                            success_count += 1
                        else:
                            errors.append({"path": entry_path, "error": result["error"]})
                    else:
                        errors.append({"path": entry_path, "error": "Failed to download entry data"})
                        
                except Exception as e:
                    logger.error(f"Failed to restore entry {entry_path}: {e}")
                    errors.append({"path": entry_path, "error": str(e)})
            
            success = len(errors) == 0
            message = f"Restore completed. {success_count} entries restored"
            if skipped_count > 0:
                message += f", {skipped_count} skipped"
            if errors:
                message += f", {len(errors)} failed"
            
            return {
                "success": success,
                "backup_key": backup_key,
                "message": message,
                "entries_restored": success_count,
                "entries_skipped": skipped_count,
                "backup_metadata": metadata,
                "errors": errors[:5]  # Limit error list
            }
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {
                "success": False,
                "backup_key": backup_key,
                "message": f"Restore failed: {str(e)}",
                "error": str(e)
            }
    
    async def list_backups(self) -> Dict[str, Any]:
        """List all available backups in S3.
        
        Returns:
            Dictionary with list of available backups
        """
        try:
            # List all backup prefixes
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: self.s3_client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix="hdev-memory-backups/",
                    Delimiter="/"
                )
            )
            
            backups = []
            if 'CommonPrefixes' in response:
                for prefix in response['CommonPrefixes']:
                    backup_name = prefix['Prefix'].split('/')[-2]
                    if backup_name:
                        # Try to get metadata for this backup
                        metadata = await self._get_backup_metadata(backup_name, silent=True)
                        backup_info = {
                            "backup_key": backup_name,
                            "timestamp": metadata.get("timestamp", "unknown") if metadata else "unknown",
                            "total_entries": metadata.get("total_entries", 0) if metadata else 0,
                            "backend_type": metadata.get("backend_type", "unknown") if metadata else "unknown"
                        }
                        backups.append(backup_info)
            
            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return {
                "success": True,
                "backups": backups,
                "message": f"Found {len(backups)} backups"
            }
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return {
                "success": False,
                "message": f"Failed to list backups: {str(e)}",
                "error": str(e)
            }
    
    async def delete_backup(self, backup_key: str) -> Dict[str, Any]:
        """Delete a backup from S3.
        
        Args:
            backup_key: Backup key to delete
            
        Returns:
            Dictionary with deletion results
        """
        try:
            logger.info(f"Deleting backup '{backup_key}'")
            
            # List all objects with this backup prefix
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: self.s3_client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=f"hdev-memory-backups/{backup_key}/"
                )
            )
            
            if 'Contents' not in response:
                return {
                    "success": False,
                    "message": f"Backup '{backup_key}' not found",
                    "error": "Backup not found"
                }
            
            # Delete all objects
            objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
            
            if objects_to_delete:
                await loop.run_in_executor(
                    self.executor,
                    lambda: self.s3_client.delete_objects(
                        Bucket=self.bucket,
                        Delete={'Objects': objects_to_delete}
                    )
                )
            
            return {
                "success": True,
                "backup_key": backup_key,
                "message": f"Backup '{backup_key}' deleted successfully",
                "objects_deleted": len(objects_to_delete)
            }
            
        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
            return {
                "success": False,
                "backup_key": backup_key,
                "message": f"Failed to delete backup: {str(e)}",
                "error": str(e)
            }
    
    async def _collect_all_entries(self, backend: MemoryBackend) -> Dict[str, Dict[str, Any]]:
        """Collect all entries from the backend."""
        entries = {}
        
        # Get tree structure
        tree_result = await backend.get_tree()
        if not tree_result["success"]:
            return entries
        
        # Collect entry paths
        entry_paths = []
        await self._collect_entry_paths(tree_result["items"], "", entry_paths)
        
        # Read all entries
        for path in entry_paths:
            try:
                result = await backend.read_entry(path)
                if result["success"] and result["type"] == "file":
                    entries[path] = {
                        "content": result["content"],
                        "metadata": result["metadata"]
                    }
            except Exception as e:
                logger.warning(f"Failed to read entry {path}: {e}")
        
        return entries
    
    async def _collect_entry_paths(self, tree: Dict, prefix: str, paths: List[str]):
        """Recursively collect entry paths from tree."""
        for key, value in tree.items():
            if key == "...":
                continue
            
            current_path = f"{prefix}/{key}" if prefix else key
            
            if isinstance(value, dict) and value:
                await self._collect_entry_paths(value, current_path, paths)
            else:
                paths.append(current_path)
    
    async def _backup_entry(self, backup_name: str, entry_path: str, entry_data: Dict[str, Any]):
        """Backup a single entry to S3."""
        s3_key = f"hdev-memory-backups/{backup_name}/entries/{entry_path}.json.gz"
        
        # Compress entry data
        json_bytes = json.dumps(entry_data, indent=2).encode('utf-8')
        compressed_data = gzip.compress(json_bytes)
        
        # Upload to S3
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=compressed_data,
                ContentType='application/json',
                ContentEncoding='gzip',
                Metadata={
                    'entry_path': entry_path,
                    'backup_name': backup_name,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            )
        )
    
    async def _upload_metadata(self, backup_name: str, metadata: Dict[str, Any]):
        """Upload backup metadata to S3."""
        s3_key = f"hdev-memory-backups/{backup_name}/metadata.json"
        
        json_data = json.dumps(metadata, indent=2).encode('utf-8')
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            lambda: self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=json_data,
                ContentType='application/json'
            )
        )
    
    async def _get_backup_metadata(self, backup_key: str, silent: bool = False) -> Optional[Dict[str, Any]]:
        """Get backup metadata from S3."""
        try:
            s3_key = f"hdev-memory-backups/{backup_key}/metadata.json"
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: self.s3_client.get_object(Bucket=self.bucket, Key=s3_key)
            )
            
            return json.loads(response['Body'].read().decode('utf-8'))
            
        except (ClientError, BotoCoreError) as e:
            if not silent:
                logger.error(f"Failed to get backup metadata: {e}")
            return None
    
    async def _list_backup_entries(self, backup_key: str) -> List[str]:
        """List all entry paths in a backup."""
        try:
            prefix = f"hdev-memory-backups/{backup_key}/entries/"
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: self.s3_client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=prefix
                )
            )
            
            entries = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Extract entry path from S3 key (remove prefix and .json.gz suffix)
                    key = obj['Key']
                    if key.startswith(prefix) and key.endswith('.json.gz'):
                        entry_path = key[len(prefix):-8]  # Remove prefix and .json.gz
                        entries.append(entry_path)
            
            return entries
            
        except Exception as e:
            logger.error(f"Failed to list backup entries: {e}")
            return []
    
    async def _download_entry(self, backup_key: str, entry_path: str) -> Optional[Dict[str, Any]]:
        """Download and decompress an entry from S3."""
        try:
            s3_key = f"hdev-memory-backups/{backup_key}/entries/{entry_path}.json.gz"
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: self.s3_client.get_object(Bucket=self.bucket, Key=s3_key)
            )
            
            # Decompress and parse
            compressed_data = response['Body'].read()
            json_bytes = gzip.decompress(compressed_data)
            return json.loads(json_bytes.decode('utf-8'))
            
        except Exception as e:
            logger.error(f"Failed to download entry {entry_path}: {e}")
            return None
    
    def close(self):
        """Clean up resources."""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)