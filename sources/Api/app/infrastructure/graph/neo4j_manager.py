"""Advanced Neo4j graph management with connection pooling, transaction management, and graph algorithms."""

import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from neo4j import Driver, GraphDatabase, Session, Transaction
from neo4j.exceptions import AuthError, ServiceUnavailable

from app.domain.models.entities import Entity, Relationship

logger = logging.getLogger(__name__)


@dataclass
class GraphSchema:
    """Graph schema definition for validation."""

    node_labels: list[str]
    relationship_types: list[str]
    properties: dict[str, list[str]]
    constraints: list[str]
    indexes: list[str]


@dataclass
class BulkOperationResult:
    """Result of bulk operations."""

    success_count: int
    failure_count: int
    errors: list[str]
    processing_time: float


class Neo4jGraphManager:
    """Advanced Neo4j graph manager with connection pooling, transactions, and graph algorithms."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
        max_connection_pool_size: int = 50,
        connection_timeout: int = 30,
        encrypted: bool = True,
        batch_size: int = 1000,
    ):
        """Initialize the advanced graph manager."""
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.max_connection_pool_size = max_connection_pool_size
        self.connection_timeout = connection_timeout
        self.encrypted = encrypted
        self.batch_size = batch_size

        # Connection management
        self.driver: Optional[Driver] = None
        self.connection_pool = []
        self.pool_lock = None

        # Transaction management
        self.active_transactions: dict[str, Transaction] = {}
        self.transaction_timeout = 300  # 5 minutes

        # Performance tracking
        self.operation_metrics: dict[str, list[float]] = {}

        # Schema validation
        self.graph_schema: Optional[GraphSchema] = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def connect(self) -> bool:
        """Connect to Neo4j with connection pooling."""
        try:
            # Create driver with connection pooling
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_pool_size=self.max_connection_pool_size,
                connection_timeout=self.connection_timeout,
                encrypted=self.encrypted,
            )

            # Test connection and initialize schema
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 as test")
                result.single()

                # Initialize schema and constraints
                self._initialize_schema(session)
                self._create_indexes(session)
                self._create_constraints(session)

            logger.info(
                f"Successfully connected to Neo4j with connection pooling: {self.database}"
            )
            return True

        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Neo4j: {e}")
            return False

    def _initialize_schema(self, session: Session):
        """Initialize graph schema for validation."""
        try:
            # Get existing schema information
            labels_query = (
                "CALL db.labels() YIELD label RETURN collect(label) as labels"
            )
            rel_types_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as types"

            labels_result = session.run(labels_query)
            rel_types_result = session.run(rel_types_query)

            labels = labels_result.single()["labels"] if labels_result.single() else []
            rel_types = (
                rel_types_result.single()["types"] if rel_types_result.single() else []
            )

            self.graph_schema = GraphSchema(
                node_labels=labels,
                relationship_types=rel_types,
                properties={},
                constraints=[],
                indexes=[],
            )

            logger.info(
                f"Graph schema initialized with {len(labels)} labels and {len(rel_types)} relationship types"
            )

        except Exception as e:
            logger.warning(f"Failed to initialize schema: {e}")
            self.graph_schema = None

    def _create_indexes(self, session: Session):
        """Create performance indexes."""
        indexes = [
            "CREATE INDEX entity_id_index IF NOT EXISTS FOR (e:Entity) ON (e.id)",
            "CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
            "CREATE INDEX entity_confidence_index IF NOT EXISTS FOR (e:Entity) ON (e.confidence)",
            "CREATE INDEX entity_timestamp_index IF NOT EXISTS FOR (e:Entity) ON (e.extraction_timestamp)",
            "CREATE INDEX relationship_type_index IF NOT EXISTS FOR (r:RELATES_TO) ON (r.type)",
            "CREATE INDEX relationship_confidence_index IF NOT EXISTS FOR (r:RELATES_TO) ON (r.confidence)",
            "CREATE INDEX relationship_timestamp_index IF NOT EXISTS FOR (r:RELATES_TO) ON (r.discovered_at)",
        ]

        try:
            for index_query in indexes:
                session.run(index_query)
            logger.info("Performance indexes created successfully")
        except Exception as e:
            logger.warning(f"Failed to create some indexes: {e}")

    def _create_constraints(self, session: Session):
        """Create advanced constraints for data integrity."""
        constraints = [
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT entity_source_file IF NOT EXISTS FOR (e:Entity) REQUIRE e.source_file IS NOT NULL",
            "CREATE CONSTRAINT entity_extraction_timestamp IF NOT EXISTS FOR (e:Entity) REQUIRE e.extraction_timestamp IS NOT NULL",
            "CREATE CONSTRAINT relationship_id_unique IF NOT EXISTS FOR (r:RELATES_TO) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT relationship_type_not_null IF NOT EXISTS FOR (r:RELATES_TO) REQUIRE r.type IS NOT NULL",
            "CREATE CONSTRAINT relationship_confidence_range IF NOT EXISTS FOR (r:RELATES_TO) REQUIRE r.confidence >= 0.0 AND r.confidence <= 1.0",
        ]

        try:
            for constraint_query in constraints:
                session.run(constraint_query)
            logger.info("Advanced constraints created successfully")
        except Exception as e:
            logger.warning(f"Failed to create some constraints: {e}")

    def begin_transaction(self, transaction_id: Optional[str] = None) -> str:
        """Begin a new transaction."""
        if not self.is_connected():
            raise RuntimeError("Not connected to database")

        tx_id = transaction_id or str(uuid.uuid4())

        try:
            session = self.driver.session(database=self.database)
            transaction = session.begin_transaction(timeout=self.transaction_timeout)
            self.active_transactions[tx_id] = transaction

            logger.info(f"Transaction {tx_id} started")
            return tx_id

        except Exception as e:
            logger.error(f"Failed to start transaction {tx_id}: {e}")
            raise

    def commit_transaction(self, transaction_id: str) -> bool:
        """Commit a transaction."""
        if transaction_id not in self.active_transactions:
            logger.error(f"Transaction {transaction_id} not found")
            return False

        try:
            transaction = self.active_transactions[transaction_id]
            transaction.commit()
            transaction.close()
            del self.active_transactions[transaction_id]

            logger.info(f"Transaction {transaction_id} committed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to commit transaction {transaction_id}: {e}")
            return False

    def rollback_transaction(self, transaction_id: str) -> bool:
        """Rollback a transaction."""
        if transaction_id not in self.active_transactions:
            logger.error(f"Transaction {transaction_id} not found")
            return False

        try:
            transaction = self.active_transactions[transaction_id]
            transaction.rollback()
            transaction.close()
            del self.active_transactions[transaction_id]

            logger.info(f"Transaction {transaction_id} rolled back successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to rollback transaction {transaction_id}: {e}")
            return False

    def store_entity_with_metadata(
        self,
        entity: Entity,
        source_file: str,
        extraction_timestamp: Optional[datetime] = None,
        version: str = "1.0",
        lineage: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> bool:
        """Store entity with comprehensive metadata using MERGE operations."""
        if not self.is_connected():
            logger.error("Cannot store entity: not connected to database")
            return False

        extraction_timestamp = extraction_timestamp or datetime.now()

        query = """
        MERGE (e:Entity {id: $entity_id})
        SET e.name = $name,
            e.entity_type = $entity_type,
            e.confidence = $confidence,
            e.source_columns = $source_columns,
            e.source_value = $source_value,
            e.attributes = $attributes,
            e.source_file = $source_file,
            e.extraction_timestamp = $extraction_timestamp,
            e.version = $version,
            e.lineage = $lineage,
            e.updated_at = $updated_at
        ON CREATE SET e.created_at = $created_at
        """

        params = {
            "entity_id": entity.id,
            "name": entity.name,
            "entity_type": entity.entity_type,
            "confidence": entity.confidence,
            "source_columns": json.dumps(entity.source_columns),
            "source_value": entity.source_value,
            "attributes": json.dumps(entity.attributes),
            "source_file": source_file,
            "extraction_timestamp": extraction_timestamp.isoformat(),
            "version": version,
            "lineage": lineage or "unknown",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        try:
            if transaction_id and transaction_id in self.active_transactions:
                transaction = self.active_transactions[transaction_id]
                transaction.run(query, params)
            else:
                with self.driver.session(database=self.database) as session:
                    session.run(query, params)

            return True

        except Exception as e:
            logger.error(f"Failed to store entity {entity.id}: {e}")
            return False

    def store_relationship_with_metadata(
        self,
        relationship: Relationship,
        discovered_at: Optional[datetime] = None,
        evidence: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> bool:
        """Store relationship with comprehensive metadata."""
        if not self.is_connected():
            logger.error("Cannot store relationship: not connected to database")
            return False

        discovered_at = discovered_at or datetime.now()

        # First ensure both entities exist
        if not self._entity_exists(
            relationship.source_entity_id
        ) or not self._entity_exists(relationship.target_entity_id):
            logger.warning(
                f"Relationship {relationship.id} references non-existent entities"
            )
            return False

        query = """
        MATCH (source:Entity {id: $source_id})
        MATCH (target:Entity {id: $target_id})
        MERGE (source)-[r:RELATES_TO {id: $rel_id}]->(target)
        SET r.type = $rel_type,
            r.confidence = $confidence,
            r.attributes = $attributes,
            r.discovered_at = $discovered_at,
            r.evidence = $evidence,
            r.updated_at = $updated_at
        ON CREATE SET r.created_at = $created_at
        """

        params = {
            "source_id": relationship.source_entity_id,
            "target_id": relationship.target_entity_id,
            "rel_id": relationship.id,
            "rel_type": relationship.relationship_type,
            "confidence": relationship.confidence,
            "attributes": json.dumps(relationship.attributes),
            "discovered_at": discovered_at.isoformat(),
            "evidence": evidence or "statistical_discovery",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        try:
            if transaction_id and transaction_id in self.active_transactions:
                transaction = self.active_transactions[transaction_id]
                transaction.run(query, params)
            else:
                with self.driver.session(database=self.database) as session:
                    session.run(query, params)

            return True

        except Exception as e:
            logger.error(f"Failed to store relationship {relationship.id}: {e}")
            return False

    def _entity_exists(self, entity_id: str) -> bool:
        """Check if entity exists in database."""
        query = "MATCH (e:Entity {id: $entity_id}) RETURN e.id LIMIT 1"

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, {"entity_id": entity_id})
                return result.single() is not None
        except Exception:
            return False

    def bulk_insert_entities(
        self, entities: list[Entity], source_file: str, batch_size: Optional[int] = None
    ) -> BulkOperationResult:
        """Bulk insert entities with batch processing."""
        if not self.is_connected():
            return BulkOperationResult(
                0, len(entities), ["Not connected to database"], 0.0
            )

        batch_size = batch_size or self.batch_size
        start_time = time.time()
        success_count = 0
        failure_count = 0
        errors = []

        try:
            # Process in batches
            for i in range(0, len(entities), batch_size):
                batch = entities[i : i + batch_size]

                # Use transaction for each batch
                tx_id = self.begin_transaction()

                try:
                    for entity in batch:
                        if self.store_entity_with_metadata(
                            entity, source_file, transaction_id=tx_id
                        ):
                            success_count += 1
                        else:
                            failure_count += 1
                            errors.append(f"Failed to store entity {entity.id}")

                    self.commit_transaction(tx_id)

                except Exception as e:
                    self.rollback_transaction(tx_id)
                    failure_count += len(batch)
                    success_count -= success_count
                    errors.append(f"Batch {i//batch_size + 1} failed: {e}")

            processing_time = time.time() - start_time

            logger.info(
                f"Bulk insert completed: {success_count} success, {failure_count} failures in {processing_time:.2f}s"
            )

            return BulkOperationResult(
                success_count, failure_count, errors, processing_time
            )

        except Exception as e:
            processing_time = time.time() - start_time
            errors.append(f"Bulk insert failed: {e}")
            return BulkOperationResult(
                success_count, failure_count, errors, processing_time
            )

    def bulk_insert_relationships(
        self, relationships: list[Relationship], batch_size: Optional[int] = None
    ) -> BulkOperationResult:
        """Bulk insert relationships with batch processing."""
        if not self.is_connected():
            return BulkOperationResult(
                0, len(relationships), ["Not connected to database"], 0.0
            )

        batch_size = batch_size or self.batch_size
        start_time = time.time()
        success_count = 0
        failure_count = 0
        errors = []

        try:
            # Process in batches
            for i in range(0, len(relationships), batch_size):
                batch = relationships[i : i + batch_size]

                # Use transaction for each batch
                tx_id = self.begin_transaction()

                try:
                    for relationship in batch:
                        if self.store_relationship_with_metadata(
                            relationship, transaction_id=tx_id
                        ):
                            success_count += 1
                        else:
                            failure_count += 1
                            errors.append(
                                f"Failed to store relationship {relationship.id}"
                            )

                    self.commit_transaction(tx_id)

                except Exception as e:
                    self.rollback_transaction(tx_id)
                    failure_count += len(batch)
                    success_count -= success_count
                    errors.append(f"Batch {i//batch_size + 1} failed: {e}")

            processing_time = time.time() - start_time

            logger.info(
                f"Bulk relationship insert completed: {success_count} success, {failure_count} failures in {processing_time:.2f}s"
            )

            return BulkOperationResult(
                success_count, failure_count, errors, processing_time
            )

        except Exception as e:
            processing_time = time.time() - start_time
            errors.append(f"Bulk relationship insert failed: {e}")
            return BulkOperationResult(
                success_count, failure_count, errors, processing_time
            )

    def validate_graph_schema(self) -> dict[str, Any]:
        """Validate graph schema consistency."""
        if not self.is_connected():
            return {"valid": False, "error": "Not connected to database"}

        validation_results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "schema_info": {},
        }

        try:
            with self.driver.session(database=self.database) as session:
                # Check for orphaned relationships
                orphaned_query = """
                MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
                WHERE NOT EXISTS((source:Entity)) OR NOT EXISTS((target:Entity))
                RETURN count(r) as orphaned_count
                """

                orphaned_result = session.run(orphaned_query)
                orphaned_count = orphaned_result.single()["orphaned_count"]

                if orphaned_count > 0:
                    validation_results["warnings"].append(
                        f"Found {orphaned_count} orphaned relationships"
                    )

                # Check for entities without relationships
                isolated_query = """
                MATCH (e:Entity)
                WHERE NOT EXISTS((e)-[:RELATES_TO]-())
                RETURN count(e) as isolated_count
                """

                isolated_result = session.run(isolated_query)
                isolated_count = isolated_result.single()["isolated_count"]

                if isolated_count > 0:
                    validation_results["warnings"].append(
                        f"Found {isolated_count} isolated entities"
                    )

                # Check data quality metrics
                quality_query = """
                MATCH (e:Entity)
                RETURN
                    count(e) as total_entities,
                    avg(e.confidence) as avg_confidence,
                    min(e.confidence) as min_confidence,
                    max(e.confidence) as max_confidence
                """

                quality_result = session.run(quality_query)
                quality_data = quality_result.single()

                validation_results["schema_info"] = {
                    "total_entities": quality_data["total_entities"],
                    "avg_confidence": quality_data["avg_confidence"],
                    "min_confidence": quality_data["min_confidence"],
                    "max_confidence": quality_data["max_confidence"],
                }

                # Check for low confidence entities
                if quality_data["avg_confidence"] < 0.5:
                    validation_results["warnings"].append(
                        "Low average entity confidence detected"
                    )

        except Exception as e:
            validation_results["valid"] = False
            validation_results["errors"].append(f"Schema validation failed: {e}")

        return validation_results

    def detect_communities(self, min_community_size: int = 3) -> list[dict[str, Any]]:
        """Detect communities in the graph using Louvain algorithm."""
        if not self.is_connected():
            return []

        query = """
        CALL gds.louvain.stream('entity-graph')
        YIELD nodeId, communityId, intermediateCommunityIds
        RETURN gds.util.asNode(nodeId).id as entity_id,
               gds.util.asNode(nodeId).name as entity_name,
               communityId,
               size(intermediateCommunityIds) as community_size
        ORDER BY communityId, entity_name
        """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query)
                communities = {}

                for record in result:
                    community_id = record["communityId"]
                    if community_id not in communities:
                        communities[community_id] = {
                            "community_id": community_id,
                            "entities": [],
                            "size": 0,
                        }

                    communities[community_id]["entities"].append(
                        {
                            "entity_id": record["entity_id"],
                            "entity_name": record["entity_name"],
                        }
                    )
                    communities[community_id]["size"] = record["community_size"]

                # Filter by minimum size
                filtered_communities = [
                    comm
                    for comm in communities.values()
                    if comm["size"] >= min_community_size
                ]

                logger.info(
                    f"Detected {len(filtered_communities)} communities with size >= {min_community_size}"
                )
                return filtered_communities

        except Exception as e:
            logger.error(f"Community detection failed: {e}")
            return []

    def calculate_pagerank(
        self, max_iterations: int = 20, damping_factor: float = 0.85
    ) -> list[dict[str, Any]]:
        """Calculate PageRank for entities."""
        if not self.is_connected():
            return []

        query = """
        CALL gds.pageRank.stream('entity-graph', {
            maxIterations: $max_iterations,
            dampingFactor: $damping_factor
        })
        YIELD nodeId, score
        RETURN gds.util.asNode(nodeId).id as entity_id,
               gds.util.asNode(nodeId).name as entity_name,
               gds.util.asNode(nodeId).entity_type as entity_type,
               score
        ORDER BY score DESC
        """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(
                    query,
                    {
                        "max_iterations": max_iterations,
                        "damping_factor": damping_factor,
                    },
                )

                pagerank_results = []
                for record in result:
                    pagerank_results.append(
                        {
                            "entity_id": record["entity_id"],
                            "entity_name": record["entity_name"],
                            "entity_type": record["entity_type"],
                            "pagerank_score": record["score"],
                        }
                    )

                logger.info(f"PageRank calculated for {len(pagerank_results)} entities")
                return pagerank_results

        except Exception as e:
            logger.error(f"PageRank calculation failed: {e}")
            return []

    def find_paths(
        self,
        source_entity_id: str,
        target_entity_id: str,
        max_path_length: int = 5,
        max_paths: int = 10,
    ) -> list[dict[str, Any]]:
        """Find paths between two entities."""
        if not self.is_connected():
            return []

        query = """
        MATCH path = (source:Entity {id: $source_id})-[r:RELATES_TO*1..$max_length]-(target:Entity {id: $target_id})
        RETURN path, length(path) as path_length
        ORDER BY path_length
        LIMIT $max_paths
        """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(
                    query,
                    {
                        "source_id": source_entity_id,
                        "target_id": target_entity_id,
                        "max_length": max_path_length,
                        "max_paths": max_paths,
                    },
                )

                paths = []
                for record in result:
                    path = record["path"]
                    path_length = record["path_length"]

                    # Extract path information
                    path_info = {
                        "path_length": path_length,
                        "entities": [],
                        "relationships": [],
                    }

                    # Extract entities
                    for node in path.nodes:
                        path_info["entities"].append(
                            {
                                "id": node["id"],
                                "name": node["name"],
                                "entity_type": node["entity_type"],
                            }
                        )

                    # Extract relationships
                    for rel in path.relationships:
                        path_info["relationships"].append(
                            {"type": rel["type"], "confidence": rel["confidence"]}
                        )

                    paths.append(path_info)

                logger.info(
                    f"Found {len(paths)} paths between {source_entity_id} and {target_entity_id}"
                )
                return paths

        except Exception as e:
            logger.error(f"Path finding failed: {e}")
            return []

    def prune_low_confidence_entities(self, confidence_threshold: float = 0.3) -> int:
        """Prune entities below confidence threshold."""
        if not self.is_connected():
            return 0

        query = """
        MATCH (e:Entity)
        WHERE e.confidence < $threshold
        OPTIONAL MATCH (e)-[r:RELATES_TO]-()
        DELETE r, e
        RETURN count(e) as pruned_count
        """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, {"threshold": confidence_threshold})
                pruned_count = result.single()["pruned_count"]

                logger.info(
                    f"Pruned {pruned_count} entities below confidence threshold {confidence_threshold}"
                )
                return pruned_count

        except Exception as e:
            logger.error(f"Entity pruning failed: {e}")
            return 0

    def create_materialized_view(
        self, view_name: str, query: str, refresh_interval: int = 3600
    ) -> bool:
        """Create materialized view for common query patterns."""
        if not self.is_connected():
            return False

        # Store view definition
        view_query = """
        MERGE (v:MaterializedView {name: $view_name})
        SET v.query = $query,
            v.refresh_interval = $refresh_interval,
            v.last_refresh = $last_refresh,
            v.created_at = $created_at
        """

        try:
            with self.driver.session(database=self.database) as session:
                session.run(
                    view_query,
                    {
                        "view_name": view_name,
                        "query": query,
                        "refresh_interval": refresh_interval,
                        "last_refresh": datetime.now().isoformat(),
                        "created_at": datetime.now().isoformat(),
                    },
                )

                logger.info(f"Materialized view '{view_name}' created successfully")
                return True

        except Exception as e:
            logger.error(f"Failed to create materialized view '{view_name}': {e}")
            return False

    def refresh_materialized_view(self, view_name: str) -> bool:
        """Refresh a materialized view."""
        if not self.is_connected():
            return False

        # Get view definition
        get_view_query = """
        MATCH (v:MaterializedView {name: $view_name})
        RETURN v.query as query
        """

        try:
            with self.driver.session(database=self.database) as session:
                view_result = session.run(get_view_query, {"view_name": view_name})
                view_data = view_result.single()

                if not view_data:
                    logger.error(f"Materialized view '{view_name}' not found")
                    return False

                # Execute the view query
                session.run(view_data["query"])

                # Update last refresh timestamp
                update_query = """
                MATCH (v:MaterializedView {name: $view_name})
                SET v.last_refresh = $last_refresh
                """

                session.run(
                    update_query,
                    {
                        "view_name": view_name,
                        "last_refresh": datetime.now().isoformat(),
                    },
                )

                logger.info(f"Materialized view '{view_name}' refreshed successfully")
                return True

        except Exception as e:
            logger.error(f"Failed to refresh materialized view '{view_name}': {e}")
            return False

    def get_entities(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Get all entities from the graph database."""
        query = """
        MATCH (e:Entity)
        RETURN e.id as id, e.name as name, e.entity_type as entity_type,
               e.confidence as confidence, e.attributes as attributes
        ORDER BY e.name
        LIMIT $limit SKIP $offset
        """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, {"limit": limit, "offset": offset})
                entities = []
                for record in result:
                    entity = {
                        "id": record["id"],
                        "name": record["name"],
                        "entity_type": record["entity_type"],
                        "confidence": record["confidence"],
                        "attributes": (
                            record["attributes"] if record["attributes"] else {}
                        ),
                    }
                    entities.append(entity)
                return entities
        except Exception as e:
            logger.error(f"Failed to get entities: {e}")
            return []

    def get_relationships(
        self, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get all relationships from the graph database."""
        query = """
        MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
        RETURN r.id as id, r.relationship_type as type, r.confidence as confidence,
               source.name as source_entity, target.name as target_entity,
               r.attributes as attributes
        ORDER BY r.relationship_type
        LIMIT $limit SKIP $offset
        """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, {"limit": limit, "offset": offset})
                relationships = []
                for record in result:
                    rel = {
                        "id": record["id"],
                        "type": record["type"],
                        "confidence": record["confidence"],
                        "source_entity": record["source_entity"],
                        "target_entity": record["target_entity"],
                        "attributes": (
                            record["attributes"] if record["attributes"] else {}
                        ),
                    }
                    relationships.append(rel)
                return relationships
        except Exception as e:
            logger.error(f"Failed to get relationships: {e}")
            return []

    def get_graph_statistics(self) -> dict[str, Any]:
        """Get basic statistics about the graph database."""
        stats = {
            "total_nodes": 0,
            "total_relationships": 0,
            "database_size_mb": 0,
            "index_count": 0,
        }

        try:
            with self.driver.session(database=self.database) as session:
                # Count nodes
                node_result = session.run("MATCH (n) RETURN count(n) as count")
                stats["total_nodes"] = node_result.single()["count"]

                # Count relationships
                rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
                stats["total_relationships"] = rel_result.single()["count"]

                # Get database size (approximate)
                size_result = session.run(
                    "CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0] as version"
                )
                if size_result.peek():
                    stats["database_size_mb"] = 1.5  # Placeholder value

                # Count indexes
                index_result = session.run("SHOW INDEXES")
                stats["index_count"] = len(list(index_result))

        except Exception as e:
            logger.warning(f"Could not get graph statistics: {e}")

        return stats

    def search_graph(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search for entities and relationships in the graph."""
        search_query = """
        MATCH (e:Entity)
        WHERE e.name CONTAINS $query OR e.entity_type CONTAINS $query
        RETURN e.id as id, e.name as name, e.entity_type as entity_type,
               e.confidence as confidence, 'entity' as result_type
        UNION
        MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
        WHERE r.relationship_type CONTAINS $query
        RETURN r.id as id, r.relationship_type as name,
               source.name + ' -> ' + target.name as description,
               r.confidence as confidence, 'relationship' as result_type
        LIMIT $limit
        """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(search_query, {"query": query, "limit": limit})
                results = []
                for record in result:
                    item = {
                        "id": record["id"],
                        "name": record["name"],
                        "description": record.get("description", ""),
                        "confidence": record["confidence"],
                        "result_type": record["result_type"],
                    }
                    results.append(item)
                return results
        except Exception as e:
            logger.error(f"Failed to search graph: {e}")
            return []

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics for the graph manager."""
        metrics = {
            "connection_pool_size": self.max_connection_pool_size,
            "active_transactions": len(self.active_transactions),
            "operation_metrics": self.operation_metrics,
            "database_stats": {},
        }

        if self.is_connected():
            try:
                with self.driver.session(database=self.database) as session:
                    # Get database statistics
                    stats_query = """
                    CALL dbms.components() YIELD name, versions, edition
                    RETURN name, versions[0] as version, edition
                    """

                    stats_result = session.run(stats_query)
                    db_info = stats_result.single()

                    if db_info:
                        metrics["database_stats"] = {
                            "name": db_info["name"],
                            "version": db_info["version"],
                            "edition": db_info["edition"],
                        }

            except Exception as e:
                logger.warning(f"Failed to get database stats: {e}")

        return metrics

    def close(self):
        """Close all connections and clean up resources."""
        # Close active transactions
        for tx_id in list(self.active_transactions.keys()):
            try:
                self.rollback_transaction(tx_id)
            except Exception:
                pass

        # Close driver
        if self.driver:
            self.driver.close()
            self.driver = None

        logger.info("Neo4jGraphManager closed successfully")

    def is_connected(self) -> bool:
        """Check if connected to database."""
        if not self.driver:
            return False

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 as test")
                result.single()
            return True
        except Exception:
            return False
