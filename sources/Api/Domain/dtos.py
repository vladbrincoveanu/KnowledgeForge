"""
Data Transfer Objects (DTOs)

Objects used for data transfer between layers, especially for API communication.
Using Pydantic for validation, serialization, and automatic type conversion.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from pydantic import field_validator
from pathlib import Path


class ProcessFileRequest(BaseModel):
    """Request to process a file."""
    file_path: str = Field(..., description="Path to the file to process")
    collection_name: Optional[str] = Field(None, description="Custom collection name for MongoDB")
    sheet_name: Optional[str] = Field(None, description="Sheet name for Excel files")
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v):
        """Validate that the file path exists and is a file."""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"File does not exist: {v}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {v}")
        return str(path.absolute())
    
    @field_validator('collection_name')
    @classmethod
    def validate_collection_name(cls, v):
        """Validate MongoDB collection name format."""
        if v is not None:
            if not v.replace('_', '').replace('-', '').isalnum():
                raise ValueError("Collection name must contain only alphanumeric characters, underscores, and hyphens")
        return v


class ProcessDirectoryRequest(BaseModel):
    """Request to process a directory."""
    directory_path: str = Field(..., description="Path to the directory to process")
    file_pattern: str = Field("*", description="File pattern to match (glob pattern)")
    
    @field_validator('directory_path')
    @classmethod
    def validate_directory_path(cls, v):
        """Validate that the directory path exists and is a directory."""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Directory does not exist: {v}")
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {v}")
        return str(path.absolute())


class QueryRequest(BaseModel):
    """Request to query data."""
    collection_name: str = Field(..., description="Name of the collection to query")
    query: Optional[Dict[str, Any]] = Field(None, description="MongoDB query filter")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of documents to return")
    skip: int = Field(0, ge=0, description="Number of documents to skip")
    
    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v):
        """Ensure limit is within reasonable bounds."""
        if v < 1:
            raise ValueError("Limit must be at least 1")
        if v > 1000:
            raise ValueError("Limit cannot exceed 1000")
        return v


class ProcessingResponse(BaseModel):
    """Response from processing operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message about the operation")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data from the operation")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class QueryResponse(BaseModel):
    """Response from query operations."""
    success: bool = Field(..., description="Whether the query was successful")
    data: List[Dict[str, Any]] = Field(..., description="Query results")
    total_count: int = Field(..., ge=0, description="Total number of documents returned")
    limit: int = Field(..., ge=1, description="Limit used in the query")
    skip: int = Field(..., ge=0, description="Skip value used in the query")
    error: Optional[str] = Field(None, description="Error message if query failed")


class CollectionInfoResponse(BaseModel):
    """Response with collection information."""
    success: bool = Field(..., description="Whether the operation was successful")
    collection_info: Optional[Dict[str, Any]] = Field(None, description="Collection metadata")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class StatusResponse(BaseModel):
    """Response with system status."""
    success: bool = Field(..., description="Whether the status retrieval was successful")
    total_collections: int = Field(..., ge=0, description="Total number of collections")
    collections: List[Dict[str, Any]] = Field(..., description="List of collection information")
    error: Optional[str] = Field(None, description="Error message if status retrieval failed")


class MetadataResponse(BaseModel):
    """Response with metadata information."""
    success: bool = Field(..., description="Whether the metadata retrieval was successful")
    metadata: Optional[Dict[str, Any]] = Field(None, description="File or collection metadata")
    error: Optional[str] = Field(None, description="Error message if metadata retrieval failed") 