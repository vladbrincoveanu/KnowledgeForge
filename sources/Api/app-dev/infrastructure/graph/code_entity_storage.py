"""Neo4j storage adapter for code entities and relationships."""

import logging
from datetime import datetime
from typing import Any, Optional

from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import ServiceUnavailable

from domain.models.code_entities import (
    CodeEntity,
    CodeRelationship,
    ExtractionResult,
)

logger = logging.getLogger(__name__)


class CodeEntityNeo4jStorage:
    """Store and query code entities in Neo4j."""
    
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
        database: str = "neo4j",
        encrypted: bool = False,
    ):
        """Initialize Neo4j storage."""
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.encrypted = encrypted
        self.driver: Optional[Driver] = None
    
    def connect(self) -> bool:
        """Connect to Neo4j."""
        try:
            if self.encrypted:
                self.driver = GraphDatabase.driver(
                    self.uri,
                    auth=(self.username, self.password),
                    encrypted=True,
                )
            else:
                self.driver = GraphDatabase.driver(
                    self.uri,
                    auth=(self.username, self.password),
                    encrypted=False,
                )
            
            # Verify connectivity
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False
    
    def close(self):
        """Close connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def create_schema(self):
        """Create indexes and constraints for code entities."""
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")
        
        with self.driver.session(database=self.database) as session:
            # Constraints
            constraints = [
                "CREATE CONSTRAINT code_entity_id_unique IF NOT EXISTS FOR (e:CodeEntity) REQUIRE e.id IS UNIQUE",
                "CREATE CONSTRAINT code_entity_id_not_null IF NOT EXISTS FOR (e:CodeEntity) REQUIRE e.id IS NOT NULL",
            ]
            
            # Indexes
            indexes = [
                "CREATE INDEX code_entity_name IF NOT EXISTS FOR (e:CodeEntity) ON (e.name)",
                "CREATE INDEX code_entity_type IF NOT EXISTS FOR (e:CodeEntity) ON (e.entity_type)",
                "CREATE INDEX code_entity_language IF NOT EXISTS FOR (e:CodeEntity) ON (e.language)",
                "CREATE INDEX code_entity_file IF NOT EXISTS FOR (e:CodeEntity) ON (e.file_path)",
                "CREATE INDEX code_entity_source_type IF NOT EXISTS FOR (e:CodeEntity) ON (e.source_type)",
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"Created constraint: {constraint}")
                except Exception as e:
                    logger.warning(f"Constraint may already exist: {e}")
            
            for index in indexes:
                try:
                    session.run(index)
                    logger.info(f"Created index: {index}")
                except Exception as e:
                    logger.warning(f"Index may already exist: {e}")
    
    def store_extraction_result(
        self,
        result: ExtractionResult,
        clear_existing: bool = False,
    ) -> dict[str, int]:
        """
        Store complete extraction result in Neo4j.
        
        Args:
            result: ExtractionResult to store
            clear_existing: If True, clear existing data first
            
        Returns:
            Dictionary with counts of stored items
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")
        
        stats = {
            "entities_stored": 0,
            "relationships_stored": 0,
            "errors": 0,
        }
        
        with self.driver.session(database=self.database) as session:
            # Clear existing data if requested
            if clear_existing:
                logger.info("Clearing existing code entities...")
                session.run("MATCH (e:CodeEntity) DETACH DELETE e")
            
            # Store entities in batches
            batch_size = 100
            for i in range(0, len(result.entities), batch_size):
                batch = result.entities[i:i + batch_size]
                try:
                    count = self._store_entity_batch(session, batch)
                    stats["entities_stored"] += count
                except Exception as e:
                    logger.error(f"Failed to store entity batch: {e}")
                    stats["errors"] += 1
            
            # Store relationships in batches
            for i in range(0, len(result.relationships), batch_size):
                batch = result.relationships[i:i + batch_size]
                try:
                    count = self._store_relationship_batch(session, batch)
                    stats["relationships_stored"] += count
                except Exception as e:
                    logger.error(f"Failed to store relationship batch: {e}")
                    stats["errors"] += 1
        
        logger.info(
            f"Stored {stats['entities_stored']} entities and "
            f"{stats['relationships_stored']} relationships"
        )
        
        return stats
    
    def _store_entity_batch(
        self,
        session: Session,
        entities: list[CodeEntity],
    ) -> int:
        """Store a batch of entities."""
        query = """
        UNWIND $entities AS entity
        MERGE (e:CodeEntity {id: entity.id})
        SET e.name = entity.name,
            e.entity_type = entity.entity_type,
            e.language = entity.language,
            e.source_type = entity.source_type,
            e.file_path = entity.file_path,
            e.line_start = entity.line_start,
            e.line_end = entity.line_end,
            e.signature = entity.signature,
            e.documentation = entity.documentation,
            e.modifiers = entity.modifiers,
            e.parent_entity_id = entity.parent_entity_id,
            e.confidence = entity.confidence,
            e.extracted_at = entity.extracted_at,
            e.extractor_version = entity.extractor_version,
            e.updated_at = datetime()
        SET e :Code
        RETURN count(e) as count
        """
        
        entity_dicts = [
            {
                "id": e.id,
                "name": e.name,
                "entity_type": e.entity_type.value,
                "language": e.language.value,
                "source_type": e.source_type.value,
                "file_path": e.file_path,
                "line_start": e.line_start,
                "line_end": e.line_end,
                "signature": e.signature,
                "documentation": e.documentation,
                "modifiers": e.modifiers,
                "parent_entity_id": e.parent_entity_id,
                "confidence": e.confidence,
                "extracted_at": e.extracted_at.isoformat(),
                "extractor_version": e.extractor_version,
            }
            for e in entities
        ]
        
        result = session.run(query, entities=entity_dicts)
        record = result.single()
        return record["count"] if record else 0
    
    def _store_relationship_batch(
        self,
        session: Session,
        relationships: list[CodeRelationship],
    ) -> int:
        """Store a batch of relationships."""
        query = """
        UNWIND $relationships AS rel
        MATCH (source:CodeEntity {id: rel.source_entity_id})
        MATCH (target:CodeEntity {id: rel.target_entity_id})
        MERGE (source)-[r:CODE_RELATIONSHIP {id: rel.id}]->(target)
        SET r.relationship_type = rel.relationship_type,
            r.direction = rel.direction,
            r.strength = rel.strength,
            r.context = rel.context,
            r.line_number = rel.line_number,
            r.confidence = rel.confidence,
            r.extracted_at = rel.extracted_at,
            r.updated_at = datetime()
        RETURN count(r) as count
        """
        
        rel_dicts = [
            {
                "id": r.id,
                "source_entity_id": r.source_entity_id,
                "target_entity_id": r.target_entity_id,
                "relationship_type": r.relationship_type.value,
                "direction": r.direction,
                "strength": r.strength,
                "context": r.context,
                "line_number": r.line_number,
                "confidence": r.confidence,
                "extracted_at": r.extracted_at.isoformat(),
            }
            for r in relationships
        ]
        
        result = session.run(query, relationships=rel_dicts)
        record = result.single()
        return record["count"] if record else 0
    
    def query_entities(
        self,
        entity_type: Optional[str] = None,
        language: Optional[str] = None,
        file_path: Optional[str] = None,
        name: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query entities with filters.
        
        Returns:
            List of entity dictionaries
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")
        
        # Build query with filters
        where_clauses = []
        params = {"limit": limit}
        
        if entity_type:
            where_clauses.append("e.entity_type = $entity_type")
            params["entity_type"] = entity_type
        
        if language:
            where_clauses.append("e.language = $language")
            params["language"] = language
        
        if file_path:
            where_clauses.append("e.file_path CONTAINS $file_path")
            params["file_path"] = file_path
        
        if name:
            where_clauses.append("e.name CONTAINS $name")
            params["name"] = name
        
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        query = f"""
        MATCH (e:CodeEntity)
        {where_clause}
        RETURN e
        LIMIT $limit
        """
        
        with self.driver.session(database=self.database) as session:
            result = session.run(query, **params)
            return [record["e"] for record in result]
    
    def get_entity_relationships(
        self,
        entity_id: str,
        relationship_type: Optional[str] = None,
        direction: str = "both",  # "both", "outgoing", "incoming"
    ) -> dict[str, Any]:
        """
        Get all relationships for an entity.
        
        Returns:
            Dictionary with entity, outgoing, and incoming relationships
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")
        
        with self.driver.session(database=self.database) as session:
            # Get the entity
            entity_query = "MATCH (e:CodeEntity {id: $entity_id}) RETURN e"
            entity_result = session.run(entity_query, entity_id=entity_id)
            entity_record = entity_result.single()
            
            if not entity_record:
                return {"entity": None, "outgoing": [], "incoming": []}
            
            entity = entity_record["e"]
            
            # Get relationships
            outgoing = []
            incoming = []
            
            if direction in ["both", "outgoing"]:
                out_query = """
                MATCH (e:CodeEntity {id: $entity_id})-[r:CODE_RELATIONSHIP]->(target:CodeEntity)
                """ + (
                    "WHERE r.relationship_type = $rel_type " if relationship_type else ""
                ) + """
                RETURN r, target
                """
                params = {"entity_id": entity_id}
                if relationship_type:
                    params["rel_type"] = relationship_type
                
                out_result = session.run(out_query, **params)
                outgoing = [
                    {
                        "relationship": record["r"],
                        "target": record["target"],
                    }
                    for record in out_result
                ]
            
            if direction in ["both", "incoming"]:
                in_query = """
                MATCH (source:CodeEntity)-[r:CODE_RELATIONSHIP]->(e:CodeEntity {id: $entity_id})
                """ + (
                    "WHERE r.relationship_type = $rel_type " if relationship_type else ""
                ) + """
                RETURN r, source
                """
                params = {"entity_id": entity_id}
                if relationship_type:
                    params["rel_type"] = relationship_type
                
                in_result = session.run(in_query, **params)
                incoming = [
                    {
                        "relationship": record["r"],
                        "source": record["source"],
                    }
                    for record in in_result
                ]
            
            return {
                "entity": entity,
                "outgoing": outgoing,
                "incoming": incoming,
            }
    
    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about stored code entities."""
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")
        
        with self.driver.session(database=self.database) as session:
            # Entity counts by type
            entity_stats = session.run("""
                MATCH (e:CodeEntity)
                RETURN e.entity_type as type, count(e) as count
                ORDER BY count DESC
            """)
            
            # Relationship counts by type
            rel_stats = session.run("""
                MATCH ()-[r:CODE_RELATIONSHIP]->()
                RETURN r.relationship_type as type, count(r) as count
                ORDER BY count DESC
            """)
            
            # Language distribution
            lang_stats = session.run("""
                MATCH (e:CodeEntity)
                RETURN e.language as language, count(e) as count
                ORDER BY count DESC
            """)
            
            # File distribution
            file_stats = session.run("""
                MATCH (e:CodeEntity)
                RETURN e.file_path as file, count(e) as count
                ORDER BY count DESC
                LIMIT 20
            """)
            
            return {
                "entities_by_type": [
                    {"type": r["type"], "count": r["count"]}
                    for r in entity_stats
                ],
                "relationships_by_type": [
                    {"type": r["type"], "count": r["count"]}
                    for r in rel_stats
                ],
                "languages": [
                    {"language": r["language"], "count": r["count"]}
                    for r in lang_stats
                ],
                "top_files": [
                    {"file": r["file"], "count": r["count"]}
                    for r in file_stats
                ],
            }
