"""Helper functions for E2E testing."""

import time
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd
import neo4j
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx

logger = logging.getLogger(__name__)


class Neo4jTestHelper:
    """Helper class for Neo4j operations in tests."""
    
    def __init__(self, driver: neo4j.Driver, database: str = "test_knowledge_forge"):
        self.driver = driver
        self.database = database
    
    def count_nodes(self, label: Optional[str] = None) -> int:
        """Count nodes in the database."""
        with self.driver.session(database=self.database) as session:
            if label:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
            else:
                result = session.run("MATCH (n) RETURN count(n) as count")
            return result.single()["count"]
    
    def count_relationships(self, rel_type: Optional[str] = None) -> int:
        """Count relationships in the database."""
        with self.driver.session(database=self.database) as session:
            if rel_type:
                result = session.run(f"MATCH ()-[r:{rel_type}]-() RETURN count(r) as count")
            else:
                result = session.run("MATCH ()-[r]-() RETURN count(r) as count")
            return result.single()["count"]
    
    def get_nodes_by_label(self, label: str) -> List[Dict[str, Any]]:
        """Get all nodes with a specific label."""
        with self.driver.session(database=self.database) as session:
            result = session.run(f"MATCH (n:{label}) RETURN n")
            return [record["n"] for record in result]
    
    def get_relationships_by_type(self, rel_type: str) -> List[Dict[str, Any]]:
        """Get all relationships of a specific type."""
        with self.driver.session(database=self.database) as session:
            result = session.run(f"MATCH ()-[r:{rel_type}]-() RETURN r")
            return [record["r"] for record in result]
    
    def node_exists(self, properties: Dict[str, Any], label: Optional[str] = None) -> bool:
        """Check if a node with specific properties exists."""
        with self.driver.session(database=self.database) as session:
            where_clause = " AND ".join([f"n.{key} = ${key}" for key in properties.keys()])
            if label:
                query = f"MATCH (n:{label}) WHERE {where_clause} RETURN count(n) > 0 as exists"
            else:
                query = f"MATCH (n) WHERE {where_clause} RETURN count(n) > 0 as exists"
            result = session.run(query, **properties)
            return result.single()["exists"]
    
    def clear_database(self):
        """Clear all nodes and relationships from the test database."""
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")


class MetadataTestHelper:
    """Helper class for PostgreSQL metadata store operations in tests."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connection = None
        try:
            self.connection = psycopg2.connect(
                host=config.get("host", "localhost"),
                port=config.get("port", 5432),
                database=config.get("database", "knowledgeforge_test"),
                user=config.get("user", "knowledgeforge"),
                password=config.get("password", "knowledgeforge123")
            )
        except Exception as e:
            logger.warning(f"Could not connect to PostgreSQL metadata store: {e}")
            self.connection = None
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the metadata store."""
        if not self.connection:
            return False
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM information_schema.tables WHERE table_name = %s",
                    [table_name]
                )
                result = cursor.fetchone()
                return result[0] > 0
        except Exception:
            return False
    
    def count_records(self, table_name: str) -> int:
        """Count records in a table."""
        if not self.connection:
            return 0
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"SELECT count(*) FROM {table_name}")
                result = cursor.fetchone()
                return result[0]
        except Exception:
            return 0
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata by file_id."""
        if not self.connection:
            return None
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM file_metadata WHERE file_id = %s",
                    [file_id]
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception:
            return None
    
    def get_extraction_runs(self, file_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get extraction run records."""
        if not self.connection:
            return []
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                if file_id:
                    cursor.execute(
                        "SELECT * FROM extraction_runs WHERE file_id = %s",
                        [file_id]
                    )
                else:
                    cursor.execute("SELECT * FROM extraction_runs")
                
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception:
            return []
    
    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()


class APITestHelper:
    """Helper class for API testing operations."""
    
    @staticmethod
    async def upload_file(
        client: httpx.AsyncClient,
        file_path: Path,
        endpoint: str = "/api/v1/extract/upload"
    ) -> httpx.Response:
        """Upload a file to the API."""
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "text/csv")}
            response = await client.post(endpoint, files=files)
        return response
    
    @staticmethod
    async def start_extraction(
        client: httpx.AsyncClient,
        file_path: str,
        extraction_config: Optional[Dict[str, Any]] = None,
        endpoint: str = "/api/v1/extract/"
    ) -> httpx.Response:
        """Start extraction process."""
        payload = {"file_path": file_path}
        if extraction_config:
            payload["extraction_config"] = extraction_config
        return await client.post(endpoint, json=payload)
    
    @staticmethod
    async def get_task_status(
        client: httpx.AsyncClient,
        task_id: str,
        endpoint: str = "/api/v1/extract"
    ) -> httpx.Response:
        """Get task status."""
        return await client.get(f"{endpoint}/{task_id}")
    
    @staticmethod
    async def wait_for_task_completion(
        client: httpx.AsyncClient,
        task_id: str,
        timeout: int = 300,
        poll_interval: int = 2,
        endpoint: str = "/api/v1/extract"
    ) -> Dict[str, Any]:
        """Wait for a task to complete and return final status."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = await APITestHelper.get_task_status(client, task_id, endpoint)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                
                if status in ["completed", "failed"]:
                    return data
                
                logger.info(f"Task {task_id} status: {status}, progress: {data.get('progress', 0)}")
            
            await asyncio.sleep(poll_interval)
        
        raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")


class DataValidationHelper:
    """Helper class for validating test data and results."""
    
    @staticmethod
    def validate_csv_structure(file_path: Path) -> Dict[str, Any]:
        """Validate CSV file structure and return basic stats."""
        try:
            df = pd.read_csv(file_path)
            return {
                "valid": True,
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
                "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "null_counts": df.isnull().sum().to_dict(),
                "sample_values": {col: df[col].dropna().head(3).tolist() for col in df.columns}
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }
    
    @staticmethod
    def validate_entities(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate extracted entities structure."""
        if not entities:
            return {"valid": False, "error": "No entities found"}
        
        required_fields = ["id", "name", "type", "confidence"]
        validation_results = {
            "valid": True,
            "count": len(entities),
            "types": {},
            "confidence_range": {"min": 1.0, "max": 0.0},
            "missing_fields": []
        }
        
        for entity in entities:
            # Check required fields
            for field in required_fields:
                if field not in entity:
                    validation_results["missing_fields"].append(f"Entity missing {field}")
                    validation_results["valid"] = False
            
            # Track entity types
            entity_type = entity.get("type", "unknown")
            validation_results["types"][entity_type] = validation_results["types"].get(entity_type, 0) + 1
            
            # Track confidence range
            confidence = entity.get("confidence", 0)
            validation_results["confidence_range"]["min"] = min(
                validation_results["confidence_range"]["min"], confidence
            )
            validation_results["confidence_range"]["max"] = max(
                validation_results["confidence_range"]["max"], confidence
            )
        
        return validation_results
    
    @staticmethod
    def validate_relationships(relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate extracted relationships structure."""
        if not relationships:
            return {"valid": True, "count": 0, "note": "No relationships found (may be expected)"}
        
        required_fields = ["id", "source_entity", "target_entity", "type", "confidence"]
        validation_results = {
            "valid": True,
            "count": len(relationships),
            "types": {},
            "confidence_range": {"min": 1.0, "max": 0.0},
            "missing_fields": []
        }
        
        for relationship in relationships:
            # Check required fields
            for field in required_fields:
                if field not in relationship:
                    validation_results["missing_fields"].append(f"Relationship missing {field}")
                    validation_results["valid"] = False
            
            # Track relationship types
            rel_type = relationship.get("type", "unknown")
            validation_results["types"][rel_type] = validation_results["types"].get(rel_type, 0) + 1
            
            # Track confidence range
            confidence = relationship.get("confidence", 0)
            validation_results["confidence_range"]["min"] = min(
                validation_results["confidence_range"]["min"], confidence
            )
            validation_results["confidence_range"]["max"] = max(
                validation_results["confidence_range"]["max"], confidence
            )
        
        return validation_results


# Import asyncio for async operations
import asyncio
