"""Graph management module for Neo4j operations."""

import logging
from typing import Dict, List, Any, Optional, Tuple
from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import ServiceUnavailable, AuthError
import json
from datetime import datetime

from .models import Entity, Relationship, Ontology

logger = logging.getLogger(__name__)


class GraphManager:
    """Manages Neo4j graph database operations for ontology storage."""
    
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        """Initialize the graph manager.
        
        Args:
            uri: Neo4j database URI
            username: Database username
            password: Database password
            database: Database name (default: neo4j)
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver: Optional[Driver] = None
        
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def connect(self) -> bool:
        """Connect to Neo4j database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            
            # Test connection
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 as test")
                result.single()
            
            logger.info(f"Successfully connected to Neo4j database: {self.database}")
            return True
            
        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Neo4j: {e}")
            return False
    
    def close(self):
        """Close the database connection."""
        if self.driver:
            self.driver.close()
            self.driver = None
            logger.info("Neo4j connection closed")
    
    def is_connected(self) -> bool:
        """Check if connected to database.
        
        Returns:
            True if connected, False otherwise
        """
        if not self.driver:
            return False
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 as test")
                result.single()
            return True
        except Exception:
            return False
    
    def create_constraints(self):
        """Create database constraints for data integrity."""
        if not self.is_connected():
            logger.error("Cannot create constraints: not connected to database")
            return False
        
        constraints = [
            "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT relationship_id IF NOT EXISTS FOR (r:Relationship) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS NOT NULL",
            "CREATE CONSTRAINT relationship_type IF NOT EXISTS FOR (r:Relationship) REQUIRE r.type IS NOT NULL"
        ]
        
        try:
            with self.driver.session(database=self.database) as session:
                for constraint in constraints:
                    session.run(constraint)
            
            logger.info("Database constraints created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create constraints: {e}")
            return False
    
    def store_ontology(self, ontology: Ontology, dataset_name: str) -> bool:
        """Store complete ontology in Neo4j.
        
        Args:
            ontology: Ontology object to store
            dataset_name: Name of the dataset
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            logger.error("Cannot store ontology: not connected to database")
            return False
        
        try:
            with self.driver.session(database=self.database) as session:
                # Store entities first
                for entity in ontology.entities:
                    self._store_entity(session, entity, dataset_name)
                
                # Store relationships
                for relationship in ontology.relationships:
                    self._store_relationship(session, relationship, dataset_name)
                
                # Store ontology metadata
                self._store_ontology_metadata(session, ontology, dataset_name)
            
            logger.info(f"Successfully stored ontology with {len(ontology.entities)} entities and {len(ontology.relationships)} relationships")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store ontology: {e}")
            return False
    
    def _store_entity(self, session: Session, entity: Entity, dataset_name: str):
        """Store a single entity in Neo4j."""
        query = """
        MERGE (e:Entity {id: $entity_id})
        SET e.name = $name,
            e.entity_type = $entity_type,
            e.confidence = $confidence,
            e.source_column = $source_column,
            e.source_value = $source_value,
            e.dataset = $dataset_name,
            e.attributes = $attributes,
            e.created_at = $created_at
        """
        
        session.run(query, {
            'entity_id': entity.id,
            'name': entity.name,
            'entity_type': entity.entity_type,
            'confidence': entity.confidence,
            'source_column': entity.source_column,
            'source_value': entity.source_value,
            'dataset_name': dataset_name,
            'attributes': json.dumps(entity.attributes),
            'created_at': datetime.now().isoformat()
        })
    
    def _store_relationship(self, session: Session, relationship: Relationship, dataset_name: str):
        """Store a single relationship in Neo4j."""
        # First ensure both entities exist
        entity_check_query = """
        MATCH (e:Entity {id: $entity_id})
        RETURN e.id
        """
        
        source_exists = session.run(entity_check_query, {'entity_id': relationship.source_entity_id}).single()
        target_exists = session.run(entity_check_query, {'entity_id': relationship.target_entity_id}).single()
        
        if not source_exists or not target_exists:
            logger.warning(f"Relationship {relationship.id} references non-existent entities")
            return
        
        # Create relationship
        rel_query = """
        MATCH (source:Entity {id: $source_id})
        MATCH (target:Entity {id: $target_id})
        MERGE (source)-[r:RELATES_TO {id: $rel_id}]->(target)
        SET r.type = $rel_type,
            r.confidence = $confidence,
            r.attributes = $attributes,
            r.dataset = $dataset_name,
            r.created_at = $created_at
        """
        
        session.run(rel_query, {
            'source_id': relationship.source_entity_id,
            'target_id': relationship.target_entity_id,
            'rel_id': relationship.id,
            'rel_type': relationship.relationship_type,
            'confidence': relationship.confidence,
            'attributes': json.dumps(relationship.attributes),
            'dataset_name': dataset_name,
            'created_at': datetime.now().isoformat()
        })
    
    def _store_ontology_metadata(self, session: Session, ontology: Ontology, dataset_name: str):
        """Store ontology metadata."""
        metadata_query = """
        MERGE (o:Ontology {dataset: $dataset_name})
        SET o.version = $version,
            o.entity_count = $entity_count,
            o.relationship_count = $relationship_count,
            o.metadata = $metadata,
            o.created_at = $created_at,
            o.updated_at = $updated_at
        """
        
        session.run(metadata_query, {
            'dataset_name': dataset_name,
            'version': ontology.version,
            'entity_count': len(ontology.entities),
            'relationship_count': len(ontology.relationships),
            'metadata': json.dumps(ontology.metadata),
            'created_at': ontology.created_at,
            'updated_at': datetime.now().isoformat()
        })
    
    def query_entities(self, entity_type: Optional[str] = None, 
                      dataset_name: Optional[str] = None, 
                      limit: int = 100) -> List[Dict[str, Any]]:
        """Query entities from the graph.
        
        Args:
            entity_type: Filter by entity type
            dataset_name: Filter by dataset
            limit: Maximum number of results
            
        Returns:
            List of entity dictionaries
        """
        if not self.is_connected():
            logger.error("Cannot query entities: not connected to database")
            return []
        
        query = "MATCH (e:Entity)"
        params = {}
        
        if entity_type:
            query += " WHERE e.entity_type = $entity_type"
            params['entity_type'] = entity_type
        
        if dataset_name:
            if 'WHERE' in query:
                query += " AND e.dataset = $dataset_name"
            else:
                query += " WHERE e.dataset = $dataset_name"
            params['dataset_name'] = dataset_name
        
        query += " RETURN e LIMIT $limit"
        params['limit'] = limit
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, params)
                entities = []
                
                for record in result:
                    entity_data = dict(record['e'])
                    # Parse attributes JSON
                    if 'attributes' in entity_data:
                        try:
                            entity_data['attributes'] = json.loads(entity_data['attributes'])
                        except (json.JSONDecodeError, TypeError):
                            entity_data['attributes'] = {}
                    
                    entities.append(entity_data)
                
                return entities
                
        except Exception as e:
            logger.error(f"Failed to query entities: {e}")
            return []
    
    def query_relationships(self, relationship_type: Optional[str] = None,
                          dataset_name: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Query relationships from the graph.
        
        Args:
            relationship_type: Filter by relationship type
            dataset_name: Filter by dataset
            limit: Maximum number of results
            
        Returns:
            List of relationship dictionaries
        """
        if not self.is_connected():
            logger.error("Cannot query relationships: not connected to database")
            return []
        
        query = """
        MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
        """
        params = {}
        
        if relationship_type:
            query += " WHERE r.type = $relationship_type"
            params['relationship_type'] = relationship_type
        
        if dataset_name:
            if 'WHERE' in query:
                query += " AND r.dataset = $dataset_name"
            else:
                query += " WHERE r.dataset = $dataset_name"
            params['dataset_name'] = dataset_name
        
        query += """
        RETURN source.name as source_name, 
               target.name as target_name, 
               r.type as relationship_type,
               r.confidence as confidence,
               r.attributes as attributes
        LIMIT $limit
        """
        params['limit'] = limit
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, params)
                relationships = []
                
                for record in result:
                    rel_data = dict(record)
                    # Parse attributes JSON
                    if 'attributes' in rel_data and rel_data['attributes']:
                        try:
                            rel_data['attributes'] = json.loads(rel_data['attributes'])
                        except (json.JSONDecodeError, TypeError):
                            rel_data['attributes'] = {}
                    
                    relationships.append(rel_data)
                
                return relationships
                
        except Exception as e:
            logger.error(f"Failed to query relationships: {e}")
            return []
    
    def get_entity_neighbors(self, entity_id: str, max_depth: int = 2) -> Dict[str, Any]:
        """Get neighboring entities up to a certain depth.
        
        Args:
            entity_id: ID of the target entity
            max_depth: Maximum depth to traverse
            
        Returns:
            Dictionary with entity and its neighbors
        """
        if not self.is_connected():
            logger.error("Cannot get neighbors: not connected to database")
            return {}
        
        query = f"""
        MATCH path = (start:Entity {{id: $entity_id}})-[r:RELATES_TO*1..{max_depth}]-(neighbor:Entity)
        RETURN start, neighbor, r, length(path) as depth
        ORDER BY depth
        """
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, {'entity_id': entity_id})
                
                neighbors = []
                start_entity = None
                
                for record in result:
                    if start_entity is None:
                        start_entity = dict(record['start'])
                        if 'attributes' in start_entity:
                            try:
                                start_entity['attributes'] = json.loads(start_entity['attributes'])
                            except (json.JSONDecodeError, TypeError):
                                start_entity['attributes'] = {}
                    
                    neighbor_data = {
                        'entity': dict(record['neighbor']),
                        'depth': record['depth'],
                        'relationships': [dict(rel) for rel in record['r']]
                    }
                    
                    # Parse attributes JSON
                    if 'attributes' in neighbor_data['entity']:
                        try:
                            neighbor_data['entity']['attributes'] = json.loads(neighbor_data['entity']['attributes'])
                        except (json.JSONDecodeError, TypeError):
                            neighbor_data['entity']['attributes'] = {}
                    
                    neighbors.append(neighbor_data)
                
                return {
                    'start_entity': start_entity,
                    'neighbors': neighbors
                }
                
        except Exception as e:
            logger.error(f"Failed to get neighbors: {e}")
            return {}
    
    def get_graph_statistics(self, dataset_name: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics about the graph.
        
        Args:
            dataset_name: Optional dataset filter
            
        Returns:
            Dictionary with graph statistics
        """
        if not self.is_connected():
            logger.error("Cannot get statistics: not connected to database")
            return {}
        
        # Base queries
        entity_count_query = "MATCH (e:Entity)"
        relationship_count_query = "MATCH ()-[r:RELATES_TO]->()"
        
        if dataset_name:
            entity_count_query += " WHERE e.dataset = $dataset_name"
            relationship_count_query += " WHERE r.dataset = $dataset_name"
        
        entity_count_query += " RETURN count(e) as count"
        relationship_count_query += " RETURN count(r) as count"
        
        try:
            with self.driver.session(database=self.database) as session:
                params = {'dataset_name': dataset_name} if dataset_name else {}
                
                entity_result = session.run(entity_count_query, params)
                relationship_result = session.run(relationship_count_query, params)
                
                entity_count = entity_result.single()['count']
                relationship_count = relationship_result.single()['count']
                
                # Get entity type distribution
                type_query = """
                MATCH (e:Entity)
                """
                if dataset_name:
                    type_query += " WHERE e.dataset = $dataset_name"
                type_query += """
                RETURN e.entity_type as type, count(e) as count
                ORDER BY count DESC
                """
                
                type_result = session.run(type_query, params)
                type_distribution = {record['type']: record['count'] for record in type_result}
                
                return {
                    'total_entities': entity_count,
                    'total_relationships': relationship_count,
                    'entity_type_distribution': type_distribution,
                    'dataset': dataset_name
                }
                
        except Exception as e:
            logger.error(f"Failed to get graph statistics: {e}")
            return {}
    
    def clear_dataset(self, dataset_name: str) -> bool:
        """Clear all data for a specific dataset.
        
        Args:
            dataset_name: Name of the dataset to clear
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            logger.error("Cannot clear dataset: not connected to database")
            return False
        
        try:
            with self.driver.session(database=self.database) as session:
                # Delete relationships first
                rel_query = """
                MATCH ()-[r:RELATES_TO]->()
                WHERE r.dataset = $dataset_name
                DELETE r
                """
                session.run(rel_query, {'dataset_name': dataset_name})
                
                # Delete entities
                entity_query = """
                MATCH (e:Entity)
                WHERE e.dataset = $dataset_name
                DELETE e
                """
                session.run(entity_query, {'dataset_name': dataset_name})
                
                # Delete ontology metadata
                ontology_query = """
                MATCH (o:Ontology)
                WHERE o.dataset = $dataset_name
                DELETE o
                """
                session.run(ontology_query, {'dataset_name': dataset_name})
            
            logger.info(f"Successfully cleared dataset: {dataset_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear dataset {dataset_name}: {e}")
            return False
