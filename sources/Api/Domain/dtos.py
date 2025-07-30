"""
Data Transfer Objects (DTOs)

Objects used for data transfer between layers, especially for API communication.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class ProcessFileRequest:
    """Request to process a file."""
    file_path: str
    collection_name: Optional[str] = None
    sheet_name: Optional[str] = None


@dataclass
class ProcessDirectoryRequest:
    """Request to process a directory."""
    directory_path: str
    file_pattern: str = "*"


@dataclass
class QueryRequest:
    """Request to query data."""
    collection_name: str
    query: Optional[Dict[str, Any]] = None
    limit: int = 100
    skip: int = 0


@dataclass
class ProcessingResponse:
    """Response from processing operations."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class QueryResponse:
    """Response from query operations."""
    success: bool
    data: List[Dict[str, Any]]
    total_count: int
    limit: int
    skip: int
    error: Optional[str] = None


@dataclass
class CollectionInfoResponse:
    """Response with collection information."""
    success: bool
    collection_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class StatusResponse:
    """Response with system status."""
    success: bool
    total_collections: int
    collections: List[Dict[str, Any]]
    error: Optional[str] = None


@dataclass
class MetadataResponse:
    """Response with metadata information."""
    success: bool
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None 