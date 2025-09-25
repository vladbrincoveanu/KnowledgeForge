"""Native PostgreSQL metadata store using psycopg2 for direct database operations."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool

from app.domain.models.recommendations import (
    EdgeRecommendation,
    NodeRecommendation,
    RecommendationSession,
)

logger = logging.getLogger(__name__)


class PostgreSQLMetadataStore:
    """PostgreSQL-based metadata store for KnowledgeForge."""

    def __init__(self, database_url: str = None, config: Dict[str, Any] = None):
        """Initialize PostgreSQL metadata store.
        
        Args:
            database_url: PostgreSQL connection string (overrides config)
            config: Configuration dictionary with database settings
        """
        self.database_url = database_url
        self.config = config or {}
        
        # Initialize connection pool
        self.connection_pool = None
        try:
            if database_url:
                self.connection_pool = SimpleConnectionPool(
                    1, 10, database_url
                )
            else:
                # Use config-based connection
                if hasattr(self.config, 'neo4j'):
                    # If it's a Config object, use Docker PostgreSQL defaults
                    self.connection_pool = SimpleConnectionPool(
                        1, 10,
                        host="localhost",
                        port=5432,
                        database="knowledgeforge",
                        user="knowledgeforge",
                        password="knowledgeforge123"
                    )
                else:
                    # If it's a dict, use .get() method
                    self.connection_pool = SimpleConnectionPool(
                        1, 10,
                        host=self.config.get("host", "localhost"),
                        port=self.config.get("port", 5432),
                        database=self.config.get("database", "knowledgeforge"),
                        user=self.config.get("user", "knowledgeforge"),
                        password=self.config.get("password", "knowledgeforge123")
                    )
            logger.info("PostgreSQL connection pool initialized successfully")
        except Exception as e:
            logger.warning(f"PostgreSQL not available, running in mock mode: {e}")
            self.connection_pool = None

        # In-memory storage for mock mode operations
        self._mock_sessions: dict[str, RecommendationSession] = {}
        self._mock_node_recommendations: dict[str, list[dict[str, Any]]] = {}
        self._mock_edge_recommendations: dict[str, list[dict[str, Any]]] = {}
        self._mock_extraction_runs: dict[str, dict[str, Any]] = {}

    def create_extraction_run(
        self, task_id: str, status: str = "pending", metadata: Dict[str, Any] | None = None
    ) -> None:
        """Create or update an extraction run entry."""
        payload = metadata or {}
        try:
            if self.connection_pool:
                conn = self.connection_pool.getconn()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO extraction_runs (id, status, metadata, created_at)
                            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                            ON CONFLICT (id) DO UPDATE SET
                                status = EXCLUDED.status,
                                metadata = EXCLUDED.metadata,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            (task_id, status, Json(payload)),
                        )
                    conn.commit()
                    logger.info(
                        "Registered extraction run %s with status %s in PostgreSQL",
                        task_id,
                        status,
                    )
                finally:
                    self.connection_pool.putconn(conn)
            else:
                self._mock_extraction_runs[task_id] = {
                    "id": task_id,
                    "status": status,
                    "metadata": payload,
                    "created_at": datetime.now().isoformat(),
                }
                logger.info("Registered extraction run %s (mock mode)", task_id)
        except Exception as e:
            logger.error(f"Failed to create extraction run: {e}")
            raise

    def register_file(self, file_path: str, file_name: str, file_size: int, 
                     file_type: str, checksum: str = None) -> str:
        """Register a new file with checksum calculation."""
        try:
            if not checksum:
                checksum = self._calculate_file_checksum(file_path)
            
            file_id = str(hashlib.sha256(f"{file_name}{checksum}".encode()).hexdigest()[:16])
            
            if self.connection_pool:
                # Store in PostgreSQL
                conn = self.connection_pool.getconn()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO files (id, file_path, file_name, file_size, file_type, checksum, processing_status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO UPDATE SET
                                file_path = EXCLUDED.file_path,
                                file_name = EXCLUDED.file_name,
                                file_size = EXCLUDED.file_size,
                                file_type = EXCLUDED.file_type,
                                checksum = EXCLUDED.checksum,
                                updated_at = CURRENT_TIMESTAMP
                        """, (file_id, file_path, file_name, file_size, file_type, checksum, 'uploaded'))
                    conn.commit()
                    logger.info(f"Registered file '{file_name}' with ID {file_id} in PostgreSQL")
                finally:
                    self.connection_pool.putconn(conn)
            else:
                # Mock mode - just log the registration
                logger.info(f"Registered file '{file_name}' with ID {file_id} (mock mode)")
            
            return file_id

        except Exception as e:
            logger.error(f"Failed to register file: {e}")
            raise


    def add_user_feedback(self, entity_id: str = None, relationship_id: str = None,
                         feedback_type: str = "correction", feedback_value: str = "",
                         confidence_adjustment: float = 0.0, user_id: str = None,
                         feedback_source: str = "api") -> str:
        """Add user feedback for entities or relationships."""
        try:
            feedback_id = str(hashlib.sha256(
                f"{entity_id}{relationship_id}{feedback_type}{feedback_value}{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16])
            
            if self.connection_pool:
                conn = self.connection_pool.getconn()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO user_feedback (id, entity_id, relationship_id, feedback_type, 
                                                     feedback_value, confidence_adjustment, user_id, feedback_source)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (feedback_id, entity_id, relationship_id, feedback_type, 
                              feedback_value, confidence_adjustment, user_id, feedback_source))
                        conn.commit()
                        logger.info(f"Added user feedback with ID {feedback_id} to PostgreSQL")
                finally:
                    self.connection_pool.putconn(conn)
            else:
                logger.info(f"Added user feedback with ID {feedback_id} (mock mode)")
            
            return feedback_id
            
        except Exception as e:
            logger.error(f"Failed to add user feedback: {e}")
            raise

    def get_database_info(self) -> Dict[str, Any]:
        """Get database information and statistics."""
        try:
            if self.connection_pool:
                # Test actual connection and get real statistics
                conn = self.connection_pool.getconn()
                try:
                    with conn.cursor() as cursor:
                        # Test connection
                        cursor.execute("SELECT 1")
                        cursor.fetchone()
                        
                        # Get actual record counts
                        cursor.execute("SELECT COUNT(*) FROM files")
                        files_count = cursor.fetchone()[0]
                        
                        cursor.execute("SELECT COUNT(*) FROM extraction_runs")
                        extraction_runs_count = cursor.fetchone()[0]
                        
                        cursor.execute("SELECT COUNT(*) FROM user_feedback")
                        feedback_count = cursor.fetchone()[0]
                        
                        cursor.execute("SELECT COUNT(*) FROM system_metrics")
                        metrics_count = cursor.fetchone()[0]
                        
                    return {
                        "database_type": "PostgreSQL",
                        "connection_status": "connected",
                        "database_name": "knowledgeforge",
                        "tables": ["files", "extraction_runs", "user_feedback", "system_metrics"],
                        "record_count": {
                            "files": files_count,
                            "extraction_runs": extraction_runs_count,
                            "user_feedback": feedback_count,
                            "system_metrics": metrics_count
                        }
                    }
                finally:
                    self.connection_pool.putconn(conn)
            else:
                return {
                    "database_type": "PostgreSQL",
                    "connection_status": "disconnected",
                    "error": "No connection pool available"
                }
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {
                "database_type": "PostgreSQL",
                "connection_status": "error",
                "error": str(e)
            }

    async def find_similar_datasets(
        self, columns: List[str], domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return datasets with overlapping column names (best effort)."""

        if not columns:
            return []

        if self.connection_pool:
            conn = None
            try:
                conn = self.connection_pool.getconn()
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        SELECT dataset_name, dataset_id, overlap_score
                        FROM dataset_similarities
                        WHERE column_name = ANY(%s)
                        ORDER BY overlap_score DESC
                        LIMIT 10
                        """,
                        (columns,),
                    )
                    rows = cursor.fetchall() or []
                    return [dict(row) for row in rows]
            except Exception as exc:
                logger.debug("Similarity lookup failed: %s", exc)
            finally:
                if conn:
                    self.connection_pool.putconn(conn)

        # Mock or fallback path
        suggestions: List[Dict[str, Any]] = []
        for column in columns[:5]:
            suggestions.append(
                {
                    "dataset_name": f"Synthetic match for {column}",
                    "dataset_id": f"mock-{column}",
                    "overlap_score": 0.2,
                    "column_name": column,
                    "domain": domain,
                }
            )
        return suggestions

    async def get_relationship_patterns(
        self, entity_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Return historical relationship patterns for given entity types."""

        if not entity_types:
            return []

        if self.connection_pool:
            conn = None
            try:
                conn = self.connection_pool.getconn()
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        SELECT source_type, target_type, relationship_type, frequency
                        FROM relationship_patterns
                        WHERE source_type = ANY(%s) OR target_type = ANY(%s)
                        ORDER BY frequency DESC
                        LIMIT 25
                        """,
                        (entity_types, entity_types),
                    )
                    rows = cursor.fetchall() or []
                    return [dict(row) for row in rows]
            except Exception as exc:
                logger.debug("Relationship pattern lookup failed: %s", exc)
            finally:
                if conn:
                    self.connection_pool.putconn(conn)

        return []

    def complete_extraction_run(self, task_id: str, status: str = "completed",
                              metadata: Dict[str, Any] = None):
        """Mark an extraction run as completed."""
        try:
            if self.connection_pool:
                conn = self.connection_pool.getconn()
                try:
                    with conn.cursor() as cursor:
                        # Update extraction run status
                        cursor.execute("""
                            UPDATE extraction_runs 
                            SET status = %s, 
                                completed_at = CURRENT_TIMESTAMP,
                                metadata = %s
                            WHERE id = %s
                        """, (status, Json(metadata or {}), task_id))
                        
                        # If this is a new extraction run, insert it
                        if cursor.rowcount == 0:
                            cursor.execute("""
                                INSERT INTO extraction_runs (id, status, metadata, completed_at)
                                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                            """, (task_id, status, Json(metadata or {})))
                        
                        conn.commit()
                        logger.info(f"Marked extraction run {task_id} as {status} in PostgreSQL")
                finally:
                    self.connection_pool.putconn(conn)
            else:
                existing = self._mock_extraction_runs.get(task_id, {})
                self._mock_extraction_runs[task_id] = {
                    **existing,
                    "id": task_id,
                    "status": status,
                    "metadata": metadata or existing.get("metadata", {}),
                    "completed_at": datetime.now().isoformat(),
                }
                logger.info(f"Marked extraction run {task_id} as {status} (mock mode)")
        except Exception as e:
            logger.error(f"Failed to complete extraction run: {e}")
            raise

    def get_extraction_run(self, task_id: str) -> Optional[dict[str, Any]]:
        """Retrieve stored metadata for an extraction run."""
        try:
            if self.connection_pool:
                conn = self.connection_pool.getconn()
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute(
                            """
                            SELECT id, status, metadata, created_at, completed_at
                            FROM extraction_runs
                            WHERE id = %s
                            LIMIT 1
                            """,
                            (task_id,),
                        )
                        row = cursor.fetchone()
                        if row:
                            return dict(row)
                finally:
                    self.connection_pool.putconn(conn)

            return self._mock_extraction_runs.get(task_id)

        except Exception as e:
            logger.error(f"Failed to fetch extraction run {task_id}: {e}")
            return None

    async def create_recommendation_session(self, session: RecommendationSession):
        """Create a new recommendation session."""
        session = session.model_copy(deep=True)
        session_id = str(session.id)

        for node in session.node_recommendations:
            node.session_id = session.id
        for edge in session.edge_recommendations:
            edge.session_id = session.id

        try:
            if self.connection_pool:
                conn = self.connection_pool.getconn()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO recommendation_sessions (id, task_id, status, metadata)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (id) DO UPDATE SET
                                status = EXCLUDED.status,
                                metadata = EXCLUDED.metadata,
                                generated_at = CURRENT_TIMESTAMP
                            """,
                            (
                                session_id,
                                session.task_id,
                                session.status,
                                Json(session.metadata or {}),
                            ),
                        )

                        for node in session.node_recommendations:
                            cursor.execute(
                                """
                                INSERT INTO node_recommendations (
                                    id, session_id, recommended_name, entity_type,
                                    confidence_score, reasoning, source_columns,
                                    llm_metadata, user_feedback
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    recommended_name = EXCLUDED.recommended_name,
                                    entity_type = EXCLUDED.entity_type,
                                    confidence_score = EXCLUDED.confidence_score,
                                    reasoning = EXCLUDED.reasoning,
                                    source_columns = EXCLUDED.source_columns,
                                    llm_metadata = EXCLUDED.llm_metadata
                                """,
                                (
                                    str(node.id),
                                    session_id,
                                    node.recommended_name,
                                    node.entity_type,
                                    round(float(node.confidence_score or 0.0), 4),
                                    node.reasoning,
                                    node.source_columns or [],
                                    Json(node.llm_metadata or {}),
                                    node.user_feedback,
                                ),
                            )

                        for edge in session.edge_recommendations:
                            cursor.execute(
                                """
                                INSERT INTO edge_recommendations (
                                    id, session_id, source_node_id, target_node_id,
                                    relationship_type, confidence_score, reasoning,
                                    connection_evidence, user_feedback
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (id) DO UPDATE SET
                                    relationship_type = EXCLUDED.relationship_type,
                                    confidence_score = EXCLUDED.confidence_score,
                                    reasoning = EXCLUDED.reasoning,
                                    connection_evidence = EXCLUDED.connection_evidence
                                """,
                                (
                                    str(edge.id),
                                    session_id,
                                    str(edge.source_node_id),
                                    str(edge.target_node_id),
                                    edge.relationship_type,
                                    round(float(edge.confidence_score or 0.0), 4),
                                    edge.reasoning,
                                    Json(edge.connection_evidence or {}),
                                    edge.user_feedback,
                                ),
                            )

                    conn.commit()
                    logger.info(
                        "Created recommendation session %s for task %s",
                        session_id,
                        session.task_id,
                    )
                finally:
                    self.connection_pool.putconn(conn)
            else:
                logger.info(
                    "Created recommendation session %s for task %s (mock mode)",
                    session_id,
                    session.task_id,
                )

            self._mock_sessions[session.task_id] = session
            self._mock_node_recommendations[session_id] = [
                node.model_dump(mode="python") for node in session.node_recommendations
            ]
            self._mock_edge_recommendations[session_id] = [
                edge.model_dump(mode="python") for edge in session.edge_recommendations
            ]

        except Exception as e:
            logger.error(f"Failed to create recommendation session: {e}")
            raise

    async def get_recommendation_session(
        self, task_id: str
    ) -> Optional[RecommendationSession]:
        """Get the latest recommendation session for a task."""
        try:
            if self.connection_pool:
                conn = self.connection_pool.getconn()
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute(
                            """
                            SELECT *
                            FROM recommendation_sessions
                            WHERE task_id = %s
                            ORDER BY generated_at DESC
                            LIMIT 1
                            """,
                            (task_id,),
                        )
                        session_row = cursor.fetchone()
                        if not session_row:
                            return self._mock_sessions.get(task_id)

                        session = RecommendationSession(**session_row)

                        cursor.execute(
                            """
                            SELECT * FROM node_recommendations
                            WHERE session_id = %s
                            ORDER BY confidence_score DESC NULLS LAST
                            """,
                            (str(session.id),),
                        )
                        node_rows = cursor.fetchall()
                        session.node_recommendations = [
                            self._build_node_recommendation(dict(row)) for row in node_rows
                        ]

                        cursor.execute(
                            """
                            SELECT * FROM edge_recommendations
                            WHERE session_id = %s
                            ORDER BY confidence_score DESC NULLS LAST
                            """,
                            (str(session.id),),
                        )
                        edge_rows = cursor.fetchall()
                        session.edge_recommendations = [
                            self._build_edge_recommendation(dict(row)) for row in edge_rows
                        ]

                        return session
                finally:
                    self.connection_pool.putconn(conn)

            return self._mock_sessions.get(task_id)

        except Exception as e:
            logger.error(f"Failed to get recommendation session: {e}")
            raise

    def _build_node_recommendation(self, row: dict[str, Any]) -> NodeRecommendation:
        metadata = row.get("llm_metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {"raw": metadata}

        source_columns = row.get("source_columns") or []
        if isinstance(source_columns, str):
            try:
                source_columns = json.loads(source_columns)
            except json.JSONDecodeError:
                source_columns = [source_columns]

        return NodeRecommendation(
            id=row["id"],
            session_id=row["session_id"],
            recommended_name=row.get("recommended_name", "Suggested Node"),
            entity_type=row.get("entity_type", "unknown"),
            confidence_score=float(row.get("confidence_score") or 0.0),
            reasoning=row.get("reasoning", ""),
            source_columns=source_columns,
            llm_metadata=metadata or {},
            user_feedback=row.get("user_feedback"),
            created_at=row.get("created_at", datetime.utcnow()),
        )

    def _build_edge_recommendation(self, row: dict[str, Any]) -> EdgeRecommendation:
        evidence = row.get("connection_evidence")
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except json.JSONDecodeError:
                evidence = {"raw": evidence}

        return EdgeRecommendation(
            id=row["id"],
            session_id=row["session_id"],
            source_node_id=row.get("source_node_id"),
            target_node_id=row.get("target_node_id"),
            relationship_type=row.get("relationship_type", "RELATED_TO"),
            confidence_score=float(row.get("confidence_score") or 0.0),
            reasoning=row.get("reasoning", ""),
            connection_evidence=evidence or {},
            user_feedback=row.get("user_feedback"),
            created_at=row.get("created_at", datetime.utcnow()),
        )

    async def update_recommendation_feedback(
        self,
        task_id: str,
        status: str,
        feedback_payload: dict[str, Any],
        node_updates: List[dict[str, Any]],
        edge_updates: List[dict[str, Any]],
    ) -> None:
        session = await self.get_recommendation_session(task_id)
        if not session:
            logger.warning(
                "Cannot update recommendation feedback – no session found for task %s",
                task_id,
            )
            return

        metadata_update = {"last_feedback": feedback_payload}

        if self.connection_pool:
            conn = self.connection_pool.getconn()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE recommendation_sessions
                        SET status = %s,
                            approved_at = CURRENT_TIMESTAMP,
                            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                        WHERE id = %s
                        """,
                        (
                            status,
                            Json(metadata_update),
                            str(session.id),
                        ),
                    )

                    for update in node_updates:
                        cursor.execute(
                            """
                            UPDATE node_recommendations
                            SET user_feedback = %s,
                                recommended_name = COALESCE(%s, recommended_name),
                                entity_type = COALESCE(%s, entity_type),
                                confidence_score = COALESCE(%s, confidence_score),
                                source_columns = COALESCE(%s, source_columns),
                                llm_metadata = COALESCE(llm_metadata, '{}'::jsonb) || %s::jsonb
                            WHERE id = %s AND session_id = %s
                            """,
                            (
                                update.get("decision"),
                                update.get("name"),
                                update.get("entity_type"),
                                update.get("confidence"),
                                update.get("source_columns"),
                                Json(update.get("metadata") or {}),
                                update.get("id"),
                                str(session.id),
                            ),
                        )

                    for update in edge_updates:
                        cursor.execute(
                            """
                            UPDATE edge_recommendations
                            SET user_feedback = %s,
                                relationship_type = COALESCE(%s, relationship_type),
                                confidence_score = COALESCE(%s, confidence_score),
                                connection_evidence = COALESCE(connection_evidence, '{}'::jsonb) || %s::jsonb,
                                reasoning = COALESCE(%s, reasoning)
                            WHERE id = %s AND session_id = %s
                            """,
                            (
                                update.get("decision"),
                                update.get("relationship_type"),
                                update.get("confidence"),
                                Json(update.get("metadata") or {}),
                                update.get("reasoning"),
                                update.get("id"),
                                str(session.id),
                            ),
                        )

                conn.commit()
            finally:
                self.connection_pool.putconn(conn)

        session.status = status
        session.approved_at = datetime.utcnow()
        session.metadata = {**(session.metadata or {}), **metadata_update}

        node_map = {str(node.id): node for node in session.node_recommendations}
        for update in node_updates:
            node = node_map.get(update.get("id"))
            if not node:
                continue
            if update.get("name"):
                node.recommended_name = update["name"]
            if update.get("entity_type"):
                node.entity_type = update["entity_type"]
            if update.get("confidence") is not None:
                node.confidence_score = float(update["confidence"])
            if update.get("source_columns"):
                node.source_columns = update["source_columns"]
            node.user_feedback = update.get("decision", node.user_feedback)
            node.llm_metadata = node.llm_metadata or {}
            node.llm_metadata.setdefault("human_feedback", {}).update(
                update.get("metadata", {}).get("human_feedback", {})
            )

        edge_map = {str(edge.id): edge for edge in session.edge_recommendations}
        for update in edge_updates:
            edge = edge_map.get(update.get("id"))
            if not edge:
                continue
            if update.get("relationship_type"):
                edge.relationship_type = update["relationship_type"]
            if update.get("confidence") is not None:
                edge.confidence_score = float(update["confidence"])
            if update.get("reasoning"):
                edge.reasoning = update["reasoning"]
            edge.user_feedback = update.get("decision", edge.user_feedback)
            edge.connection_evidence = edge.connection_evidence or {}
            edge.connection_evidence.setdefault("human_feedback", {}).update(
                update.get("metadata", {}).get("human_feedback", {})
            )

        self._mock_sessions[task_id] = session
        self._mock_node_recommendations[str(session.id)] = [
            node.model_dump(mode="python") for node in session.node_recommendations
        ]
        self._mock_edge_recommendations[str(session.id)] = [
            edge.model_dump(mode="python") for edge in session.edge_recommendations
        ]

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
        if hasattr(self, 'connection_pool'):
            self.connection_pool.closeall()
            logger.info("PostgreSQL connection pool closed")


# Backward compatibility alias
MetadataStore = PostgreSQLMetadataStore
