"""Extraction configuration and feature flags."""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

logger = logging.getLogger(__name__)


class ExtractionConfig:
    """
    Configuration for service extraction.
    
    Feature Flags:
    - STORE_TO_JSON: Store results to JSON files instead of database
    - JSON_OUTPUT_DIR: Directory for JSON output files
    """
    
    # Feature flags (can be overridden via environment variables)
    STORE_TO_JSON: bool = True  # Default: store to JSON
    STORE_TO_NEO4J: bool = False  # Default: skip Neo4j
    
    # Enhancement feature flags
    ENABLE_GIT_ANALYSIS: bool = True       # Owner + status from git history
    ENABLE_DOMAIN_DETECTION: bool = True   # Domain inference from imports/namespaces
    ENABLE_DEPENDENCY_SCAN: bool = True    # Direct dependencies from imports
    ENABLE_LLM_DESCRIPTIONS: bool = False  # Optional LLM summarization (disabled by default)
    ENABLE_LLM_LABELS: bool = True         # Optional LLM label/notes enrichment
    
    # Git settings
    GIT_CLONE_FOR_ANALYSIS: bool = True
    GIT_CONTRIBUTOR_LIMIT: int = 5
    
    # LLM settings
    LLM_MAX_TOKENS: int = 150
    LLM_DESCRIPTION_ENABLED: bool = False
    LLM_BUDGET_TOKENS: int = 4000  # Rough token cap per extraction to avoid overspend
    
    # Output directory for JSON files
    JSON_OUTPUT_DIR: Path = Path(__file__).parent.parent.parent.parent / "data" / "extractions"
    
    @classmethod
    def load_from_env(cls):
        """Load configuration from environment variables."""
        cls.STORE_TO_JSON = os.getenv("KF_STORE_TO_JSON", "true").lower() in ("true", "1", "yes")
        cls.STORE_TO_NEO4J = os.getenv("KF_STORE_TO_NEO4J", "false").lower() in ("true", "1", "yes")
        cls.ENABLE_GIT_ANALYSIS = os.getenv("KF_ENABLE_GIT_ANALYSIS", str(cls.ENABLE_GIT_ANALYSIS)).lower() in ("true", "1", "yes")
        cls.ENABLE_DOMAIN_DETECTION = os.getenv("KF_ENABLE_DOMAIN_DETECTION", str(cls.ENABLE_DOMAIN_DETECTION)).lower() in ("true", "1", "yes")
        cls.ENABLE_DEPENDENCY_SCAN = os.getenv("KF_ENABLE_DEPENDENCY_SCAN", str(cls.ENABLE_DEPENDENCY_SCAN)).lower() in ("true", "1", "yes")
        cls.ENABLE_LLM_DESCRIPTIONS = os.getenv("KF_ENABLE_LLM_DESCRIPTIONS", str(cls.ENABLE_LLM_DESCRIPTIONS)).lower() in ("true", "1", "yes")
        cls.ENABLE_LLM_LABELS = os.getenv("KF_ENABLE_LLM_LABELS", str(cls.ENABLE_LLM_LABELS)).lower() in ("true", "1", "yes")
        cls.GIT_CLONE_FOR_ANALYSIS = os.getenv("KF_GIT_CLONE_FOR_ANALYSIS", str(cls.GIT_CLONE_FOR_ANALYSIS)).lower() in ("true", "1", "yes")
        
        contributor_limit = os.getenv("KF_GIT_CONTRIBUTOR_LIMIT")
        if contributor_limit and contributor_limit.isdigit():
            cls.GIT_CONTRIBUTOR_LIMIT = int(contributor_limit)
        
        llm_max_tokens = os.getenv("KF_LLM_MAX_TOKENS")
        if llm_max_tokens and llm_max_tokens.isdigit():
            cls.LLM_MAX_TOKENS = int(llm_max_tokens)
        llm_budget_tokens = os.getenv("KF_LLM_BUDGET_TOKENS")
        if llm_budget_tokens and llm_budget_tokens.isdigit():
            cls.LLM_BUDGET_TOKENS = int(llm_budget_tokens)
        
        cls.LLM_DESCRIPTION_ENABLED = os.getenv("KF_LLM_DESCRIPTION_ENABLED", str(cls.LLM_DESCRIPTION_ENABLED)).lower() in ("true", "1", "yes")
        
        output_dir = os.getenv("KF_JSON_OUTPUT_DIR")
        if output_dir:
            cls.JSON_OUTPUT_DIR = Path(output_dir)
        
        logger.info(
            "Extraction config: STORE_TO_JSON=%s, STORE_TO_NEO4J=%s, "
            "ENABLE_GIT_ANALYSIS=%s, ENABLE_DOMAIN_DETECTION=%s, "
            "ENABLE_DEPENDENCY_SCAN=%s, ENABLE_LLM_DESCRIPTIONS=%s, ENABLE_LLM_LABELS=%s, LLM_BUDGET_TOKENS=%s",
            cls.STORE_TO_JSON,
            cls.STORE_TO_NEO4J,
            cls.ENABLE_GIT_ANALYSIS,
            cls.ENABLE_DOMAIN_DETECTION,
            cls.ENABLE_DEPENDENCY_SCAN,
            cls.ENABLE_LLM_DESCRIPTIONS,
            cls.ENABLE_LLM_LABELS,
            cls.LLM_BUDGET_TOKENS,
        )


class JSONResultStore:
    """
    Store extraction results to JSON files for easy access and debugging.
    
    Output Structure:
    data/extractions/
    ├── {task_id}/
    │   ├── metadata.json      # Task metadata, timestamps, status
    │   ├── services.json      # All extracted services (5 primary fields)
    │   ├── connections.json   # Service connections/relationships
    │   └── summary.json       # Human-readable summary
    """
    
    def __init__(self, task_id: str, output_dir: Optional[Path] = None):
        self.task_id = task_id
        self.output_dir = output_dir or ExtractionConfig.JSON_OUTPUT_DIR
        self.task_dir = self.output_dir / task_id
    
    def ensure_dir(self):
        """Ensure output directory exists."""
        self.task_dir.mkdir(parents=True, exist_ok=True)
    
    def save_metadata(
        self,
        status: str,
        repository_url: Optional[str] = None,
        repository_name: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        errors: Optional[list[str]] = None,
        warnings: Optional[list[str]] = None,
    ):
        """Save task metadata."""
        self.ensure_dir()
        
        metadata = {
            "task_id": self.task_id,
            "status": status,
            "repository_url": repository_url,
            "repository_name": repository_name,
            "started_at": started_at.isoformat() if started_at else None,
            "completed_at": completed_at.isoformat() if completed_at else None,
            "errors": errors or [],
            "warnings": warnings or [],
            "last_updated": datetime.now().isoformat(),
        }
        
        self._write_json("metadata.json", metadata)
        logger.info(f"Saved metadata for task {self.task_id}")
    
    def save_services(self, services: list[dict]):
        """
        Save extracted services with the 5 primary fields.
        
        Each service dict should have:
        - id, name, display_name
        - domain, owner, status, tier, data_class (THE 5 PRIMARY FIELDS)
        - Additional metadata (language, framework, file_path, etc.)
        """
        self.ensure_dir()
        
        # Ensure services are serializable and highlight the 5 fields
        clean_services = []
        for svc in services:
            clean_svc = {
                # ═══════════════════════════════════════════════════════════
                # THE 5 PRIMARY EXTRACTION FIELDS (always at top)
                # ═══════════════════════════════════════════════════════════
                "domain": svc.get("domain"),
                "owner": svc.get("owner"),
                "owner_contributors": svc.get("owner_contributors", []),
                "owner_contributor_stats": svc.get("owner_contributor_stats", []),
                "contributor_count": svc.get("contributor_count", 0),
                "status": svc.get("status"),
                "status_evidence": svc.get("status_evidence"),
                "tier": svc.get("tier"),
                "data_class": svc.get("data_class"),
                # ═══════════════════════════════════════════════════════════
                # Service identity
                "id": svc.get("id"),
                "name": svc.get("name"),
                "display_name": svc.get("display_name"),
                "description": svc.get("description"),
                "notes": svc.get("notes") or svc.get("description"),
                # ═══════════════════════════════════════════════════════════
                # Technical details
                "language": svc.get("language"),
                "framework": svc.get("framework"),
                "port": svc.get("port"),
                "file_path": svc.get("file_path"),
                "source": svc.get("source"),
                # ═══════════════════════════════════════════════════════════
                # Dependencies
                "direct_depends": svc.get("direct_depends", []),
                "dependencies": svc.get("dependencies", []),
                "dependents": svc.get("dependents", []),
                # ═══════════════════════════════════════════════════════════
                # Git activity metrics
                # Note: last_commit_date is already a string (from .isoformat() in service_extraction.py)
                "last_commit_date": svc.get("last_commit_date") if svc.get("last_commit_date") else None,
                "commit_count_30d": svc.get("commit_count_30d", 0),
                "commit_count_90d": svc.get("commit_count_90d", 0),
                "commit_count_180d": svc.get("commit_count_180d", 0),
                # ═══════════════════════════════════════════════════════════
                # Additional
                "attributes": svc.get("attributes", {}),
                "confidence": svc.get("confidence", 1.0),
            }
            clean_services.append(clean_svc)
        
        output = {
            "task_id": self.task_id,
            "total_services": len(clean_services),
            "extracted_at": datetime.now().isoformat(),
            "services": clean_services,
        }
        
        self._write_json("services.json", output)
        logger.info(f"Saved {len(clean_services)} services for task {self.task_id}")
    
    def save_connections(self, connections: list[dict]):
        """Save service connections."""
        self.ensure_dir()
        
        clean_connections = []
        for conn in connections:
            clean_conn = {
                "id": conn.get("id"),
                "source_service_id": conn.get("source_service_id"),
                "target_service_id": conn.get("target_service_id"),
                "connection_type": conn.get("connection_type"),
                "protocol": conn.get("protocol"),
                "endpoint": conn.get("endpoint"),
                "strength": conn.get("strength"),
                "file_path": conn.get("file_path"),
                "confidence": conn.get("confidence", 1.0),
            }
            clean_connections.append(clean_conn)
        
        output = {
            "task_id": self.task_id,
            "total_connections": len(clean_connections),
            "extracted_at": datetime.now().isoformat(),
            "connections": clean_connections,
        }
        
        self._write_json("connections.json", output)
        logger.info(f"Saved {len(clean_connections)} connections for task {self.task_id}")
    
    def save_summary(
        self,
        services: list[dict],
        connections: list[dict],
        repository_name: Optional[str] = None,
    ):
        """
        Save a human-readable summary.
        
        This is designed to be easy for Cursor/AI to read and understand.
        """
        self.ensure_dir()
        
        # Count by status
        status_counts = {}
        for svc in services:
            status = svc.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count by domain
        domain_counts = {}
        for svc in services:
            domain = svc.get("domain") or "Unclassified"
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        # Count by tier
        tier_counts = {}
        for svc in services:
            tier = svc.get("tier") or "unknown"
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        
        summary = {
            "task_id": self.task_id,
            "repository": repository_name,
            "generated_at": datetime.now().isoformat(),
            
            # Quick stats
            "statistics": {
                "total_services": len(services),
                "total_connections": len(connections),
                "services_by_status": status_counts,
                "services_by_domain": domain_counts,
                "services_by_tier": tier_counts,
            },
            
            # Services with the 5 primary fields (easy to scan)
            "services_overview": [
                {
                    "name": svc.get("name"),
                    "domain": svc.get("domain") or "-",
                    "owner": svc.get("owner") or "-",
                    "status": svc.get("status") or "-",
                    "tier": svc.get("tier") or "-",
                    "data_class": svc.get("data_class") or "-",
                }
                for svc in services
            ],
            
            # File paths for reference
            "output_files": {
                "metadata": str(self.task_dir / "metadata.json"),
                "services": str(self.task_dir / "services.json"),
                "connections": str(self.task_dir / "connections.json"),
                "summary": str(self.task_dir / "summary.json"),
            },
        }
        
        self._write_json("summary.json", summary)
        logger.info(f"Saved summary for task {self.task_id}")
        
        # Also print a quick summary to logs
        logger.info(f"""
═══════════════════════════════════════════════════════════════════════════
EXTRACTION SUMMARY - {self.task_id}
═══════════════════════════════════════════════════════════════════════════
Repository: {repository_name or 'N/A'}
Total Services: {len(services)}
Total Connections: {len(connections)}

By Status: {status_counts}
By Domain: {domain_counts}
By Tier: {tier_counts}

Output saved to: {self.task_dir}
═══════════════════════════════════════════════════════════════════════════
""")
    
    def _write_json(self, filename: str, data: Any):
        """Write data to JSON file with pretty formatting."""
        filepath = self.task_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    def load_services(self) -> list[dict]:
        """Load services from JSON file."""
        filepath = self.task_dir / "services.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("services", [])
        return []
    
    def load_connections(self) -> list[dict]:
        """Load connections from JSON file."""
        filepath = self.task_dir / "connections.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("connections", [])
        return []
    
    def load_summary(self) -> Optional[dict]:
        """Load summary from JSON file."""
        filepath = self.task_dir / "summary.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    def get_output_path(self) -> Path:
        """Get the output directory path."""
        return self.task_dir


# Initialize config on module load
ExtractionConfig.load_from_env()

# Ensure all attributes are defined (safety check for import issues)
if not hasattr(ExtractionConfig, 'ENABLE_LLM_DESCRIPTIONS'):
    ExtractionConfig.ENABLE_LLM_DESCRIPTIONS = False
if not hasattr(ExtractionConfig, 'ENABLE_LLM_LABELS'):
    ExtractionConfig.ENABLE_LLM_LABELS = False
if not hasattr(ExtractionConfig, 'LLM_BUDGET_TOKENS'):
    ExtractionConfig.LLM_BUDGET_TOKENS = 4000
if not hasattr(ExtractionConfig, 'ENABLE_GIT_ANALYSIS'):
    ExtractionConfig.ENABLE_GIT_ANALYSIS = True
if not hasattr(ExtractionConfig, 'ENABLE_DOMAIN_DETECTION'):
    ExtractionConfig.ENABLE_DOMAIN_DETECTION = True
if not hasattr(ExtractionConfig, 'ENABLE_DEPENDENCY_SCAN'):
    ExtractionConfig.ENABLE_DEPENDENCY_SCAN = True
