"""Pydantic models for memory server API."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class MemoryTreeResponse(BaseModel):
    """Response model for memory tree endpoint."""
    type: str = "tree"
    path: str
    items: Dict[str, Any]
    success: bool
    error: Optional[str] = None


class MemoryEntryResponse(BaseModel):
    """Response model for memory entry endpoint."""
    type: str
    path: str
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    items: Optional[List[Dict[str, Any]]] = None
    success: bool
    error: Optional[str] = None


class WriteEntryRequest(BaseModel):
    """Request model for writing memory entries."""
    content: str = Field(..., description="Content to write")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class WriteEntryResponse(BaseModel):
    """Response model for write operations."""
    path: str
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


class DeleteEntryResponse(BaseModel):
    """Response model for delete operations."""
    path: str
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


class SearchResult(BaseModel):
    """Individual search result."""
    path: str
    snippet: str
    score: float


class SearchResponse(BaseModel):
    """Response model for search endpoint."""
    query: str
    results: List[SearchResult]
    success: bool = True
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check."""
    healthy: bool
    message: str
    details: Dict[str, Any]
    timestamp: str


class BackupRequest(BaseModel):
    """Request model for backup operations."""
    backup_name: Optional[str] = Field(None, description="Optional custom backup name")


class BackupResponse(BaseModel):
    """Response model for backup operations."""
    success: bool
    message: str
    backup_key: Optional[str] = None
    entries_backed_up: int = 0
    backup_size_bytes: int = 0
    errors: Optional[List[Dict[str, str]]] = None
    error: Optional[str] = None


class RestoreRequest(BaseModel):
    """Request model for restore operations."""
    backup_key: str = Field(..., description="Backup key to restore from")
    overwrite: bool = Field(False, description="Whether to overwrite existing entries")


class RestoreResponse(BaseModel):
    """Response model for restore operations."""
    success: bool
    message: str
    backup_key: Optional[str] = None
    entries_restored: int = 0
    entries_skipped: int = 0
    backup_metadata: Optional[Dict[str, Any]] = None
    errors: Optional[List[Dict[str, str]]] = None
    error: Optional[str] = None


class BackupInfo(BaseModel):
    """Information about a backup."""
    backup_key: str
    timestamp: str
    total_entries: int
    backend_type: str


class ListBackupsResponse(BaseModel):
    """Response model for listing backups."""
    success: bool
    message: str
    backups: List[BackupInfo] = []
    error: Optional[str] = None


class DeleteBackupRequest(BaseModel):
    """Request model for deleting backups."""
    backup_key: str = Field(..., description="Backup key to delete")


class DeleteBackupResponse(BaseModel):
    """Response model for deleting backups."""
    success: bool
    message: str
    backup_key: Optional[str] = None
    objects_deleted: int = 0
    error: Optional[str] = None