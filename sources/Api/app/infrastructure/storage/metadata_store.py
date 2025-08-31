"""Advanced metadata store module using DuckDB for fast analytical queries and comprehensive metadata tracking."""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class QualityRule:
    """Data quality rule definition."""

    rule_id: str
    rule_name: str
    rule_type: str  # 'threshold', 'pattern', 'completeness', 'consistency'
    field: str
    condition: str
    threshold: Optional[float] = None
    severity: str = "warning"  # 'info', 'warning', 'error', 'critical'
    description: str = ""


@dataclass
class DriftMetrics:
    """Data drift detection metrics."""

    field_name: str
    baseline_mean: float
    current_mean: float
    drift_score: float
    drift_detected: bool
    confidence: float
    detected_at: datetime


class AdvancedMetadataStore:
    """Advanced metadata store using DuckDB for fast analytical queries and comprehensive tracking."""

    def __init__(self, db_path: str = ":memory:", enable_audit_logging: bool = True):
        """Initialize the advanced metadata store.

        Args:
            db_path: Path to DuckDB database file (use :memory: for in-memory)
            enable_audit_logging: Enable comprehensive audit logging
        """
        self.db_path = db_path
        self.enable_audit_logging = enable_audit_logging
        self.con = duckdb.connect(db_path)
        self._init_database()
        self._init_quality_rules()

    def _init_database(self):
        """Initialize the database with advanced table structure."""
        try:
            # Files table with checksums and processing history
            self.con.execute(
                """
                CREATE SEQUENCE IF NOT EXISTS files_id_seq START 1;
            """
            )
            self.con.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY DEFAULT nextval('files_id_seq'),
                    file_path TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size BIGINT NOT NULL,
                    checksum TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    uploaded_at TIMESTAMP NOT NULL,
                    last_processed_at TIMESTAMP,
                    processing_status TEXT DEFAULT 'pending',
                    metadata TEXT,
                    profile_data TEXT
                )
            """
            )

            # Extraction runs with comprehensive metadata
            self.con.execute(
                """
                CREATE SEQUENCE IF NOT EXISTS extraction_runs_id_seq START 1;
            """
            )
            self.con.execute(
                """
                CREATE TABLE IF NOT EXISTS extraction_runs (
                    id INTEGER PRIMARY KEY DEFAULT nextval('extraction_runs_id_seq'),
                    file_id INTEGER NOT NULL,
                    run_id TEXT UNIQUE NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    status TEXT DEFAULT 'running',
                    config TEXT,
                    results TEXT,
                    error_message TEXT,
                    model_version TEXT,
                    extraction_method TEXT,
                    FOREIGN KEY (file_id) REFERENCES files (id)
                )
            """
            )

            # Entities metadata with temporal tracking
            self.con.execute(
                """
                CREATE SEQUENCE IF NOT EXISTS entities_metadata_id_seq START 1;
            """
            )
            self.con.execute(
                """
                CREATE TABLE IF NOT EXISTS entities_metadata (
                    id INTEGER PRIMARY KEY DEFAULT nextval('entities_metadata_id_seq'),
                    entity_id TEXT NOT NULL,
                    file_id INTEGER NOT NULL,
                    extraction_run_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source_column TEXT,
                    source_value TEXT,
                    attributes TEXT,
                    quality_score REAL,
                    validation_status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    version INTEGER DEFAULT 1,
                    lineage TEXT,
                    FOREIGN KEY (file_id) REFERENCES files (id),
                    FOREIGN KEY (extraction_run_id) REFERENCES extraction_runs (run_id)
                )
            """
            )

            # Relationships metadata with evidence tracking
            self.con.execute(
                """
                CREATE SEQUENCE IF NOT EXISTS relationships_metadata_id_seq START 1;
            """
            )
            self.con.execute(
                """
                CREATE TABLE IF NOT EXISTS relationships_metadata (
                    id INTEGER PRIMARY KEY DEFAULT nextval('relationships_metadata_id_seq'),
                    relationship_id TEXT NOT NULL,
                    file_id INTEGER NOT NULL,
                    extraction_run_id TEXT NOT NULL,
                    source_entity_id TEXT NOT NULL,
                    target_entity_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    attributes TEXT,
                    source_columns TEXT,
                    evidence TEXT,
                    discovery_method TEXT,
                    quality_score REAL,
                    validation_status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    version INTEGER DEFAULT 1,
                    FOREIGN KEY (file_id) REFERENCES files (id),
                    FOREIGN KEY (extraction_run_id) REFERENCES extraction_runs (run_id)
                )
            """
            )

            # User feedback and validations
            self.con.execute(
                """
                CREATE SEQUENCE IF NOT EXISTS user_feedback_id_seq START 1;
            """
            )
            self.con.execute(
                """
                CREATE TABLE IF NOT EXISTS user_feedback (
                    id INTEGER PRIMARY KEY DEFAULT nextval('user_feedback_id_seq'),
                    entity_id TEXT,
                    relationship_id TEXT,
                    feedback_type TEXT NOT NULL, -- 'correction', 'validation', 'annotation'
                    feedback_value TEXT NOT NULL,
                    confidence_adjustment REAL,
                    user_id TEXT,
                    feedback_source TEXT, -- 'manual', 'api', 'ui'
                    feedback_at TIMESTAMP NOT NULL,
                    processed_at TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                )
            """
            )

            # Quality metrics with temporal tracking
            self.con.execute(
                """
                CREATE SEQUENCE IF NOT EXISTS quality_metrics_id_seq START 1;
            """
            )
            self.con.execute(
                """
                CREATE TABLE IF NOT EXISTS quality_metrics (
                    id INTEGER PRIMARY KEY DEFAULT nextval('quality_metrics_id_seq'),
                    file_id INTEGER NOT NULL,
                    extraction_run_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metric_type TEXT NOT NULL, -- 'entity', 'relationship', 'overall'
                    threshold_value REAL,
                    threshold_exceeded BOOLEAN,
                    calculated_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES files (id),
                    FOREIGN KEY (extraction_run_id) REFERENCES extraction_runs (run_id)
                )
            """
            )

            # Audit log for all operations
            if self.enable_audit_logging:
                self.con.execute(
                    """
                    CREATE SEQUENCE IF NOT EXISTS audit_log_id_seq START 1;
                """
                )
                self.con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY DEFAULT nextval('audit_log_id_seq'),
                        operation TEXT NOT NULL,
                        table_name TEXT NOT NULL,
                        record_id TEXT,
                        operation_type TEXT NOT NULL, -- 'CREATE', 'UPDATE', 'DELETE', 'QUERY'
                        user_id TEXT,
                        timestamp TIMESTAMP NOT NULL,
                        details TEXT,
                        ip_address TEXT,
                        session_id TEXT
                    )
                """
                )

            # Data quality rules
            self.con.execute(
                """
                CREATE SEQUENCE IF NOT EXISTS quality_rules_id_seq START 1;
            """
            )
            self.con.execute(
                """
                CREATE TABLE IF NOT EXISTS quality_rules (
                    id INTEGER PRIMARY KEY DEFAULT nextval('quality_rules_id_seq'),
                    rule_id TEXT UNIQUE NOT NULL,
                    rule_name TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    field TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    threshold_value REAL,
                    severity TEXT NOT NULL,
                    description TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """
            )

            # Baseline statistics for drift detection
            self.con.execute(
                """
                CREATE SEQUENCE IF NOT EXISTS baseline_statistics_id_seq START 1;
            """
            )
            self.con.execute(
                """
                CREATE TABLE IF NOT EXISTS baseline_statistics (
                    id INTEGER PRIMARY KEY DEFAULT nextval('baseline_statistics_id_seq'),
                    field_name TEXT NOT NULL,
                    entity_type TEXT,
                    baseline_mean REAL,
                    baseline_std REAL,
                    baseline_min REAL,
                    baseline_max REAL,
                    baseline_count INTEGER,
                    baseline_date DATE NOT NULL,
                    is_current BOOLEAN DEFAULT TRUE
                )
            """
            )

            # Create indexes for performance
            self.con.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_checksum ON files(checksum)"
            )
            self.con.execute(
                "CREATE INDEX IF NOT EXISTS idx_files_status ON files(processing_status)"
            )
            self.con.execute(
                "CREATE INDEX IF NOT EXISTS idx_extraction_runs_file ON extraction_runs(file_id)"
            )
            self.con.execute(
                "CREATE INDEX IF NOT EXISTS idx_entities_file ON entities_metadata(file_id)"
            )
            self.con.execute(
                "CREATE INDEX IF NOT EXISTS idx_entities_type ON entities_metadata(entity_type)"
            )
            self.con.execute(
                "CREATE INDEX IF NOT EXISTS idx_entities_confidence ON entities_metadata(confidence)"
            )
            self.con.execute(
                "CREATE INDEX IF NOT EXISTS idx_relationships_file ON relationships_metadata(file_id)"
            )
            self.con.execute(
                "CREATE INDEX IF NOT EXISTS idx_quality_metrics_file ON quality_metrics(file_id)"
            )
            self.con.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)"
            )

            logger.info("Advanced metadata database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize metadata database: {e}")
            raise

    def _init_quality_rules(self):
        """Initialize default quality rules."""
        default_rules = [
            QualityRule(
                rule_id="confidence_threshold",
                rule_name="Minimum Confidence Threshold",
                rule_type="threshold",
                field="confidence",
                condition="confidence >= 0.5",
                threshold=0.5,
                severity="warning",
                description="Entities and relationships should have confidence >= 0.5",
            ),
            QualityRule(
                rule_id="name_completeness",
                rule_name="Name Completeness",
                rule_type="completeness",
                field="name",
                condition="name IS NOT NULL AND name != ''",
                severity="error",
                description="Entity names must not be empty",
            ),
            QualityRule(
                rule_id="entity_type_validation",
                rule_name="Entity Type Validation",
                rule_type="pattern",
                field="entity_type",
                condition="entity_type IN ('PERSON', 'ORGANIZATION', 'LOCATION', 'PRODUCT', 'EVENT', 'OTHER')",
                severity="warning",
                description="Entity types should be from predefined set",
            ),
        ]

        for rule in default_rules:
            self._add_quality_rule(rule)

    def _audit_log(
        self,
        operation: str,
        table_name: str,
        record_id: Optional[str] = None,
        operation_type: str = "QUERY",
        user_id: Optional[str] = None,
        details: Optional[str] = None,
    ):
        """Log audit information."""
        if not self.enable_audit_logging:
            return

        try:
            self.con.execute(
                """
                INSERT INTO audit_log (operation, table_name, record_id, operation_type,
                                     user_id, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    operation,
                    table_name,
                    record_id,
                    operation_type,
                    user_id,
                    datetime.now().isoformat(),
                    details,
                ),
            )
        except Exception as e:
            logger.warning(f"Failed to log audit entry: {e}")

    def register_file(
        self,
        file_path: str,
        file_name: str,
        file_size: int,
        file_type: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """Register a new file with checksum calculation."""
        try:
            # Calculate file checksum
            checksum = self._calculate_file_checksum(file_path)

            # Check if file already exists
            existing = self.con.execute(
                """
                SELECT id FROM files WHERE checksum = ?
            """,
                (checksum,),
            ).fetchone()

            if existing:
                logger.info(f"File with checksum {checksum} already registered")
                return existing[0]

            # Register new file - ID will be auto-generated by sequence
            result = self.con.execute(
                """
                INSERT INTO files (file_path, file_name, file_size, checksum, file_type,
                                 uploaded_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """,
                (
                    file_path,
                    file_name,
                    file_size,
                    checksum,
                    file_type,
                    datetime.now().isoformat(),
                    json.dumps(metadata) if metadata else None,
                ),
            )

            file_id = result.fetchone()[0]

            self._audit_log(
                "File registration",
                "files",
                str(file_id),
                "CREATE",
                details=f"Registered file: {file_name}",
            )

            logger.info(f"Registered file '{file_name}' with ID {file_id}")
            return file_id

        except Exception as e:
            logger.error(f"Failed to register file: {e}")
            raise

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

    def start_extraction_run(
        self,
        file_id: int,
        run_id: str,
        config: dict[str, Any],
        model_version: str,
        extraction_method: str,
    ) -> str:
        """Start a new extraction run with comprehensive tracking."""
        try:
            self.con.execute(
                """
                INSERT INTO extraction_runs (file_id, run_id, started_at, config,
                                           model_version, extraction_method)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    file_id,
                    run_id,
                    datetime.now().isoformat(),
                    json.dumps(config),
                    model_version,
                    extraction_method,
                ),
            )

            # Update file status
            self.con.execute(
                """
                UPDATE files SET processing_status = 'processing', last_processed_at = ?
                WHERE id = ?
            """,
                (datetime.now().isoformat(), file_id),
            )

            self._audit_log(
                "Extraction run started",
                "extraction_runs",
                run_id,
                "CREATE",
                details=f"Started extraction for file ID {file_id}",
            )

            logger.info(f"Started extraction run {run_id} for file {file_id}")
            return run_id

        except Exception as e:
            logger.error(f"Failed to start extraction run: {e}")
            raise

    def complete_extraction_run(
        self,
        run_id: str,
        results: dict[str, Any],
        status: str = "completed",
        error_message: Optional[str] = None,
        performance_metrics: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Complete an extraction run with results and metrics."""
        try:
            self.con.execute(
                """
                UPDATE extraction_runs
                SET completed_at = ?, status = ?, results = ?, error_message = ?, performance_metrics = ?
                WHERE run_id = ?
            """,
                (
                    datetime.now().isoformat(),
                    status,
                    json.dumps(results),
                    error_message,
                    json.dumps(performance_metrics) if performance_metrics else None,
                    run_id,
                ),
            )

            # Update file status
            file_id = self.con.execute(
                """
                SELECT file_id FROM extraction_runs WHERE run_id = ?
            """,
                (run_id,),
            ).fetchone()[0]

            file_status = "completed" if status == "completed" else "failed"
            self.con.execute(
                """
                UPDATE files SET processing_status = ? WHERE id = ?
            """,
                (file_status, file_id),
            )

            self._audit_log(
                "Extraction run completed",
                "extraction_runs",
                run_id,
                "UPDATE",
                details=f"Completed with status: {status}",
            )

            logger.info(f"Completed extraction run {run_id} with status: {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to complete extraction run: {e}")
            return False

    def store_entities_with_metadata(
        self, file_id: int, extraction_run_id: str, entities: list[dict[str, Any]]
    ) -> bool:
        """Store entities with comprehensive metadata and quality scoring."""
        try:
            for entity in entities:
                # Calculate quality score
                quality_score = self._calculate_entity_quality_score(entity)

                # Store entity metadata
                self.con.execute(
                    """
                    INSERT INTO entities_metadata (
                        entity_id, file_id, extraction_run_id, name, entity_type, confidence,
                        source_column, source_value, attributes, quality_score, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        entity["id"],
                        file_id,
                        extraction_run_id,
                        entity["name"],
                        entity["entity_type"],
                        entity["confidence"],
                        entity.get("source_column"),
                        entity.get("source_value"),
                        json.dumps(entity.get("attributes", {})),
                        quality_score,
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                    ),
                )

            self._audit_log(
                "Entities stored",
                "entities_metadata",
                None,
                "CREATE",
                details=f"Stored {len(entities)} entities for run {extraction_run_id}",
            )

            logger.info(
                f"Stored {len(entities)} entities for extraction run {extraction_run_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store entities: {e}")
            return False

    def store_relationships_with_metadata(
        self, file_id: int, extraction_run_id: str, relationships: list[dict[str, Any]]
    ) -> bool:
        """Store relationships with comprehensive metadata and quality scoring."""
        try:
            for relationship in relationships:
                # Calculate quality score
                quality_score = self._calculate_relationship_quality_score(relationship)

                # Store relationship metadata
                self.con.execute(
                    """
                    INSERT INTO relationships_metadata (
                        relationship_id, file_id, extraction_run_id, source_entity_id,
                        target_entity_id, relationship_type, confidence, attributes,
                        source_columns, evidence, discovery_method, quality_score,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        relationship["id"],
                        file_id,
                        extraction_run_id,
                        relationship["source_entity_id"],
                        relationship["target_entity_id"],
                        relationship["relationship_type"],
                        relationship["confidence"],
                        json.dumps(relationship.get("attributes", {})),
                        json.dumps(relationship.get("source_columns", [])),
                        relationship.get("evidence", "statistical_discovery"),
                        relationship.get("discovery_method", "pattern_matching"),
                        quality_score,
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                    ),
                )

            self._audit_log(
                "Relationships stored",
                "relationships_metadata",
                None,
                "CREATE",
                details=f"Stored {len(relationships)} relationships for run {extraction_run_id}",
            )

            logger.info(
                f"Stored {len(relationships)} relationships for extraction run {extraction_run_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store relationships: {e}")
            return False

    def _calculate_entity_quality_score(self, entity: dict[str, Any]) -> float:
        """Calculate quality score for an entity based on multiple factors."""
        score = 0.0
        factors = 0

        # Confidence score (40% weight)
        if "confidence" in entity:
            score += entity["confidence"] * 0.4
            factors += 1

        # Name completeness (30% weight)
        if entity.get("name") and len(str(entity["name"]).strip()) > 0:
            score += 0.3
            factors += 1

        # Entity type validity (20% weight)
        valid_types = [
            "PERSON",
            "ORGANIZATION",
            "LOCATION",
            "PRODUCT",
            "EVENT",
            "OTHER",
        ]
        if entity.get("entity_type") in valid_types:
            score += 0.2
            factors += 1

        # Source information (10% weight)
        if entity.get("source_column") and entity.get("source_value"):
            score += 0.1
            factors += 1

        return score if factors > 0 else 0.0

    def _calculate_relationship_quality_score(
        self, relationship: dict[str, Any]
    ) -> float:
        """Calculate quality score for a relationship based on multiple factors."""
        score = 0.0
        factors = 0

        # Confidence score (50% weight)
        if "confidence" in relationship:
            score += relationship["confidence"] * 0.5
            factors += 1

        # Relationship type validity (30% weight)
        if (
            relationship.get("relationship_type")
            and len(str(relationship["relationship_type"]).strip()) > 0
        ):
            score += 0.3
            factors += 1

        # Source information (20% weight)
        if (
            relationship.get("source_columns")
            and len(relationship.get("source_columns", [])) > 0
        ):
            score += 0.2
            factors += 1

        return score if factors > 0 else 0.0

    def add_user_feedback(
        self,
        entity_id: Optional[str],
        relationship_id: Optional[str],
        feedback_type: str,
        feedback_value: str,
        confidence_adjustment: Optional[float] = None,
        user_id: Optional[str] = None,
        feedback_source: str = "manual",
    ) -> int:
        """Add user feedback for entities or relationships."""
        try:
            result = self.con.execute(
                """
                INSERT INTO user_feedback (
                    entity_id, relationship_id, feedback_type, feedback_value,
                    confidence_adjustment, user_id, feedback_source, feedback_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """,
                (
                    entity_id,
                    relationship_id,
                    feedback_type,
                    feedback_value,
                    confidence_adjustment,
                    user_id,
                    feedback_source,
                    datetime.now().isoformat(),
                ),
            )

            feedback_id = result.fetchone()[0]

            self._audit_log(
                "User feedback added",
                "user_feedback",
                str(feedback_id),
                "CREATE",
                user_id,
                details=f"Feedback type: {feedback_type}",
            )

            logger.info(f"Added user feedback with ID {feedback_id}")
            return feedback_id

        except Exception as e:
            logger.error(f"Failed to add user feedback: {e}")
            raise

    def _add_quality_rule(self, rule: QualityRule) -> bool:
        """Add a quality rule to the system."""
        try:
            self.con.execute(
                """
                INSERT OR REPLACE INTO quality_rules (
                    rule_id, rule_name, rule_type, field, condition, threshold_value,
                    severity, description, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    rule.rule_id,
                    rule.rule_name,
                    rule.rule_type,
                    rule.field,
                    rule.condition,
                    rule.threshold_value,
                    rule.severity,
                    rule.description,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                ),
            )

            return True
        except Exception as e:
            logger.error(f"Failed to add quality rule: {e}")
            return False

    def evaluate_data_quality(
        self, file_id: int, extraction_run_id: str
    ) -> dict[str, Any]:
        """Evaluate data quality using configured rules and generate metrics."""
        try:
            quality_results = {
                "file_id": file_id,
                "extraction_run_id": extraction_run_id,
                "evaluated_at": datetime.now().isoformat(),
                "overall_score": 0.0,
                "rule_violations": [],
                "metrics": {},
            }

            # Get quality rules
            rules = self.con.execute(
                """
                SELECT * FROM quality_rules WHERE is_active = TRUE
            """
            ).fetchdf()

            total_score = 0.0
            total_rules = len(rules)

            for _, rule in rules.iterrows():
                rule_result = self._evaluate_quality_rule(
                    rule, file_id, extraction_run_id
                )
                quality_results["rule_violations"].extend(rule_result["violations"])

                if rule_result["passed"]:
                    total_score += 1.0

            quality_results["overall_score"] = (
                total_score / total_rules if total_rules > 0 else 0.0
            )

            # Store quality metrics
            self._store_quality_metrics(file_id, extraction_run_id, quality_results)

            logger.info(
                f"Data quality evaluation completed for run {extraction_run_id}"
            )
            return quality_results

        except Exception as e:
            logger.error(f"Failed to evaluate data quality: {e}")
            return {}

    def _evaluate_quality_rule(
        self, rule: pd.Series, file_id: int, extraction_run_id: str
    ) -> dict[str, Any]:
        """Evaluate a single quality rule."""
        result = {
            "rule_id": rule["rule_id"],
            "rule_name": rule["rule_name"],
            "passed": True,
            "violations": [],
        }

        try:
            if rule["rule_type"] == "threshold":
                violations = self._evaluate_threshold_rule(
                    rule, file_id, extraction_run_id
                )
            elif rule["rule_type"] == "completeness":
                violations = self._evaluate_completeness_rule(
                    rule, file_id, extraction_run_id
                )
            elif rule["rule_type"] == "pattern":
                violations = self._evaluate_pattern_rule(
                    rule, file_id, extraction_run_id
                )
            else:
                violations = []

            result["violations"] = violations
            result["passed"] = len(violations) == 0

        except Exception as e:
            logger.warning(f"Failed to evaluate rule {rule['rule_id']}: {e}")
            result["passed"] = False
            result["violations"].append(f"Rule evaluation failed: {e}")

        return result

    def _evaluate_threshold_rule(
        self, rule: pd.Series, file_id: int, extraction_run_id: str
    ) -> list[str]:
        """Evaluate a threshold-based quality rule."""
        violations = []

        try:
            if rule["field"] == "confidence":
                # Check entity confidence
                entity_violations = self.con.execute(
                    """
                    SELECT entity_id, confidence FROM entities_metadata
                    WHERE file_id = ? AND extraction_run_id = ? AND confidence < ?
                """,
                    (file_id, extraction_run_id, rule["threshold_value"]),
                ).fetchdf()

                for _, row in entity_violations.iterrows():
                    violations.append(
                        f"Entity {row['entity_id']} has low confidence: {row['confidence']}"
                    )

                # Check relationship confidence
                rel_violations = self.con.execute(
                    """
                    SELECT relationship_id, confidence FROM relationships_metadata
                    WHERE file_id = ? AND extraction_run_id = ? AND confidence < ?
                """,
                    (file_id, extraction_run_id, rule["threshold_value"]),
                ).fetchdf()

                for _, row in rel_violations.iterrows():
                    violations.append(
                        f"Relationship {row['relationship_id']} has low confidence: {row['confidence']}"
                    )

        except Exception as e:
            violations.append(f"Threshold rule evaluation failed: {e}")

        return violations

    def _evaluate_completeness_rule(
        self, rule: pd.Series, file_id: int, extraction_run_id: str
    ) -> list[str]:
        """Evaluate a completeness-based quality rule."""
        violations = []

        try:
            if rule["field"] == "name":
                # Check for empty entity names
                empty_names = self.con.execute(
                    """
                    SELECT entity_id FROM entities_metadata
                    WHERE file_id = ? AND extraction_run_id = ?
                    AND (name IS NULL OR name = '' OR name = 'NULL')
                """,
                    (file_id, extraction_run_id),
                ).fetchdf()

                for _, row in empty_names.iterrows():
                    violations.append(f"Entity {row['entity_id']} has empty name")

        except Exception as e:
            violations.append(f"Completeness rule evaluation failed: {e}")

        return violations

    def _evaluate_pattern_rule(
        self, rule: pd.Series, file_id: int, extraction_run_id: str
    ) -> list[str]:
        """Evaluate a pattern-based quality rule."""
        violations = []

        try:
            if rule["field"] == "entity_type":
                # Check entity type validity
                invalid_types = self.con.execute(
                    """
                    SELECT entity_id, entity_type FROM entities_metadata
                    WHERE file_id = ? AND extraction_run_id = ?
                    AND entity_type NOT IN ('PERSON', 'ORGANIZATION', 'LOCATION', 'PRODUCT', 'EVENT', 'OTHER')
                """,
                    (file_id, extraction_run_id),
                ).fetchdf()

                for _, row in invalid_types.iterrows():
                    violations.append(
                        f"Entity {row['entity_id']} has invalid type: {row['entity_type']}"
                    )

        except Exception as e:
            violations.append(f"Pattern rule evaluation failed: {e}")

        return violations

    def _store_quality_metrics(
        self, file_id: int, extraction_run_id: str, quality_results: dict[str, Any]
    ):
        """Store quality metrics in the database."""
        try:
            # Store overall quality score
            self.con.execute(
                """
                INSERT INTO quality_metrics (
                    file_id, extraction_run_id, metric_name, metric_value, metric_type, calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    file_id,
                    extraction_run_id,
                    "overall_quality_score",
                    quality_results["overall_score"],
                    "overall",
                    datetime.now().isoformat(),
                ),
            )

            # Store rule violation count
            violation_count = len(quality_results["rule_violations"])
            self.con.execute(
                """
                INSERT INTO quality_metrics (
                    file_id, extraction_run_id, metric_name, metric_value, metric_type, calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    file_id,
                    extraction_run_id,
                    "rule_violations_count",
                    violation_count,
                    "overall",
                    datetime.now().isoformat(),
                ),
            )

        except Exception as e:
            logger.error(f"Failed to store quality metrics: {e}")

    def detect_data_drift(
        self,
        field_name: str,
        entity_type: Optional[str] = None,
        baseline_date: Optional[datetime] = None,
    ) -> list[DriftMetrics]:
        """Detect data drift for a specific field."""
        try:
            # Get baseline statistics
            if baseline_date is None:
                baseline_date = datetime.now() - timedelta(days=30)

            baseline_query = """
                SELECT baseline_mean, baseline_std, baseline_min, baseline_max, baseline_count
                FROM baseline_statistics
                WHERE field_name = ? AND is_current = TRUE
            """
            baseline_params = [field_name]

            if entity_type:
                baseline_query += " AND entity_type = ?"
                baseline_params.append(entity_type)

            baseline_result = self.con.execute(
                baseline_query, baseline_params
            ).fetchone()

            if not baseline_result:
                logger.warning(f"No baseline statistics found for field {field_name}")
                return []

            baseline_mean, baseline_std, baseline_min, baseline_max, baseline_count = (
                baseline_result
            )

            # Get current statistics
            current_query = """
                SELECT AVG(confidence) as current_mean, COUNT(*) as current_count
                FROM entities_metadata
                WHERE created_at >= ?
            """
            current_params = [baseline_date.isoformat()]

            if entity_type:
                current_query += " AND entity_type = ?"
                current_params.append(entity_type)

            current_result = self.con.execute(current_query, current_params).fetchone()

            if not current_result:
                return []

            current_mean, current_count = current_result

            # Calculate drift score
            if baseline_std > 0:
                drift_score = abs(current_mean - baseline_mean) / baseline_std
                drift_detected = drift_score > 2.0  # 2 standard deviations
                confidence = min(1.0, 1.0 / (1.0 + drift_score))
            else:
                drift_score = 0.0
                drift_detected = False
                confidence = 1.0

            drift_metrics = DriftMetrics(
                field_name=field_name,
                baseline_mean=baseline_mean,
                current_mean=current_mean,
                drift_score=drift_score,
                drift_detected=drift_detected,
                confidence=confidence,
                detected_at=datetime.now(),
            )

            # Store drift detection result
            self._store_drift_detection(drift_metrics)

            return [drift_metrics]

        except Exception as e:
            logger.error(f"Failed to detect data drift: {e}")
            return []

    def _store_drift_detection(self, drift_metrics: DriftMetrics):
        """Store drift detection results."""
        try:
            # Update baseline statistics
            self.con.execute(
                """
                UPDATE baseline_statistics SET is_current = FALSE
                WHERE field_name = ? AND is_current = TRUE
            """,
                (drift_metrics.field_name,),
            )

            # Insert new baseline
            self.con.execute(
                """
                INSERT INTO baseline_statistics (
                    field_name, baseline_mean, baseline_std, baseline_min, baseline_max,
                    baseline_count, baseline_date, is_current
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    drift_metrics.field_name,
                    drift_metrics.current_mean,
                    0.0,
                    0.0,
                    0.0,
                    0,
                    datetime.now().date(),
                    True,
                ),
            )

        except Exception as e:
            logger.error(f"Failed to store drift detection: {e}")

    def generate_extraction_analytics(
        self,
        file_id: Optional[int] = None,
        date_range: Optional[tuple[datetime, datetime]] = None,
    ) -> dict[str, Any]:
        """Generate comprehensive extraction analytics."""
        try:
            analytics = {
                "generated_at": datetime.now().isoformat(),
                "summary": {},
                "trends": {},
                "quality_metrics": {},
                "performance_metrics": {},
            }

            # Build date filter
            date_filter = ""
            date_params = []
            if date_range:
                start_date, end_date = date_range
                date_filter = "WHERE created_at BETWEEN ? AND ?"
                date_params = [start_date.isoformat(), end_date.isoformat()]

            # Overall statistics
            if file_id:
                # Single file analytics
                analytics["summary"] = self._get_file_analytics(file_id)
            else:
                # Multi-file analytics
                analytics["summary"] = self._get_overall_analytics(
                    date_filter, date_params
                )

            # Quality trends
            analytics["quality_metrics"] = self._get_quality_trends(
                date_filter, date_params
            )

            # Performance trends
            analytics["performance_metrics"] = self._get_performance_trends(
                date_filter, date_params
            )

            logger.info("Extraction analytics generated successfully")
            return analytics

        except Exception as e:
            logger.error(f"Failed to generate extraction analytics: {e}")
            return {}

    def _get_file_analytics(self, file_id: int) -> dict[str, Any]:
        """Get analytics for a specific file."""
        try:
            # File information
            file_info = self.con.execute(
                """
                SELECT file_name, file_size, checksum, processing_status, uploaded_at
                FROM files WHERE id = ?
            """,
                (file_id,),
            ).fetchone()

            if not file_info:
                return {}

            # Entity statistics
            entity_stats = self.con.execute(
                """
                SELECT COUNT(*) as total_entities,
                       AVG(confidence) as avg_confidence,
                       AVG(quality_score) as avg_quality_score
                FROM entities_metadata WHERE file_id = ?
            """,
                (file_id,),
            ).fetchone()

            # Relationship statistics
            rel_stats = self.con.execute(
                """
                SELECT COUNT(*) as total_relationships,
                       AVG(confidence) as avg_confidence,
                       AVG(quality_score) as avg_quality_score
                FROM relationships_metadata WHERE file_id = ?
            """,
                (file_id,),
            ).fetchone()

            return {
                "file_info": {
                    "name": file_info[0],
                    "size": file_info[1],
                    "checksum": file_info[2],
                    "status": file_info[3],
                    "uploaded_at": file_info[4],
                },
                "entity_statistics": {
                    "total_count": entity_stats[0],
                    "average_confidence": entity_stats[1] or 0.0,
                    "average_quality_score": entity_stats[2] or 0.0,
                },
                "relationship_statistics": {
                    "total_count": rel_stats[0],
                    "average_confidence": rel_stats[1] or 0.0,
                    "average_quality_score": rel_stats[2] or 0.0,
                },
            }

        except Exception as e:
            logger.error(f"Failed to get file analytics: {e}")
            return {}

    def _get_overall_analytics(
        self, date_filter: str, date_params: list
    ) -> dict[str, Any]:
        """Get overall analytics across all files."""
        try:
            # Total files processed
            total_files = self.con.execute(
                f"""
                SELECT COUNT(*) FROM files {date_filter}
            """,
                date_params,
            ).fetchone()[0]

            # Total entities and relationships
            total_entities = self.con.execute(
                f"""
                SELECT COUNT(*) FROM entities_metadata {date_filter}
            """,
                date_params,
            ).fetchone()[0]

            total_relationships = self.con.execute(
                f"""
                SELECT COUNT(*) FROM relationships_metadata {date_filter}
            """,
                date_params,
            ).fetchone()[0]

            # Average quality scores
            avg_entity_quality = (
                self.con.execute(
                    f"""
                SELECT AVG(quality_score) FROM entities_metadata {date_filter}
            """,
                    date_params,
                ).fetchone()[0]
                or 0.0
            )

            avg_rel_quality = (
                self.con.execute(
                    f"""
                SELECT AVG(quality_score) FROM relationships_metadata {date_filter}
            """,
                    date_params,
                ).fetchone()[0]
                or 0.0
            )

            return {
                "total_files_processed": total_files,
                "total_entities_extracted": total_entities,
                "total_relationships_discovered": total_relationships,
                "average_entity_quality": avg_entity_quality,
                "average_relationship_quality": avg_rel_quality,
            }

        except Exception as e:
            logger.error(f"Failed to get overall analytics: {e}")
            return {}

    def _get_quality_trends(
        self, date_filter: str, date_params: list
    ) -> dict[str, Any]:
        """Get quality trends over time."""
        try:
            # Daily quality scores
            daily_quality = self.con.execute(
                f"""
                SELECT DATE(created_at) as date,
                       AVG(quality_score) as avg_quality,
                       COUNT(*) as count
                FROM entities_metadata {date_filter}
                GROUP BY DATE(created_at)
                ORDER BY date
            """,
                date_params,
            ).fetchdf()

            return {
                "daily_quality_trends": (
                    daily_quality.to_dict("records") if not daily_quality.empty else []
                )
            }

        except Exception as e:
            logger.error(f"Failed to get quality trends: {e}")
            return {}

    def _get_performance_trends(
        self, date_filter: str, date_params: list
    ) -> dict[str, Any]:
        """Get performance trends over time."""
        try:
            # Extraction run performance
            run_performance = self.con.execute(
                f"""
                SELECT DATE(started_at) as date,
                       AVG(CAST((julianday(completed_at) - julianday(started_at)) * 24 * 60 * 60 AS REAL)) as avg_duration_seconds,
                       COUNT(*) as run_count
                FROM extraction_runs {date_filter}
                WHERE completed_at IS NOT NULL
                GROUP BY DATE(started_at)
                ORDER BY date
            """,
                date_params,
            ).fetchdf()

            return {
                "daily_performance_trends": (
                    run_performance.to_dict("records")
                    if not run_performance.empty
                    else []
                )
            }

        except Exception as e:
            logger.error(f"Failed to get performance trends: {e}")
            return {}

    def get_audit_log(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        operation: Optional[str] = None,
        table_name: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Retrieve audit log entries with filtering."""
        try:
            query = "SELECT * FROM audit_log WHERE 1=1"
            params = []

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())

            if operation:
                query += " AND operation = ?"
                params.append(operation)

            if table_name:
                query += " AND table_name = ?"
                params.append(table_name)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            result = self.con.execute(query, params).fetchdf()

            if result.empty:
                return []

            return result.to_dict("records")

        except Exception as e:
            logger.error(f"Failed to retrieve audit log: {e}")
            return []

    def export_metadata_analytics(
        self, output_path: str, file_id: Optional[int] = None, format: str = "json"
    ) -> bool:
        """Export comprehensive metadata analytics."""
        try:
            # Generate analytics
            analytics = self.generate_extraction_analytics(file_id)

            if format.lower() == "json":
                with open(output_path, "w") as f:
                    json.dump(analytics, f, indent=2, default=str)
            elif format.lower() == "csv":
                # Export key metrics to CSV
                df = pd.DataFrame([analytics["summary"]])
                df.to_csv(output_path, index=False)
            elif format.lower() == "parquet":
                df = pd.DataFrame([analytics["summary"]])
                df.to_parquet(output_path, index=False)
            else:
                raise ValueError(f"Unsupported export format: {format}")

            logger.info(f"Metadata analytics exported to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export metadata analytics: {e}")
            return False

    def close(self):
        """Close the database connection."""
        if hasattr(self, "con") and self.con:
            self.con.close()
            logger.info("Metadata store connection closed")


# Backward compatibility - keep the old class name
MetadataStore = AdvancedMetadataStore
