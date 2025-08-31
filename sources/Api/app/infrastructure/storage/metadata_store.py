"""Native PostgreSQL metadata store using psycopg2 for direct database operations."""

import json
import logging
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extensions import connection, cursor
import os

logger = logging.getLogger(__name__)

class PostgreSQLMetadataStore:
    """Native PostgreSQL metadata store using direct SQL queries."""
    
    def __init__(self, database_url: str = None, config: dict = None):
        """Initialize the PostgreSQL metadata store.
        
        Args:
            database_url: PostgreSQL connection string (overrides config)
            config: Configuration dictionary with database settings
        """
        if database_url:
            self.database_url = database_url
        elif config and 'database' in config:
            db_config = config['database']
            self.database_url = f"postgresql://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}"
        else:
            # Fallback to environment variables
            self.database_url = os.getenv('DATABASE_URL', 'postgresql://knowledgeforge:knowledgeforge123@localhost:5432/knowledgeforge')
        
        self.pool = None
        self._init_connection_pool()
    
    def _init_connection_pool(self):
        """Initialize the connection pool."""
        try:
            self.pool = SimpleConnectionPool(
                minconn=1,
                maxconn=20,
                dsn=self.database_url
            )
            logger.info("PostgreSQL connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
            raise
    
    def get_connection(self) -> connection:
        """Get a database connection from the pool."""
        if not self.pool:
            self._init_connection_pool()
        return self.pool.getconn()
    
    def return_connection(self, conn: connection):
        """Return a connection to the pool."""
        if self.pool:
            self.pool.putconn(conn)
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True) -> List[Dict]:
        """Execute a database query and return results."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
                conn.commit()
                return []
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Query execution failed: {e}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def execute_single(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Execute a query and return a single result."""
        results = self.execute_query(query, params, fetch=True)
        return results[0] if results else None
    
    def register_file(self, file_path: str, file_name: str, file_size: int, 
                     file_type: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """Register a new file with checksum calculation."""
        try:
            checksum = self._calculate_file_checksum(file_path)
            
            # Check if file already exists
            existing = self.execute_single(
                "SELECT id FROM files WHERE checksum = %s",
                (checksum,)
            )
            
            if existing:
                logger.info(f"File with checksum {checksum} already registered")
                return existing['id']
            
            # Register new file
            result = self.execute_single(
                """
                INSERT INTO files (file_path, file_name, file_size, checksum, file_type, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (file_path, file_name, file_size, checksum, file_type, 
                 Json(metadata) if metadata else None)
            )
            
            file_id = result['id']
            logger.info(f"Registered file '{file_name}' with ID {file_id}")
            return file_id
            
        except Exception as e:
            logger.error(f"Failed to register file: {e}")
            raise
    
    def start_extraction_run(self, file_id: int, run_id: str, config: Dict[str, Any],
                           model_version: str, extraction_method: str) -> str:
        """Start a new extraction run."""
        try:
            # Insert extraction run
            self.execute_query(
                """
                INSERT INTO extraction_runs (file_id, run_id, config, model_version, extraction_method)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (file_id, run_id, Json(config), model_version, extraction_method),
                fetch=False
            )
            
            # Update file status
            self.execute_query(
                """
                UPDATE files SET processing_status = 'processing', last_processed_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (file_id,),
                fetch=False
            )
            
            logger.info(f"Started extraction run {run_id} for file {file_id}")
            return run_id
            
        except Exception as e:
            logger.error(f"Failed to start extraction run: {e}")
            raise
    
    def complete_extraction_run(self, run_id: str, results: Dict[str, Any],
                              status: str = "completed", error_message: Optional[str] = None,
                              performance_metrics: Optional[Dict[str, Any]] = None) -> bool:
        """Complete an extraction run."""
        try:
            # Update extraction run
            self.execute_query(
                """
                UPDATE extraction_runs 
                SET completed_at = CURRENT_TIMESTAMP, status = %s, results = %s, 
                    error_message = %s, performance_metrics = %s
                WHERE run_id = %s
                """,
                (status, Json(results), error_message, 
                 Json(performance_metrics) if performance_metrics else None, run_id),
                fetch=False
            )
            
            # Get file_id for status update
            run_info = self.execute_single(
                "SELECT file_id FROM extraction_runs WHERE run_id = %s",
                (run_id,)
            )
            
            if run_info:
                # Update file status
                file_status = 'completed' if status == 'completed' else 'failed'
                self.execute_query(
                    """
                    UPDATE files SET processing_status = %s, last_processed_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (file_status, run_info['file_id']),
                    fetch=False
                )
            
            logger.info(f"Completed extraction run {run_id} with status {status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete extraction run: {e}")
            return False
    
    def store_entities(self, file_id: int, extraction_run_id: str, 
                      entities: List[Dict[str, Any]]) -> bool:
        """Store extracted entities."""
        try:
            for entity in entities:
                self.execute_query(
                    """
                    INSERT INTO entities_metadata (
                        entity_id, file_id, extraction_run_id, name, entity_type, confidence,
                        source_column, source_value, attributes, quality_score
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        entity.get('id'), file_id, extraction_run_id, entity.get('name'),
                        entity.get('entity_type'), entity.get('confidence', 0.0),
                        entity.get('source_column'), entity.get('source_value'),
                        Json(entity.get('attributes', {})), entity.get('quality_score', 0.0)
                    ),
                    fetch=False
                )
            
            logger.info(f"Stored {len(entities)} entities for extraction run {extraction_run_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store entities: {e}")
            return False
    
    def store_relationships(self, file_id: int, extraction_run_id: str,
                          relationships: List[Dict[str, Any]]) -> bool:
        """Store discovered relationships."""
        try:
            for rel in relationships:
                self.execute_query(
                    """
                    INSERT INTO relationships_metadata (
                        relationship_id, file_id, extraction_run_id, source_entity_id,
                        target_entity_id, relationship_type, confidence, attributes,
                        source_columns, evidence, discovery_method, quality_score
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        rel.get('id'), file_id, extraction_run_id,
                        rel.get('source_entity_id'), rel.get('target_entity_id'),
                        rel.get('relationship_type'), rel.get('confidence', 0.0),
                        Json(rel.get('attributes', {})), Json(rel.get('source_columns', [])),
                        rel.get('evidence', 'statistical_discovery'),
                        rel.get('discovery_method', 'pattern_matching'),
                        rel.get('quality_score', 0.0)
                    ),
                    fetch=False
                )
            
            logger.info(f"Stored {len(relationships)} relationships for extraction run {extraction_run_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store relationships: {e}")
            return False
    
    def get_file_by_id(self, file_id: int) -> Optional[Dict]:
        """Get file by ID."""
        try:
            return self.execute_single(
                "SELECT * FROM files WHERE id = %s",
                (file_id,)
            )
        except Exception as e:
            logger.error(f"Failed to get file {file_id}: {e}")
            return None
    
    def get_extraction_run(self, run_id: str) -> Optional[Dict]:
        """Get extraction run by ID."""
        try:
            return self.execute_single(
                "SELECT * FROM extraction_runs WHERE run_id = %s",
                (run_id,)
            )
        except Exception as e:
            logger.error(f"Failed to get extraction run {run_id}: {e}")
            return None
    
    def list_files(self, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """List files with optional status filter."""
        try:
            if status:
                return self.execute_query(
                    "SELECT * FROM files WHERE processing_status = %s ORDER BY uploaded_at DESC LIMIT %s",
                    (status, limit)
                )
            else:
                return self.execute_query(
                    "SELECT * FROM files ORDER BY uploaded_at DESC LIMIT %s",
                    (limit,)
                )
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def get_extraction_results(self, run_id: str) -> Dict[str, Any]:
        """Get complete extraction results for a run."""
        try:
            # Get extraction run info
            run_info = self.get_extraction_run(run_id)
            if not run_info:
                return {}
            
            # Get entities
            entities = self.execute_query(
                "SELECT * FROM entities_metadata WHERE extraction_run_id = %s",
                (run_id,)
            )
            
            # Get relationships
            relationships = self.execute_query(
                "SELECT * FROM relationships_metadata WHERE extraction_run_id = %s",
                (run_id,)
            )
            
            return {
                'extraction_run': run_info,
                'entities': entities,
                'relationships': relationships,
                'summary': {
                    'total_entities': len(entities),
                    'total_relationships': len(relationships),
                    'status': run_info['status']
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get extraction results: {e}")
            return {}
    
    def cleanup_old_files(self, days_old: int = 30) -> int:
        """Clean up old files and their associated data."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Delete old files (cascade will handle related records)
            result = self.execute_query(
                "DELETE FROM files WHERE uploaded_at < %s RETURNING id",
                (cutoff_date,),
                fetch=False
            )
            
            count = len(result) if result else 0
            logger.info(f"Cleaned up {count} old files")
            return count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return 0
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of file."""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return "unknown"
    
    def close(self):
        """Close the connection pool."""
        if self.pool:
            self.pool.closeall()
            logger.info("PostgreSQL connection pool closed")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()

# Backward compatibility alias
MetadataStore = PostgreSQLMetadataStore
