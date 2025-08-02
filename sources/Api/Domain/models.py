"""
Domain Models

Core business entities and value objects for the data processing system.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class DataType(Enum):
    """Supported data types."""
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    UNKNOWN = "unknown"


@dataclass
class ColumnMetadata:
    """Metadata for a single column."""
    name: str
    position: int
    data_type: DataType
    subtype: str
    nullable: bool
    total_count: int
    null_count: int
    null_percentage: float
    unique_count: int
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    max_length: Optional[int] = None
    sample_values: List[Any] = None

    def __post_init__(self):
        if self.sample_values is None:
            self.sample_values = []


@dataclass
class SchemaSummary:
    """Summary of data schema."""
    numeric_columns_count: int
    categorical_columns_count: int
    datetime_columns_count: int
    boolean_columns_count: int
    numeric_columns: List[str]
    categorical_columns: List[str]
    datetime_columns: List[str]
    boolean_columns: List[str]


@dataclass
class FileInfo:
    """Information about the source file."""
    file_name: str
    file_path: str
    file_size_bytes: int
    file_size_mb: float
    last_modified: datetime
    total_rows: int
    total_columns: int
    has_duplicates: bool
    duplicate_rows_count: int
    extraction_timestamp: datetime


@dataclass
class DataRow:
    """A single row of data."""
    row_id: int
    data: Dict[str, Any]
    file_info: FileInfo
    inserted_at: datetime


@dataclass
class FileMetadata:
    """Complete metadata for a file."""
    file_info: FileInfo
    columns: Dict[str, ColumnMetadata]
    schema_summary: SchemaSummary


@dataclass
class ProcessingResult:
    """Result of processing a file."""
    success: bool
    file_path: str
    collection_name: str
    rows_processed: int
    rows_inserted: int
    metadata: FileMetadata
    error: Optional[str] = None


@dataclass
class CollectionInfo:
    """Information about a MongoDB collection."""
    collection_name: str
    document_count: int
    storage_size: int
    index_size: int
    metadata: Optional[FileMetadata] = None
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None


@dataclass
class ProcessingStatus:
    """Status of data processing operations."""
    total_collections: int
    collections: List[CollectionInfo]
    success: bool
    error: Optional[str] = None 