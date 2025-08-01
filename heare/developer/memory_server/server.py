"""FastAPI-based memory server implementation."""

import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from ..memory_backends.base import MemoryBackend
from ..memory_backends.filesystem import FilesystemMemoryBackend
from ..config import MemoryConfig
from ..web.app import MemoryWebApp
from .models import (
    MemoryTreeResponse,
    MemoryEntryResponse,
    WriteEntryRequest,
    WriteEntryResponse,
    DeleteEntryResponse,
    SearchResponse,
    SearchResult,
    HealthResponse,
    BackupResponse,
    RestoreResponse,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer(auto_error=False)


class MemoryServer:
    """Memory server with FastAPI backend."""
    
    def __init__(
        self,
        backend: MemoryBackend,
        api_key: Optional[str] = None,
        enable_web_ui: bool = True,
    ):
        """Initialize the memory server.
        
        Args:
            backend: Memory backend to use
            api_key: Optional API key for authentication
            enable_web_ui: Whether to enable the web UI
        """
        self.backend = backend
        self.api_key = api_key
        self.enable_web_ui = enable_web_ui
        self.app = FastAPI(
            title="Hdev Memory Server",
            description="Remote memory storage API for hdev",
            version="1.0.0",
        )
        
        self._setup_middleware()
        self._setup_routes()
        
        if enable_web_ui:
            self._setup_web_ui()
    
    def _setup_middleware(self):
        """Set up FastAPI middleware."""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, specify actual origins
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _verify_api_key(
        self, credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
    ):
        """Verify API key if configured."""
        if self.api_key is None:
            return True  # No authentication required
        
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if credentials.credentials != self.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return True
    
    def _setup_routes(self):
        """Set up API routes."""
        
        @self.app.get("/api/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint."""
            health_result = await self.backend.health_check()
            return HealthResponse(
                healthy=health_result["healthy"],
                message=health_result["message"],
                details=health_result["details"],
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        @self.app.get("/api/memory/tree", response_model=MemoryTreeResponse)
        async def get_memory_tree(
            prefix: Optional[str] = None,
            depth: int = -1,
            _: bool = Depends(self._verify_api_key)
        ):
            """Get memory tree structure."""
            try:
                prefix_path = Path(prefix) if prefix else None
                result = await self.backend.get_tree(prefix_path, depth)
                return MemoryTreeResponse(**result)
            except Exception as e:
                logger.error(f"Error getting memory tree: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/memory/entry/{path:path}", response_model=MemoryEntryResponse)
        async def read_memory_entry(
            path: str,
            _: bool = Depends(self._verify_api_key)
        ):
            """Read a memory entry."""
            try:
                result = await self.backend.read_entry(path)
                return MemoryEntryResponse(**result)
            except Exception as e:
                logger.error(f"Error reading memory entry {path}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/api/memory/entry/{path:path}", response_model=WriteEntryResponse)
        async def write_memory_entry(
            path: str,
            request: WriteEntryRequest,
            _: bool = Depends(self._verify_api_key)
        ):
            """Write a memory entry."""
            try:
                result = await self.backend.write_entry(
                    path, request.content, request.metadata
                )
                return WriteEntryResponse(**result)
            except Exception as e:
                logger.error(f"Error writing memory entry {path}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/memory/entry/{path:path}", response_model=DeleteEntryResponse)
        async def delete_memory_entry(
            path: str,
            _: bool = Depends(self._verify_api_key)
        ):
            """Delete a memory entry."""
            try:
                result = await self.backend.delete_entry(path)
                return DeleteEntryResponse(**result)
            except Exception as e:
                logger.error(f"Error deleting memory entry {path}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/memory/search", response_model=SearchResponse)
        async def search_memory(
            q: str,
            prefix: Optional[str] = None,
            _: bool = Depends(self._verify_api_key)
        ):
            """Search memory entries."""
            try:
                results = await self.backend.search(q, prefix)
                search_results = [
                    SearchResult(
                        path=result["path"],
                        snippet=result["snippet"],
                        score=result["score"]
                    )
                    for result in results
                ]
                return SearchResponse(query=q, results=search_results)
            except Exception as e:
                logger.error(f"Error searching memory: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Placeholder endpoints for S3 backup/restore (to be implemented in Phase 4)
        @self.app.post("/api/memory/backup", response_model=BackupResponse)
        async def backup_memory(
            _: bool = Depends(self._verify_api_key)
        ):
            """Trigger memory backup to S3."""
            # TODO: Implement in Phase 4
            return BackupResponse(
                success=False,
                message="Backup functionality not yet implemented",
                error="Feature coming in Phase 4"
            )
        
        @self.app.post("/api/memory/restore", response_model=RestoreResponse)
        async def restore_memory(
            backup_key: Optional[str] = None,
            _: bool = Depends(self._verify_api_key)
        ):
            """Restore memory from S3 backup."""
            # TODO: Implement in Phase 4
            return RestoreResponse(
                success=False,
                message="Restore functionality not yet implemented",
                error="Feature coming in Phase 4"
            )
    
    def _setup_web_ui(self):
        """Set up the web UI routes."""
        # We'll integrate with the existing Flask web app later
        # For now, just add a placeholder
        @self.app.get("/", response_class=HTMLResponse)
        async def web_ui_root():
            """Web UI root - placeholder for now."""
            return """
            <html>
                <head><title>Hdev Memory Server</title></head>
                <body>
                    <h1>Hdev Memory Server</h1>
                    <p>Web UI integration coming soon!</p>
                    <p>API Documentation: <a href="/docs">/docs</a></p>
                    <p>Health Check: <a href="/api/health">/api/health</a></p>
                </body>
            </html>
            """


def create_app(
    backend: Optional[MemoryBackend] = None,
    api_key: Optional[str] = None,
    storage_path: Optional[Path] = None,
    enable_web_ui: bool = True,
) -> FastAPI:
    """Create FastAPI app with memory server.
    
    Args:
        backend: Memory backend to use. If None, uses FilesystemMemoryBackend
        api_key: Optional API key for authentication
        storage_path: Path for filesystem backend storage
        enable_web_ui: Whether to enable web UI
        
    Returns:
        Configured FastAPI application
    """
    if backend is None:
        # Use filesystem backend as default
        base_dir = storage_path or Path.cwd() / "memory"
        backend = FilesystemMemoryBackend(base_dir)
    
    server = MemoryServer(backend, api_key, enable_web_ui)
    return server.app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    backend: Optional[MemoryBackend] = None,
    api_key: Optional[str] = None,
    storage_path: Optional[Path] = None,
    enable_web_ui: bool = True,
    log_level: str = "info",
):
    """Run the memory server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        backend: Memory backend to use
        api_key: Optional API key for authentication
        storage_path: Path for filesystem backend storage
        enable_web_ui: Whether to enable web UI
        log_level: Logging level
    """
    app = create_app(backend, api_key, storage_path, enable_web_ui)
    
    logger.info(f"Starting memory server on {host}:{port}")
    if api_key:
        logger.info("API key authentication enabled")
    else:
        logger.warning("No API key configured - server is open!")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=True,
    )