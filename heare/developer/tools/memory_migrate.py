"""Memory migration tools for copying between backends."""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from heare.developer.context import AgentContext
from heare.developer.tools.framework import tool
from heare.developer.memory_backends.factory import create_memory_backend
from heare.developer.memory_backends.filesystem import FilesystemMemoryBackend
from heare.developer.memory_backends.http import HTTPMemoryBackend
from heare.developer.config import MemoryConfig, get_config

logger = logging.getLogger(__name__)


class MemoryMigrator:
    """Handles migration of memory entries between different backends."""
    
    def __init__(self, source_backend, target_backend):
        """Initialize the memory migrator.
        
        Args:
            source_backend: Source memory backend to copy from
            target_backend: Target memory backend to copy to
        """
        self.source_backend = source_backend
        self.target_backend = target_backend
        self.stats = {
            "total_entries": 0,
            "copied_entries": 0,
            "skipped_entries": 0,
            "failed_entries": 0,
            "errors": []
        }
    
    async def migrate_all(self, overwrite: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        """Migrate all memory entries from source to target backend.
        
        Args:
            overwrite: Whether to overwrite existing entries in target
            dry_run: If True, only simulate the migration without actual copying
            
        Returns:
            Dictionary with migration statistics and results
        """
        logger.info(f"Starting memory migration (dry_run: {dry_run}, overwrite: {overwrite})")
        
        # Reset stats
        self.stats = {
            "total_entries": 0,
            "copied_entries": 0,
            "skipped_entries": 0,
            "failed_entries": 0,
            "errors": []
        }
        
        # Get all entries from source
        entries = await self._discover_entries()
        self.stats["total_entries"] = len(entries)
        
        if not entries:
            return {
                "success": True,
                "message": "No entries found to migrate",
                "stats": self.stats
            }
        
        # Migrate each entry
        for entry_path in entries:
            try:
                result = await self._migrate_entry(entry_path, overwrite, dry_run)
                if result["success"]:
                    if result["action"] == "copied":
                        self.stats["copied_entries"] += 1
                    elif result["action"] == "skipped":
                        self.stats["skipped_entries"] += 1
                else:
                    self.stats["failed_entries"] += 1
                    self.stats["errors"].append({
                        "path": entry_path,
                        "error": result["error"]
                    })
            except Exception as e:
                self.stats["failed_entries"] += 1
                self.stats["errors"].append({
                    "path": entry_path,
                    "error": str(e)
                })
                logger.error(f"Error migrating entry {entry_path}: {e}")
        
        success = self.stats["failed_entries"] == 0
        action_word = "would be" if dry_run else "were"
        
        return {
            "success": success,
            "message": f"Migration {'simulation ' if dry_run else ''}completed. {self.stats['copied_entries']} entries {action_word} copied, {self.stats['skipped_entries']} skipped, {self.stats['failed_entries']} failed.",
            "stats": self.stats
        }
    
    async def _discover_entries(self) -> List[str]:
        """Discover all entries in the source backend.
        
        Returns:
            List of entry paths
        """
        entries = []
        
        # Get the tree structure from source
        tree_result = await self.source_backend.get_tree()
        if not tree_result["success"]:
            logger.error(f"Failed to get source tree: {tree_result['error']}")
            return entries
        
        # Recursively collect all entry paths
        await self._collect_entries_from_tree(tree_result["items"], "", entries)
        
        return entries
    
    async def _collect_entries_from_tree(self, tree: Dict, prefix: str, entries: List[str]):
        """Recursively collect entry paths from tree structure.
        
        Args:
            tree: Tree structure dict
            prefix: Current path prefix
            entries: List to append found entries to
        """
        for key, value in tree.items():
            if key == "...":  # Skip depth limit indicators
                continue
                
            current_path = f"{prefix}/{key}" if prefix else key
            
            if isinstance(value, dict) and value:
                # This is a directory with children
                await self._collect_entries_from_tree(value, current_path, entries)
            else:
                # This is a leaf entry - verify it exists by trying to read it
                try:
                    read_result = await self.source_backend.read_entry(current_path)
                    if read_result["success"] and read_result["type"] == "file":
                        entries.append(current_path)
                except Exception as e:
                    logger.warning(f"Could not verify entry {current_path}: {e}")
    
    async def _migrate_entry(self, entry_path: str, overwrite: bool, dry_run: bool) -> Dict[str, Any]:
        """Migrate a single entry from source to target.
        
        Args:
            entry_path: Path of the entry to migrate
            overwrite: Whether to overwrite existing entries
            dry_run: If True, only simulate the migration
            
        Returns:
            Dictionary with migration result for this entry
        """
        try:
            # Read from source
            source_result = await self.source_backend.read_entry(entry_path)
            if not source_result["success"]:
                return {
                    "success": False,
                    "action": "failed",
                    "error": f"Failed to read from source: {source_result['error']}"
                }
            
            # Check if entry exists in target
            target_result = await self.target_backend.read_entry(entry_path)
            entry_exists = target_result["success"]
            
            if entry_exists and not overwrite:
                return {
                    "success": True,
                    "action": "skipped",
                    "message": "Entry exists in target and overwrite is disabled"
                }
            
            if dry_run:
                action = "overwrite" if entry_exists else "copy"
                return {
                    "success": True,
                    "action": "copied",  # For stats counting
                    "message": f"Would {action} entry"
                }
            
            # Write to target
            write_result = await self.target_backend.write_entry(
                entry_path,
                source_result["content"],
                source_result["metadata"]
            )
            
            if write_result["success"]:
                action = "overwritten" if entry_exists else "copied"
                return {
                    "success": True,
                    "action": "copied",
                    "message": f"Entry {action} successfully"
                }
            else:
                return {
                    "success": False,
                    "action": "failed",
                    "error": f"Failed to write to target: {write_result['error']}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "action": "failed",
                "error": str(e)
            }


@tool
async def migrate_memory(
    context: AgentContext,
    source_config: Optional[str] = None,
    target_config: Optional[str] = None,
    overwrite: bool = False,
    dry_run: bool = False
) -> str:
    """Migrate memory entries between backends.
    
    Args:
        source_config: Source backend config (filesystem or http:url). If None, uses current config.
        target_config: Target backend config (filesystem or http:url). Required.
        overwrite: Whether to overwrite existing entries in target backend
        dry_run: If True, only simulate the migration without actual copying
        
    Returns:
        Migration results and statistics
    """
    if not target_config:
        return "Error: target_config is required. Use 'filesystem' or 'http:https://memory.example.com'"
    
    try:
        # Parse source config
        if source_config:
            source_backend = await _parse_backend_config(source_config)
        else:
            # Use current memory backend
            source_backend = context.memory_manager.backend
        
        # Parse target config
        target_backend = await _parse_backend_config(target_config)
        
        # Create migrator and run migration
        migrator = MemoryMigrator(source_backend, target_backend)
        result = await migrator.migrate_all(overwrite=overwrite, dry_run=dry_run)
        
        # Format results
        stats = result["stats"]
        output = [result["message"]]
        output.append("")
        output.append("Migration Statistics:")
        output.append(f"  Total entries found: {stats['total_entries']}")
        output.append(f"  Entries copied: {stats['copied_entries']}")
        output.append(f"  Entries skipped: {stats['skipped_entries']}")
        output.append(f"  Entries failed: {stats['failed_entries']}")
        
        if stats["errors"]:
            output.append("")
            output.append("Errors:")
            for error in stats["errors"][:5]:  # Show first 5 errors
                output.append(f"  {error['path']}: {error['error']}")
            if len(stats["errors"]) > 5:
                output.append(f"  ... and {len(stats['errors']) - 5} more errors")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error during migration: {str(e)}"


@tool
async def backup_memory_s3(
    context: AgentContext,
    backup_name: Optional[str] = None
) -> str:
    """Backup memory to S3.
    
    Args:
        backup_name: Optional custom backup name. If None, uses timestamp.
        
    Returns:
        Backup results and statistics
    """
    try:
        from ..s3_backup import S3BackupManager
        from ..config import get_config
        
        config = get_config()
        
        if not config.memory.s3_bucket:
            return "Error: S3 backup is not configured. Please set s3_bucket in config or environment variables."
        
        # Create S3 backup manager
        s3_manager = S3BackupManager(config.memory)
        
        # Run backup
        result = await s3_manager.backup_all(context.memory_manager.backend, backup_name)
        
        # Format results
        output = [result["message"]]
        if result["success"]:
            output.append(f"Backup key: {result['backup_key']}")
            output.append(f"Entries backed up: {result['entries_backed_up']}")
            output.append(f"Backup size: {result['backup_size_bytes']} bytes")
        
        if result.get("errors"):
            output.append("")
            output.append("Errors:")
            for error in result["errors"][:5]:  # Show first 5 errors
                output.append(f"  {error['path']}: {error['error']}")
        
        # Close S3 manager
        s3_manager.close()
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error during backup: {str(e)}"


@tool
async def restore_memory_s3(
    context: AgentContext,
    backup_key: str,
    overwrite: bool = False
) -> str:
    """Restore memory from S3 backup.
    
    Args:
        backup_key: S3 backup key to restore from
        overwrite: Whether to overwrite existing entries
        
    Returns:
        Restore results and statistics
    """
    try:
        from ..s3_backup import S3BackupManager
        from ..config import get_config
        
        config = get_config()
        
        if not config.memory.s3_bucket:
            return "Error: S3 backup is not configured. Please set s3_bucket in config or environment variables."
        
        # Create S3 backup manager
        s3_manager = S3BackupManager(config.memory)
        
        # Run restore
        result = await s3_manager.restore_backup(
            context.memory_manager.backend, 
            backup_key, 
            overwrite
        )
        
        # Format results
        output = [result["message"]]
        if result["success"]:
            output.append(f"Entries restored: {result['entries_restored']}")
            if result["entries_skipped"] > 0:
                output.append(f"Entries skipped: {result['entries_skipped']}")
            
            if result.get("backup_metadata"):
                metadata = result["backup_metadata"]
                output.append(f"Backup timestamp: {metadata.get('timestamp', 'unknown')}")
                output.append(f"Original backend: {metadata.get('backend_type', 'unknown')}")
        
        if result.get("errors"):
            output.append("")
            output.append("Errors:")
            for error in result["errors"][:5]:  # Show first 5 errors
                output.append(f"  {error['path']}: {error['error']}")
        
        # Close S3 manager
        s3_manager.close()
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error during restore: {str(e)}"


@tool
async def list_memory_backups(context: AgentContext) -> str:
    """List all available memory backups in S3.
    
    Returns:
        List of available backups with metadata
    """
    try:
        from ..s3_backup import S3BackupManager
        from ..config import get_config
        
        config = get_config()
        
        if not config.memory.s3_bucket:
            return "Error: S3 backup is not configured. Please set s3_bucket in config or environment variables."
        
        # Create S3 backup manager
        s3_manager = S3BackupManager(config.memory)
        
        # List backups
        result = await s3_manager.list_backups()
        
        # Format results
        if not result["success"]:
            return f"Error: {result['message']}"
        
        backups = result["backups"]
        if not backups:
            return "No backups found in S3."
        
        output = [f"Found {len(backups)} backups:"]
        output.append("")
        
        for backup in backups:
            output.append(f"• {backup['backup_key']}")
            output.append(f"  Timestamp: {backup['timestamp']}")
            output.append(f"  Entries: {backup['total_entries']}")
            output.append(f"  Backend: {backup['backend_type']}")
            output.append("")
        
        # Close S3 manager
        s3_manager.close()
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error listing backups: {str(e)}"


async def _parse_backend_config(config_str: str):
    """Parse backend configuration string and create backend.
    
    Args:
        config_str: Config string like 'filesystem' or 'http:https://memory.example.com'
        
    Returns:
        Memory backend instance
    """
    if config_str == "filesystem":
        # Use default filesystem backend
        return FilesystemMemoryBackend()
    elif config_str.startswith("http:"):
        # Parse HTTP backend config
        url = config_str[5:]  # Remove 'http:' prefix
        
        # Get API key from current config or environment
        current_config = get_config()
        api_key = current_config.memory.http_api_key
        
        return HTTPMemoryBackend(base_url=url, api_key=api_key)
    else:
        raise ValueError(f"Unknown backend config: {config_str}. Use 'filesystem' or 'http:URL'")


def create_migration_cli():
    """Create CLI function for memory migration."""
    
    async def migrate_memory_cli(
        source: str = "filesystem",
        target: str = None,
        overwrite: bool = False,
        dry_run: bool = False,
        source_path: str = None,
        target_url: str = None,
        api_key: str = None
    ):
        """CLI function to migrate memory between backends.
        
        Args:
            source: Source backend type ('filesystem' or 'http')
            target: Target backend type ('filesystem' or 'http')
            overwrite: Whether to overwrite existing entries
            dry_run: Only simulate the migration
            source_path: Path for source filesystem backend
            target_url: URL for target HTTP backend
            api_key: API key for HTTP backends
        """
        if not target:
            print("Error: --target is required")
            return
        
        try:
            # Create source backend
            if source == "filesystem":
                source_path_obj = Path(source_path) if source_path else None
                source_backend = FilesystemMemoryBackend(source_path_obj)
            elif source == "http":
                if not target_url:
                    print("Error: --target-url is required for HTTP source")
                    return
                source_backend = HTTPMemoryBackend(base_url=target_url, api_key=api_key)
            else:
                print(f"Error: Unknown source backend: {source}")
                return
            
            # Create target backend
            if target == "filesystem":
                target_path_obj = Path(source_path) if source_path else None
                target_backend = FilesystemMemoryBackend(target_path_obj)
            elif target == "http":
                if not target_url:
                    print("Error: --target-url is required for HTTP target")
                    return
                target_backend = HTTPMemoryBackend(base_url=target_url, api_key=api_key)
            else:
                print(f"Error: Unknown target backend: {target}")
                return
            
            # Run migration
            migrator = MemoryMigrator(source_backend, target_backend)
            result = await migrator.migrate_all(overwrite=overwrite, dry_run=dry_run)
            
            # Print results
            print(result["message"])
            stats = result["stats"]
            print(f"\nMigration Statistics:")
            print(f"  Total entries found: {stats['total_entries']}")
            print(f"  Entries copied: {stats['copied_entries']}")
            print(f"  Entries skipped: {stats['skipped_entries']}")
            print(f"  Entries failed: {stats['failed_entries']}")
            
            if stats["errors"]:
                print(f"\nErrors:")
                for error in stats["errors"]:
                    print(f"  {error['path']}: {error['error']}")
                    
        except Exception as e:
            print(f"Error during migration: {e}")
    
    return migrate_memory_cli


def migrate_memory_cli_main(args: List[str]):
    """Main entry point for memory migration CLI."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(
        prog="hdev migrate-memory",
        description="Migrate memory entries between different backends"
    )
    
    parser.add_argument(
        "--source",
        choices=["filesystem", "http"],
        default="filesystem",
        help="Source backend type (default: filesystem)"
    )
    
    parser.add_argument(
        "--target",
        choices=["filesystem", "http"],
        required=True,
        help="Target backend type"
    )
    
    parser.add_argument(
        "--source-path",
        type=Path,
        help="Path for source filesystem backend (default: ~/.hdev/memory)"
    )
    
    parser.add_argument(
        "--target-path", 
        type=Path,
        help="Path for target filesystem backend (default: ~/.hdev/memory)"
    )
    
    parser.add_argument(
        "--source-url",
        help="URL for source HTTP backend"
    )
    
    parser.add_argument(
        "--target-url",
        help="URL for target HTTP backend"
    )
    
    parser.add_argument(
        "--api-key",
        help="API key for HTTP backends (can also use HDEV_MEMORY_HTTP_API_KEY env var)"
    )
    
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing entries in target backend"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only simulate the migration without actual copying"
    )
    
    parsed_args = parser.parse_args(args)
    
    # Get API key from args or environment
    api_key = parsed_args.api_key or os.getenv("HDEV_MEMORY_HTTP_API_KEY")
    
    async def run_migration():
        try:
            # Create source backend
            if parsed_args.source == "filesystem":
                source_backend = FilesystemMemoryBackend(parsed_args.source_path)
            elif parsed_args.source == "http":
                if not parsed_args.source_url:
                    print("Error: --source-url is required for HTTP source")
                    return
                source_backend = HTTPMemoryBackend(base_url=parsed_args.source_url, api_key=api_key)
            
            # Create target backend
            if parsed_args.target == "filesystem":
                target_backend = FilesystemMemoryBackend(parsed_args.target_path)
            elif parsed_args.target == "http":
                if not parsed_args.target_url:
                    print("Error: --target-url is required for HTTP target")
                    return
                target_backend = HTTPMemoryBackend(base_url=parsed_args.target_url, api_key=api_key)
            
            print(f"Migrating memory from {parsed_args.source} to {parsed_args.target}")
            if parsed_args.dry_run:
                print("DRY RUN - No actual changes will be made")
            
            # Run migration
            migrator = MemoryMigrator(source_backend, target_backend)
            result = await migrator.migrate_all(
                overwrite=parsed_args.overwrite, 
                dry_run=parsed_args.dry_run
            )
            
            # Print results
            print(result["message"])
            stats = result["stats"]
            print(f"\nMigration Statistics:")
            print(f"  Total entries found: {stats['total_entries']}")
            print(f"  Entries copied: {stats['copied_entries']}")
            print(f"  Entries skipped: {stats['skipped_entries']}")
            print(f"  Entries failed: {stats['failed_entries']}")
            
            if stats["errors"]:
                print(f"\nErrors:")
                for error in stats["errors"]:
                    print(f"  {error['path']}: {error['error']}")
            
            # Close HTTP backends if used
            if hasattr(source_backend, 'close'):
                await source_backend.close()
            if hasattr(target_backend, 'close'):
                await target_backend.close()
                    
        except Exception as e:
            print(f"Error during migration: {e}")
            import traceback
            traceback.print_exc()
    
    # Run the async migration
    asyncio.run(run_migration())


def backup_memory_cli_main(args: List[str]):
    """Main entry point for memory backup CLI."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(
        prog="hdev backup-memory",
        description="Backup memory to S3"
    )
    
    parser.add_argument(
        "--backup-name",
        help="Custom backup name (default: timestamp-based)"
    )
    
    parser.add_argument(
        "--s3-bucket",
        help="S3 bucket for backup (can also use HDEV_S3_BUCKET env var)"
    )
    
    parser.add_argument(
        "--s3-region",
        default="us-east-1",
        help="S3 region (default: us-east-1)"
    )
    
    parser.add_argument(
        "--s3-endpoint-url",
        help="S3 endpoint URL for S3-compatible services"
    )
    
    parser.add_argument(
        "--memory-backend",
        choices=["filesystem", "http"],
        default="filesystem",
        help="Memory backend to backup from (default: filesystem)"
    )
    
    parser.add_argument(
        "--memory-path",
        type=Path,
        help="Path for filesystem backend (default: ~/.hdev/memory)"
    )
    
    parser.add_argument(
        "--memory-url",
        help="URL for HTTP memory backend"
    )
    
    parser.add_argument(
        "--api-key",
        help="API key for HTTP backends (can also use HDEV_MEMORY_HTTP_API_KEY env var)"
    )
    
    parsed_args = parser.parse_args(args)
    
    async def run_backup():
        try:
            from ..s3_backup import S3BackupManager
            from ..config import MemoryConfig
            
            # Create memory config for S3
            s3_config = MemoryConfig(
                s3_bucket=parsed_args.s3_bucket or os.getenv("HDEV_S3_BUCKET"),
                s3_region=parsed_args.s3_region,
                s3_access_key_id=os.getenv("HDEV_S3_ACCESS_KEY_ID"),
                s3_secret_access_key=os.getenv("HDEV_S3_SECRET_ACCESS_KEY"),
                s3_endpoint_url=parsed_args.s3_endpoint_url or os.getenv("HDEV_S3_ENDPOINT_URL"),
            )
            
            if not s3_config.s3_bucket:
                print("Error: S3 bucket must be specified via --s3-bucket or HDEV_S3_BUCKET env var")
                return
            
            # Create S3 backup manager
            s3_manager = S3BackupManager(s3_config)
            
            # Create memory backend
            if parsed_args.memory_backend == "filesystem":
                from ..memory_backends.filesystem import FilesystemMemoryBackend
                backend = FilesystemMemoryBackend(parsed_args.memory_path)
            elif parsed_args.memory_backend == "http":
                if not parsed_args.memory_url:
                    print("Error: --memory-url is required for HTTP backend")
                    return
                from ..memory_backends.http import HTTPMemoryBackend
                api_key = parsed_args.api_key or os.getenv("HDEV_MEMORY_HTTP_API_KEY")
                backend = HTTPMemoryBackend(base_url=parsed_args.memory_url, api_key=api_key)
            
            print(f"Starting backup to S3 bucket '{s3_config.s3_bucket}'...")
            if parsed_args.backup_name:
                print(f"Backup name: {parsed_args.backup_name}")
            
            # Run backup
            result = await s3_manager.backup_all(backend, parsed_args.backup_name)
            
            # Print results
            print(result["message"])
            if result["success"]:
                print(f"Backup key: {result['backup_key']}")
                print(f"Entries backed up: {result['entries_backed_up']}")
                print(f"Backup size: {result['backup_size_bytes']} bytes")
            
            if result.get("errors"):
                print("\nErrors:")
                for error in result["errors"]:
                    print(f"  {error['path']}: {error['error']}")
            
            # Close backends
            if hasattr(backend, 'close'):
                await backend.close()
            s3_manager.close()
                    
        except Exception as e:
            print(f"Error during backup: {e}")
            import traceback
            traceback.print_exc()
    
    # Run the async backup
    asyncio.run(run_backup())


def restore_memory_cli_main(args: List[str]):
    """Main entry point for memory restore CLI."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(
        prog="hdev restore-memory",
        description="Restore memory from S3 backup"
    )
    
    parser.add_argument(
        "backup_key",
        help="Backup key to restore from"
    )
    
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing entries in target backend"
    )
    
    parser.add_argument(
        "--s3-bucket",
        help="S3 bucket for backup (can also use HDEV_S3_BUCKET env var)"
    )
    
    parser.add_argument(
        "--s3-region",
        default="us-east-1",
        help="S3 region (default: us-east-1)"
    )
    
    parser.add_argument(
        "--s3-endpoint-url",
        help="S3 endpoint URL for S3-compatible services"
    )
    
    parser.add_argument(
        "--memory-backend",
        choices=["filesystem", "http"],
        default="filesystem",
        help="Memory backend to restore to (default: filesystem)"
    )
    
    parser.add_argument(
        "--memory-path",
        type=Path,
        help="Path for filesystem backend (default: ~/.hdev/memory)"
    )
    
    parser.add_argument(
        "--memory-url",
        help="URL for HTTP memory backend"
    )
    
    parser.add_argument(
        "--api-key",
        help="API key for HTTP backends (can also use HDEV_MEMORY_HTTP_API_KEY env var)"
    )
    
    parsed_args = parser.parse_args(args)
    
    async def run_restore():
        try:
            from ..s3_backup import S3BackupManager
            from ..config import MemoryConfig
            
            # Create memory config for S3
            s3_config = MemoryConfig(
                s3_bucket=parsed_args.s3_bucket or os.getenv("HDEV_S3_BUCKET"),
                s3_region=parsed_args.s3_region,
                s3_access_key_id=os.getenv("HDEV_S3_ACCESS_KEY_ID"),
                s3_secret_access_key=os.getenv("HDEV_S3_SECRET_ACCESS_KEY"),
                s3_endpoint_url=parsed_args.s3_endpoint_url or os.getenv("HDEV_S3_ENDPOINT_URL"),
            )
            
            if not s3_config.s3_bucket:
                print("Error: S3 bucket must be specified via --s3-bucket or HDEV_S3_BUCKET env var")
                return
            
            # Create S3 backup manager
            s3_manager = S3BackupManager(s3_config)
            
            # Create memory backend
            if parsed_args.memory_backend == "filesystem":
                from ..memory_backends.filesystem import FilesystemMemoryBackend
                backend = FilesystemMemoryBackend(parsed_args.memory_path)
            elif parsed_args.memory_backend == "http":
                if not parsed_args.memory_url:
                    print("Error: --memory-url is required for HTTP backend")
                    return
                from ..memory_backends.http import HTTPMemoryBackend
                api_key = parsed_args.api_key or os.getenv("HDEV_MEMORY_HTTP_API_KEY")
                backend = HTTPMemoryBackend(base_url=parsed_args.memory_url, api_key=api_key)
            
            print(f"Starting restore from backup '{parsed_args.backup_key}'...")
            if parsed_args.overwrite:
                print("Overwrite mode enabled - existing entries will be replaced")
            
            # Run restore
            result = await s3_manager.restore_backup(
                backend, 
                parsed_args.backup_key, 
                parsed_args.overwrite
            )
            
            # Print results
            print(result["message"])
            if result["success"]:
                print(f"Entries restored: {result['entries_restored']}")
                if result["entries_skipped"] > 0:
                    print(f"Entries skipped: {result['entries_skipped']}")
                
                if result.get("backup_metadata"):
                    metadata = result["backup_metadata"]
                    print(f"Backup timestamp: {metadata.get('timestamp', 'unknown')}")
                    print(f"Original backend: {metadata.get('backend_type', 'unknown')}")
            
            if result.get("errors"):
                print("\nErrors:")
                for error in result["errors"]:
                    print(f"  {error['path']}: {error['error']}")
            
            # Close backends
            if hasattr(backend, 'close'):
                await backend.close()
            s3_manager.close()
                    
        except Exception as e:
            print(f"Error during restore: {e}")
            import traceback
            traceback.print_exc()
    
    # Run the async restore
    asyncio.run(run_restore())