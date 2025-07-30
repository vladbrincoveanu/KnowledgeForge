"""
Unit Tests for Domain Models

Tests for domain entities and value objects.
"""

import pytest
from datetime import datetime
from typing import Dict, List, Any

from sources.Api.Domain.models import (
    DataType, ColumnMetadata, SchemaSummary, FileInfo, 
    FileMetadata, DataRow, ProcessingResult, CollectionInfo, ProcessingStatus
)


class TestDataType:
    """Test DataType enum."""
    
    def test_data_type_values(self):
        """Test that DataType enum has correct values."""
        assert DataType.INTEGER.value == "integer"
        assert DataType.FLOAT.value == "float"
        assert DataType.STRING.value == "string"
        assert DataType.BOOLEAN.value == "boolean"
        assert DataType.DATETIME.value == "datetime"
        assert DataType.UNKNOWN.value == "unknown"


class TestColumnMetadata:
    """Test ColumnMetadata dataclass."""
    
    def test_column_metadata_creation(self):
        """Test creating a ColumnMetadata instance."""
        column = ColumnMetadata(
            name="test_column",
            position=0,
            data_type=DataType.STRING,
            subtype="object",
            nullable=True,
            total_count=100,
            null_count=5,
            null_percentage=5.0,
            unique_count=95,
            max_length=50,
            sample_values=["value1", "value2"]
        )
        
        assert column.name == "test_column"
        assert column.position == 0
        assert column.data_type == DataType.STRING
        assert column.nullable is True
        assert column.total_count == 100
        assert column.null_count == 5
        assert column.null_percentage == 5.0
        assert column.unique_count == 95
        assert column.max_length == 50
        assert column.sample_values == ["value1", "value2"]
    
    def test_column_metadata_default_sample_values(self):
        """Test that sample_values defaults to empty list."""
        column = ColumnMetadata(
            name="test_column",
            position=0,
            data_type=DataType.INTEGER,
            subtype="int64",
            nullable=False,
            total_count=100,
            null_count=0,
            null_percentage=0.0,
            unique_count=100
        )
        
        assert column.sample_values == []


class TestSchemaSummary:
    """Test SchemaSummary dataclass."""
    
    def test_schema_summary_creation(self):
        """Test creating a SchemaSummary instance."""
        schema = SchemaSummary(
            numeric_columns_count=2,
            categorical_columns_count=3,
            datetime_columns_count=1,
            boolean_columns_count=1,
            numeric_columns=["age", "salary"],
            categorical_columns=["name", "city", "department"],
            datetime_columns=["birth_date"],
            boolean_columns=["is_active"]
        )
        
        assert schema.numeric_columns_count == 2
        assert schema.categorical_columns_count == 3
        assert schema.datetime_columns_count == 1
        assert schema.boolean_columns_count == 1
        assert schema.numeric_columns == ["age", "salary"]
        assert schema.categorical_columns == ["name", "city", "department"]
        assert schema.datetime_columns == ["birth_date"]
        assert schema.boolean_columns == ["is_active"]


class TestFileInfo:
    """Test FileInfo dataclass."""
    
    def test_file_info_creation(self):
        """Test creating a FileInfo instance."""
        now = datetime.now()
        file_info = FileInfo(
            file_name="test.csv",
            file_path="/path/to/test.csv",
            file_size_bytes=1024,
            file_size_mb=1.0,
            last_modified=now,
            total_rows=100,
            total_columns=5,
            has_duplicates=False,
            duplicate_rows_count=0,
            extraction_timestamp=now
        )
        
        assert file_info.file_name == "test.csv"
        assert file_info.file_path == "/path/to/test.csv"
        assert file_info.file_size_bytes == 1024
        assert file_info.file_size_mb == 1.0
        assert file_info.last_modified == now
        assert file_info.total_rows == 100
        assert file_info.total_columns == 5
        assert file_info.has_duplicates is False
        assert file_info.duplicate_rows_count == 0
        assert file_info.extraction_timestamp == now


class TestDataRow:
    """Test DataRow dataclass."""
    
    def test_data_row_creation(self):
        """Test creating a DataRow instance."""
        now = datetime.now()
        file_info = FileInfo(
            file_name="test.csv",
            file_path="/path/to/test.csv",
            file_size_bytes=1024,
            file_size_mb=1.0,
            last_modified=now,
            total_rows=100,
            total_columns=3,
            has_duplicates=False,
            duplicate_rows_count=0,
            extraction_timestamp=now
        )
        
        data_row = DataRow(
            row_id=1,
            data={"name": "John", "age": 30, "city": "New York"},
            file_info=file_info,
            inserted_at=now
        )
        
        assert data_row.row_id == 1
        assert data_row.data == {"name": "John", "age": 30, "city": "New York"}
        assert data_row.file_info == file_info
        assert data_row.inserted_at == now


class TestFileMetadata:
    """Test FileMetadata dataclass."""
    
    def test_file_metadata_creation(self):
        """Test creating a FileMetadata instance."""
        now = datetime.now()
        file_info = FileInfo(
            file_name="test.csv",
            file_path="/path/to/test.csv",
            file_size_bytes=1024,
            file_size_mb=1.0,
            last_modified=now,
            total_rows=100,
            total_columns=3,
            has_duplicates=False,
            duplicate_rows_count=0,
            extraction_timestamp=now
        )
        
        columns = {
            "name": ColumnMetadata(
                name="name",
                position=0,
                data_type=DataType.STRING,
                subtype="object",
                nullable=False,
                total_count=100,
                null_count=0,
                null_percentage=0.0,
                unique_count=100,
                max_length=50,
                sample_values=["John", "Jane"]
            )
        }
        
        schema_summary = SchemaSummary(
            numeric_columns_count=0,
            categorical_columns_count=1,
            datetime_columns_count=0,
            boolean_columns_count=0,
            numeric_columns=[],
            categorical_columns=["name"],
            datetime_columns=[],
            boolean_columns=[]
        )
        
        metadata = FileMetadata(
            file_info=file_info,
            columns=columns,
            schema_summary=schema_summary
        )
        
        assert metadata.file_info == file_info
        assert metadata.columns == columns
        assert metadata.schema_summary == schema_summary


class TestProcessingResult:
    """Test ProcessingResult dataclass."""
    
    def test_processing_result_success(self):
        """Test creating a successful ProcessingResult."""
        now = datetime.now()
        file_info = FileInfo(
            file_name="test.csv",
            file_path="/path/to/test.csv",
            file_size_bytes=1024,
            file_size_mb=1.0,
            last_modified=now,
            total_rows=100,
            total_columns=3,
            has_duplicates=False,
            duplicate_rows_count=0,
            extraction_timestamp=now
        )
        
        metadata = FileMetadata(
            file_info=file_info,
            columns={},
            schema_summary=SchemaSummary(
                numeric_columns_count=0,
                categorical_columns_count=0,
                datetime_columns_count=0,
                boolean_columns_count=0,
                numeric_columns=[],
                categorical_columns=[],
                datetime_columns=[],
                boolean_columns=[]
            )
        )
        
        result = ProcessingResult(
            success=True,
            file_path="/path/to/test.csv",
            collection_name="test_collection",
            rows_processed=100,
            rows_inserted=100,
            metadata=metadata
        )
        
        assert result.success is True
        assert result.file_path == "/path/to/test.csv"
        assert result.collection_name == "test_collection"
        assert result.rows_processed == 100
        assert result.rows_inserted == 100
        assert result.metadata == metadata
        assert result.error is None
    
    def test_processing_result_failure(self):
        """Test creating a failed ProcessingResult."""
        result = ProcessingResult(
            success=False,
            file_path="/path/to/test.csv",
            collection_name="test_collection",
            rows_processed=0,
            rows_inserted=0,
            metadata=None,
            error="File not found"
        )
        
        assert result.success is False
        assert result.error == "File not found"


class TestCollectionInfo:
    """Test CollectionInfo dataclass."""
    
    def test_collection_info_creation(self):
        """Test creating a CollectionInfo instance."""
        now = datetime.now()
        collection_info = CollectionInfo(
            collection_name="test_collection",
            document_count=1000,
            storage_size=1024000,
            index_size=51200,
            created_at=now,
            last_updated=now
        )
        
        assert collection_info.collection_name == "test_collection"
        assert collection_info.document_count == 1000
        assert collection_info.storage_size == 1024000
        assert collection_info.index_size == 51200
        assert collection_info.created_at == now
        assert collection_info.last_updated == now
        assert collection_info.metadata is None


class TestProcessingStatus:
    """Test ProcessingStatus dataclass."""
    
    def test_processing_status_creation(self):
        """Test creating a ProcessingStatus instance."""
        collections = [
            CollectionInfo(
                collection_name="test1",
                document_count=100,
                storage_size=102400,
                index_size=5120
            ),
            CollectionInfo(
                collection_name="test2",
                document_count=200,
                storage_size=204800,
                index_size=10240
            )
        ]
        
        status = ProcessingStatus(
            total_collections=2,
            collections=collections,
            success=True
        )
        
        assert status.total_collections == 2
        assert status.collections == collections
        assert status.success is True
        assert status.error is None
    
    def test_processing_status_with_error(self):
        """Test creating a ProcessingStatus with error."""
        status = ProcessingStatus(
            total_collections=0,
            collections=[],
            success=False,
            error="Database connection failed"
        )
        
        assert status.total_collections == 0
        assert status.collections == []
        assert status.success is False
        assert status.error == "Database connection failed" 