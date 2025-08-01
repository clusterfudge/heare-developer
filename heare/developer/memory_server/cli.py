"""CLI for the memory server."""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from ..config import get_config
from ..memory_backends.factory import create_memory_backend
from .server import run_server


def memory_server_main(args: list[str]):
    """Main entry point for memory server CLI."""
    parser = argparse.ArgumentParser(
        prog="hdev memory-server",
        description="Run the hdev memory server"
    )
    
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: 8080, or PORT env var)"
    )
    
    parser.add_argument(
        "--storage-path",
        type=Path,
        help="Path to store memory files (for filesystem backend)"
    )
    
    parser.add_argument(
        "--api-key",
        help="API key for authentication (optional)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Log level (default: info)"
    )
    
    parser.add_argument(
        "--no-web-ui",
        action="store_true",
        help="Disable web UI"
    )
    
    parser.add_argument(
        "--backend",
        choices=["filesystem", "http"],
        help="Memory backend to use (overrides config)"
    )
    
    parsed_args = parser.parse_args(args)
    
    # Determine port
    port = parsed_args.port
    if port is None:
        port = int(os.getenv("PORT", "8080"))
    
    # Get API key from environment if not provided
    api_key = parsed_args.api_key or os.getenv("HDEV_MEMORY_API_KEY")
    
    # Load configuration
    config = get_config()
    
    # Override backend if specified
    if parsed_args.backend:
        config.memory.backend = parsed_args.backend
    
    # Override storage path if specified
    if parsed_args.storage_path:
        config.memory.filesystem_path = parsed_args.storage_path
    
    # Create backend
    try:
        backend = create_memory_backend(config.memory)
    except ValueError as e:
        print(f"Error creating memory backend: {e}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Starting memory server with {config.memory.backend} backend...")
    if api_key:
        print("Authentication: API key required")
    else:
        print("Authentication: None (open server)")
    
    # Run server
    try:
        run_server(
            host=parsed_args.host,
            port=port,
            backend=backend,
            api_key=api_key,
            enable_web_ui=not parsed_args.no_web_ui,
            log_level=parsed_args.log_level,
        )
    except KeyboardInterrupt:
        print("\nShutting down memory server...")
    except Exception as e:
        print(f"Error running memory server: {e}", file=sys.stderr)
        sys.exit(1)