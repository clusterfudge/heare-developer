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


class BackupResponse(BaseModel):
    """Response model for backup operations."""
    success: bool
    message: str
    backup_key: Optional[str] = None
    error: Optional[str] = None


class RestoreResponse(BaseModel):
    """Response model for restore operations."""
    success: bool
    message: str
    restored_entries: int = 0
    error: Optional[str] = None