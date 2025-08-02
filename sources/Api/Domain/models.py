"""
Domain Models

Core business entities and value objects for the data processing system.
Using Pydantic for validation, serialization, and automatic type conversion.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from pathlib import Path


class DataType(Enum):
    """Supported data types."""
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    UNKNOWN = "unknown"


class ColumnMetadata(BaseModel):
    """Metadata for a single column."""
    name: str = Field(..., description="Column name")
    position: int = Field(..., ge=0, description="Column position (0-indexed)")
    data_type: DataType = Field(..., description="Detected data type")
    subtype: str = Field(..., description="Specific subtype (e.g., int64, float64)")
    nullable: bool = Field(..., description="Whether the column contains null values")
    total_count: int = Field(..., ge=0, description="Total number of values")
    null_count: int = Field(..., ge=0, description="Number of null values")
    null_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of null values")
    unique_count: int = Field(..., ge=0, description="Number of unique values")
    min_value: Optional[Any] = Field(None, description="Minimum value in the column")
    max_value: Optional[Any] = Field(None, description="Maximum value in the column")
    max_length: Optional[int] = Field(None, ge=0, description="Maximum string length")
    sample_values: List[Any] = Field(default_factory=list, description="Sample values from the column")
    
    @field_validator('null_percentage')
    @classmethod
    def validate_null_percentage(cls, v):
        """Ensure null percentage is within valid range."""
        if v < 0 or v > 100:
            raise ValueError("Null percentage must be between 0 and 100")
        return v
    
    @field_validator('total_count')
    @classmethod
    def validate_total_count(cls, v, info):
        """Ensure total count is greater than or equal to null count."""
        if 'null_count' in info.data and v < info.data['null_count']:
            raise ValueError("Total count cannot be less than null count")
        return v


class SchemaSummary(BaseModel):
    """Summary of data schema."""
    numeric_columns_count: int = Field(..., ge=0, description="Number of numeric columns")
    categorical_columns_count: int = Field(..., ge=0, description="Number of categorical columns")
    datetime_columns_count: int = Field(..., ge=0, description="Number of datetime columns")
    boolean_columns_count: int = Field(..., ge=0, description="Number of boolean columns")
    numeric_columns: List[str] = Field(default_factory=list, description="List of numeric column names")
    categorical_columns: List[str] = Field(default_factory=list, description="List of categorical column names")
    datetime_columns: List[str] = Field(default_factory=list, description="List of datetime column names")
    boolean_columns: List[str] = Field(default_factory=list, description="List of boolean column names")


class FileInfo(BaseModel):
    """Information about the source file."""
    file_name: str = Field(..., description="Name of the file")
    file_path: str = Field(..., description="Full path to the file")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    file_size_mb: float = Field(..., ge=0.0, description="File size in megabytes")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    total_rows: int = Field(..., ge=0, description="Total number of rows")
    total_columns: int = Field(..., ge=0, description="Total number of columns")
    has_duplicates: bool = Field(..., description="Whether the file contains duplicate rows")
    duplicate_rows_count: int = Field(..., ge=0, description="Number of duplicate rows")
    extraction_timestamp: datetime = Field(..., description="When metadata was extracted")
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v):
        """Validate that the file path is absolute."""
        path = Path(v)
        return str(path.absolute())
    
    @field_validator('file_size_mb')
    @classmethod
    def validate_file_size_mb(cls, v):
        """Ensure file size is reasonable."""
        if v > 1000:  # 1GB limit
            raise ValueError("File size cannot exceed 1GB")
        return v


class DataRow(BaseModel):
    """A single row of data."""
    row_id: int = Field(..., ge=0, description="Unique row identifier")
    data: Dict[str, Any] = Field(..., description="Row data as key-value pairs")
    file_info: FileInfo = Field(..., description="Reference to file information")
    inserted_at: datetime = Field(..., description="When the row was inserted")


class FileMetadata(BaseModel):
    """Complete metadata for a file."""
    file_info: FileInfo = Field(..., description="File information")
    columns: Dict[str, ColumnMetadata] = Field(..., description="Column metadata by column name")
    schema_summary: SchemaSummary = Field(..., description="Schema summary")


class ProcessingResult(BaseModel):
    """Result of processing a file."""
    success: bool = Field(..., description="Whether processing was successful")
    file_path: str = Field(..., description="Path to the processed file")
    collection_name: str = Field(..., description="MongoDB collection name")
    rows_processed: int = Field(..., ge=0, description="Number of rows processed")
    rows_inserted: int = Field(..., ge=0, description="Number of rows inserted")
    metadata: FileMetadata = Field(..., description="File metadata")
    error: Optional[str] = Field(None, description="Error message if processing failed")
    
    @field_validator('rows_inserted')
    @classmethod
    def validate_rows_inserted(cls, v, info):
        """Ensure rows inserted doesn't exceed rows processed."""
        if 'rows_processed' in info.data and v > info.data['rows_processed']:
            raise ValueError("Rows inserted cannot exceed rows processed")
        return v


class CollectionInfo(BaseModel):
    """Information about a MongoDB collection."""
    collection_name: str = Field(..., description="Name of the collection")
    document_count: int = Field(..., ge=0, description="Number of documents in the collection")
    storage_size: int = Field(..., ge=0, description="Storage size in bytes")
    index_size: int = Field(..., ge=0, description="Index size in bytes")
    metadata: Optional[FileMetadata] = Field(None, description="File metadata if available")
    created_at: Optional[datetime] = Field(None, description="When the collection was created")
    last_updated: Optional[datetime] = Field(None, description="When the collection was last updated")


class ProcessingStatus(BaseModel):
    """Status of data processing operations."""
    total_collections: int = Field(..., ge=0, description="Total number of collections")
    collections: List[CollectionInfo] = Field(default_factory=list, description="List of collection information")
    success: bool = Field(..., description="Whether the status retrieval was successful")
    error: Optional[str] = Field(None, description="Error message if status retrieval failed") 