"""
Data Processing Service

Main service for orchestrating data processing operations including
file processing, directory processing, and status management.
"""

import os
import glob
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from ...Domain.models import ProcessingResult, ProcessingStatus
from ...Domain.dtos import (
    ProcessFileRequest, ProcessDirectoryRequest, QueryRequest,
    ProcessingResponse, QueryResponse, StatusResponse
)
from ...Infrastructure.mongodb_connector import MongoDBConnector
from .file_processor_service import FileProcessorService

logger = logging.getLogger(__name__)


class DataProcessingService:
    """Service for processing data files and storing them in MongoDB."""
    
    def __init__(self, mongodb_connector: MongoDBConnector):
        """
        Initialize the service with a MongoDB connector.
        
        Args:
            mongodb_connector (MongoDBConnector): MongoDB connection handler
        """
        self.mongodb_connector = mongodb_connector
        self.file_processor = FileProcessorService(mongodb_connector)
        
    def process_file(self, request: ProcessFileRequest) -> ProcessingResponse:
        """
        Process a single file and store its data in MongoDB.
        
        Args:
            request (ProcessFileRequest): Processing request
            
        Returns:
            ProcessingResponse: Processing result
        """
        try:
            file_path = request.file_path
            collection_name = request.collection_name or self._generate_collection_name(file_path)
            
            # Delegate to file processor service
            result = self.file_processor.process_file(file_path, collection_name, request.sheet_name)
            
            if result.success:
                # Convert metadata to dictionary for JSON serialization
                metadata_dict = {}
                if result.metadata and result.metadata.columns:
                    for col_name, col_metadata in result.metadata.columns.items():
                        metadata_dict[col_name] = {
                            "name": col_metadata.name,
                            "data_type": col_metadata.data_type.value if hasattr(col_metadata.data_type, 'value') else str(col_metadata.data_type),
                            "nullable": col_metadata.nullable,
                            "unique_count": col_metadata.unique_count,
                            "sample_values": col_metadata.sample_values[:5] if col_metadata.sample_values else []
                        }
                
                return ProcessingResponse(
                    success=True,
                    message=f"Successfully processed {file_path}",
                    data={
                        "collection_name": result.collection_name,
                        "rows_processed": result.rows_processed,
                        "rows_inserted": result.rows_inserted,
                        "file_info": {
                            "file_name": result.metadata.file_info.file_name,
                            "total_rows": result.metadata.file_info.total_rows,
                            "total_columns": result.metadata.file_info.total_columns
                        },
                        "columns": metadata_dict
                    }
                )
            else:
                return ProcessingResponse(
                    success=False,
                    message=f"Failed to process {file_path}",
                    error=result.error
                )
                
        except Exception as e:
            logger.error(f"Error processing file {request.file_path}: {e}")
            return ProcessingResponse(
                success=False,
                message=f"Error processing file: {str(e)}",
                error=str(e)
            )
    
    def process_directory(self, request: ProcessDirectoryRequest) -> ProcessingResponse:
        """
        Process all files in a directory matching the pattern.
        
        Args:
            request (ProcessDirectoryRequest): Directory processing request
            
        Returns:
            ProcessingResponse: Processing result
        """
        try:
            directory_path = request.directory_path
            file_pattern = request.file_pattern
            
            # Find matching files
            pattern = os.path.join(directory_path, file_pattern)
            files = glob.glob(pattern)
            
            if not files:
                return ProcessingResponse(
                    success=False,
                    message=f"No files found matching pattern: {pattern}",
                    error="No matching files found"
                )
            
            # Process each file
            results = []
            for file_path in files:
                if file_path.lower().endswith(('.csv', '.xlsx', '.xls')):
                    file_request = ProcessFileRequest(file_path=file_path)
                    result = self.process_file(file_request)
                    results.append({
                        "file": file_path,
                        "success": result.success,
                        "message": result.message,
                        "data": result.data
                    })
            
            # Count successes and failures
            successful = sum(1 for r in results if r["success"])
            failed = len(results) - successful
            
            return ProcessingResponse(
                success=failed == 0,
                message=f"Processed {len(results)} files. {successful} successful, {failed} failed.",
                data={
                    "total_files": len(results),
                    "successful": successful,
                    "failed": failed,
                    "results": results
                }
            )
            
        except Exception as e:
            logger.error(f"Error processing directory {request.directory_path}: {e}")
            return ProcessingResponse(
                success=False,
                message=f"Error processing directory: {str(e)}",
                error=str(e)
            )
    
    def get_processing_status(self) -> StatusResponse:
        """
        Get the status of all processed collections.
        
        Returns:
            StatusResponse: Status information
        """
        try:
            collections = self.mongodb_connector.list_collections()
            
            collections_data = []
            for collection in collections:
                collections_data.append({
                    "collection_name": collection.collection_name,
                    "document_count": collection.document_count,
                    "storage_size": collection.storage_size,
                    "index_size": collection.index_size,
                    "created_at": collection.created_at.isoformat() if collection.created_at else None,
                    "last_updated": collection.last_updated.isoformat() if collection.last_updated else None
                })
            
            return StatusResponse(
                success=True,
                total_collections=len(collections),
                collections=collections_data
            )
            
        except Exception as e:
            logger.error(f"Error getting processing status: {e}")
            return StatusResponse(
                success=False,
                total_collections=0,
                collections=[],
                error=str(e)
            )
    
    def query_data(self, request: QueryRequest) -> QueryResponse:
        """
        Query data from a collection.
        
        Args:
            request (QueryRequest): Query request
            
        Returns:
            QueryResponse: Query results
        """
        try:
            data = self.mongodb_connector.query_data(
                collection_name=request.collection_name,
                query=request.query,
                limit=request.limit,
                skip=request.skip
            )
            
            return QueryResponse(
                success=True,
                data=data,
                total_count=len(data),
                limit=request.limit,
                skip=request.skip
            )
            
        except Exception as e:
            logger.error(f"Error querying data: {e}")
            return QueryResponse(
                success=False,
                data=[],
                total_count=0,
                limit=request.limit,
                skip=request.skip,
                error=str(e)
            )
    
    def _generate_collection_name(self, file_path: str) -> str:
        """Generate a collection name from file path."""
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        # Clean the name for MongoDB collection naming
        collection_name = base_name.lower().replace(' ', '_').replace('-', '_')
        # Remove any non-alphanumeric characters except underscore
        collection_name = ''.join(c for c in collection_name if c.isalnum() or c == '_')
        return f"csv_{collection_name}" if file_path.lower().endswith('.csv') else f"xlsx_{collection_name}" 