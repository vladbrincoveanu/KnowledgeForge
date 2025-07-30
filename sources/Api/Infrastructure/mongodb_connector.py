"""
MongoDB Connector

Infrastructure layer component for MongoDB operations.
"""

import pymongo
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from bson import ObjectId
import logging

from ..Domain.models import CollectionInfo, DataRow, FileInfo, FileMetadata
from .config_manager import config_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MongoDBConnector:
    """MongoDB connection and operations handler."""
    
    def __init__(self, connection_string: str = None, 
                 database_name: str = None):
        """
        Initialize MongoDB connection.
        
        Args:
            connection_string (str): MongoDB connection string (optional, uses config if not provided)
            database_name (str): Name of the database to use (optional, uses config if not provided)
        """
        # Load configuration
        db_config = config_manager.get_database_config()
        
        # Use provided values or fall back to config
        self.connection_string = connection_string or db_config['connection_string']
        self.database_name = database_name or db_config['database_name']
        self.client = None
        self.db = None
        
    def connect(self) -> bool:
        """
        Establish connection to MongoDB.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.client = pymongo.MongoClient(self.connection_string)
            # Test the connection
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            logger.info(f"Successfully connected to MongoDB database: {self.database_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
    
    def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    def _convert_numpy_types(self, obj):
        """Convert numpy types to Python types for MongoDB serialization."""
        if isinstance(obj, dict):
            return {k: self._convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif hasattr(obj, 'item'):  # numpy types
            return obj.item()
        elif hasattr(obj, 'dtype'):  # numpy arrays and scalars
            if hasattr(obj, 'tolist'):
                return obj.tolist()
            else:
                return obj.item()
        elif str(type(obj)).startswith("<class 'numpy."):
            # Handle numpy boolean, int, float types
            if hasattr(obj, 'item'):
                return obj.item()
            else:
                return bool(obj) if isinstance(obj, (bool, type(True))) else obj
        else:
            return obj

    def create_collection(self, collection_name: str, metadata: FileMetadata) -> bool:
        """
        Create a new collection with metadata.
        
        Args:
            collection_name (str): Name of the collection
            metadata (FileMetadata): Schema metadata for the collection
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert metadata to dict for MongoDB storage
            metadata_dict = self._convert_metadata_to_dict(metadata)
            
            # Store metadata in a separate collection
            metadata_collection = self.db[f"{collection_name}_metadata"]
            metadata_doc = {
                "collection_name": collection_name,
                "metadata": metadata_dict,
                "created_at": datetime.now(),
                "total_documents": 0
            }
            metadata_collection.insert_one(metadata_doc)
            
            # Create the main collection
            collection = self.db[collection_name]
            # Create an index on the row_id field for efficient querying
            collection.create_index("row_id")
            
            logger.info(f"Created collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            return False
    
    def insert_data_rows(self, collection_name: str, data_rows: List[DataRow], 
                        batch_size: int = 1000) -> int:
        """
        Insert data rows into MongoDB collection.
        
        Args:
            collection_name (str): Name of the collection
            data_rows (List[DataRow]): List of data rows to insert
            batch_size (int): Number of documents to insert in each batch
            
        Returns:
            int: Number of documents inserted
        """
        try:
            collection = self.db[collection_name]
            inserted_count = 0
            
            # Process data in batches
            for i in range(0, len(data_rows), batch_size):
                batch = data_rows[i:i + batch_size]
                
                # Convert DataRow objects to MongoDB documents
                documents = []
                for data_row in batch:
                    doc = {
                        "row_id": data_row.row_id,
                        "data": data_row.data,
                        "file_info": self._convert_file_info_to_dict(data_row.file_info),
                        "inserted_at": data_row.inserted_at
                    }
                    documents.append(doc)
                
                # Insert batch
                result = collection.insert_many(documents)
                inserted_count += len(result.inserted_ids)
                
                logger.info(f"Inserted batch {i//batch_size + 1}: {len(documents)} documents")
            
            # Update metadata collection with document count
            metadata_collection = self.db[f"{collection_name}_metadata"]
            metadata_collection.update_one(
                {"collection_name": collection_name},
                {"$set": {"total_documents": inserted_count, "last_updated": datetime.now()}}
            )
            
            logger.info(f"Successfully inserted {inserted_count} documents into {collection_name}")
            return inserted_count
            
        except Exception as e:
            logger.error(f"Failed to insert data into {collection_name}: {e}")
            return 0
    
    def get_collection_info(self, collection_name: str) -> Optional[CollectionInfo]:
        """
        Get information about a collection.
        
        Args:
            collection_name (str): Name of the collection
            
        Returns:
            Optional[CollectionInfo]: Collection information
        """
        try:
            collection = self.db[collection_name]
            metadata_collection = self.db[f"{collection_name}_metadata"]
            
            # Get basic collection stats
            stats = self.db.command("collstats", collection_name)
            
            # Get metadata
            metadata_doc = metadata_collection.find_one({"collection_name": collection_name})
            
            return CollectionInfo(
                collection_name=collection_name,
                document_count=collection.count_documents({}),
                storage_size=stats.get("size", 0),
                index_size=stats.get("totalIndexSize", 0),
                metadata=self._convert_dict_to_metadata(metadata_doc.get("metadata")) if metadata_doc else None,
                created_at=metadata_doc.get("created_at") if metadata_doc else None,
                last_updated=metadata_doc.get("last_updated") if metadata_doc else None
            )
        except Exception as e:
            logger.error(f"Failed to get collection info for {collection_name}: {e}")
            return None
    
    def list_collections(self) -> List[CollectionInfo]:
        """
        List all collections in the database.
        
        Returns:
            List[CollectionInfo]: List of collection information
        """
        try:
            collections = []
            for collection_name in self.db.list_collection_names():
                if not collection_name.endswith("_metadata"):
                    info = self.get_collection_info(collection_name)
                    if info:
                        collections.append(info)
            return collections
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []
    
    def query_data(self, collection_name: str, query: Dict[str, Any] = None, 
                   limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """
        Query data from a collection.
        
        Args:
            collection_name (str): Name of the collection
            query (Dict[str, Any]): MongoDB query
            limit (int): Maximum number of documents to return
            skip (int): Number of documents to skip
            
        Returns:
            List[Dict[str, Any]]: Query results
        """
        try:
            collection = self.db[collection_name]
            if query is None:
                query = {}
            
            cursor = collection.find(query).skip(skip).limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"Failed to query collection {collection_name}: {e}")
            return []
    
    def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection and its metadata.
        
        Args:
            collection_name (str): Name of the collection to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Delete the main collection
            self.db[collection_name].drop()
            
            # Delete the metadata collection
            self.db[f"{collection_name}_metadata"].drop()
            
            logger.info(f"Successfully deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {e}")
            return False
    
    def _convert_metadata_to_dict(self, metadata: FileMetadata) -> Dict[str, Any]:
        """Convert FileMetadata to dictionary for MongoDB storage."""
        return {
            "file_info": self._convert_file_info_to_dict(metadata.file_info),
            "columns": {name: self._convert_column_metadata_to_dict(col) 
                       for name, col in metadata.columns.items()},
            "schema_summary": {
                "numeric_columns_count": metadata.schema_summary.numeric_columns_count,
                "categorical_columns_count": metadata.schema_summary.categorical_columns_count,
                "datetime_columns_count": metadata.schema_summary.datetime_columns_count,
                "boolean_columns_count": metadata.schema_summary.boolean_columns_count,
                "numeric_columns": metadata.schema_summary.numeric_columns,
                "categorical_columns": metadata.schema_summary.categorical_columns,
                "datetime_columns": metadata.schema_summary.datetime_columns,
                "boolean_columns": metadata.schema_summary.boolean_columns
            }
        }
    
    def _convert_file_info_to_dict(self, file_info: FileInfo) -> Dict[str, Any]:
        """Convert FileInfo to dictionary for MongoDB storage."""
        return {
            "file_name": file_info.file_name,
            "file_path": file_info.file_path,
            "file_size_bytes": file_info.file_size_bytes,
            "file_size_mb": file_info.file_size_mb,
            "last_modified": file_info.last_modified,
            "total_rows": file_info.total_rows,
            "total_columns": file_info.total_columns,
            "has_duplicates": file_info.has_duplicates,
            "duplicate_rows_count": file_info.duplicate_rows_count,
            "extraction_timestamp": file_info.extraction_timestamp
        }
    
    def _convert_column_metadata_to_dict(self, column: Any) -> Dict[str, Any]:
        """Convert ColumnMetadata to dictionary for MongoDB storage."""
        return {
            "name": column.name,
            "position": column.position,
            "data_type": column.data_type.value,
            "subtype": column.subtype,
            "nullable": column.nullable,
            "total_count": column.total_count,
            "null_count": column.null_count,
            "null_percentage": column.null_percentage,
            "unique_count": column.unique_count,
            "min_value": column.min_value,
            "max_value": column.max_value,
            "max_length": column.max_length,
            "sample_values": column.sample_values
        }
    
    def _convert_dict_to_metadata(self, metadata_dict: Dict[str, Any]) -> Optional[FileMetadata]:
        """Convert dictionary back to FileMetadata object."""
        if not metadata_dict:
            return None
        
        # This is a simplified conversion - in a full implementation,
        # you would convert back to proper domain objects
        return metadata_dict 