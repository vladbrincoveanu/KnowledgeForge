"""
Query Service

Service responsible for querying data from MongoDB collections and
providing collection management operations.
"""

from typing import Dict, List, Any
import logging

from ...Infrastructure.mongodb_connector import MongoDBConnector

logger = logging.getLogger(__name__)


class QueryService:
    """Service for querying data from MongoDB collections."""
    
    def __init__(self, mongodb_connector: MongoDBConnector):
        """
        Initialize the service with a MongoDB connector.
        
        Args:
            mongodb_connector (MongoDBConnector): MongoDB connection handler
        """
        self.mongodb_connector = mongodb_connector
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a specific collection.
        
        Args:
            collection_name (str): Name of the collection
            
        Returns:
            Dict[str, Any]: Collection information
        """
        try:
            info = self.mongodb_connector.get_collection_info(collection_name)
            if info:
                return {
                    "collection_name": info.collection_name,
                    "document_count": info.document_count,
                    "storage_size": info.storage_size,
                    "index_size": info.index_size,
                    "created_at": info.created_at.isoformat() if info.created_at else None,
                    "last_updated": info.last_updated.isoformat() if info.last_updated else None,
                    "metadata": info.metadata
                }
            else:
                return {"error": f"Collection '{collection_name}' not found"}
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {"error": str(e)}
    
    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections with their information.
        
        Returns:
            List[Dict[str, Any]]: List of collection information
        """
        try:
            collections = self.mongodb_connector.list_collections()
            return [
                {
                    "collection_name": col.collection_name,
                    "document_count": col.document_count,
                    "storage_size": col.storage_size,
                    "index_size": col.index_size,
                    "created_at": col.created_at.isoformat() if col.created_at else None,
                    "last_updated": col.last_updated.isoformat() if col.last_updated else None
                }
                for col in collections
            ]
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
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
            return self.mongodb_connector.delete_collection(collection_name)
        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}")
            return False
    
    def get_collection_statistics(self, collection_name: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a collection.
        
        Args:
            collection_name (str): Name of the collection
            
        Returns:
            Dict[str, Any]: Collection statistics
        """
        try:
            info = self.mongodb_connector.get_collection_info(collection_name)
            if not info:
                return {"error": f"Collection '{collection_name}' not found"}
            
            # Calculate additional statistics
            stats = {
                "collection_name": info.collection_name,
                "document_count": info.document_count,
                "storage_size": info.storage_size,
                "index_size": info.index_size,
                "total_size": info.storage_size + info.index_size,
                "created_at": info.created_at.isoformat() if info.created_at else None,
                "last_updated": info.last_updated.isoformat() if info.last_updated else None,
                "metadata": info.metadata
            }
            
            # Add calculated fields
            if info.document_count > 0:
                stats["avg_document_size"] = info.storage_size / info.document_count
                stats["index_overhead"] = (info.index_size / info.storage_size) * 100 if info.storage_size > 0 else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting collection statistics: {e}")
            return {"error": str(e)}
    
    def search_collections(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Search collections by name.
        
        Args:
            search_term (str): Search term to match collection names
            
        Returns:
            List[Dict[str, Any]]: Matching collections
        """
        try:
            all_collections = self.list_collections()
            search_term_lower = search_term.lower()
            
            matching_collections = [
                col for col in all_collections
                if search_term_lower in col["collection_name"].lower()
            ]
            
            return matching_collections
            
        except Exception as e:
            logger.error(f"Error searching collections: {e}")
            return []
    
    def get_collection_metadata(self, collection_name: str) -> Dict[str, Any]:
        """
        Get metadata for a specific collection.
        
        Args:
            collection_name (str): Name of the collection
            
        Returns:
            Dict[str, Any]: Collection metadata
        """
        try:
            info = self.mongodb_connector.get_collection_info(collection_name)
            if info and info.metadata:
                return {
                    "collection_name": collection_name,
                    "metadata": info.metadata
                }
            else:
                return {"error": f"Metadata not found for collection '{collection_name}'"}
                
        except Exception as e:
            logger.error(f"Error getting collection metadata: {e}")
            return {"error": str(e)} 