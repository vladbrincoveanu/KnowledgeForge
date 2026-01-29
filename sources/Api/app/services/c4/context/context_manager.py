"""Context Manager for C4 Model Level 1 (System Context).

Orchestrates the detection of:
- System name and purpose
- External dependencies
- Actors (users, systems)
- Languages and frameworks
- All 7 primary Service model fields:
  1. domain - Business area
  2. owner - Team/squad (with contributor stats)
  3. status - Lifecycle stage (Active-Dev, Maintenance-Only, Deprecated)
  4. tier - Criticality level
  5. data_class - Data sensitivity classification
  6. active_experts - Bus factor indicator
  7. compliance - Architectural compliance risk
- Git activity metrics (commits, dates, contributors)
"""

import logging
from pathlib import Path
from typing import Any, Optional

from .system_detector import SystemDetector
from .dependency_detector import DependencyDetector
from .metadata_detector import MetadataDetector

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages Level 1 Context extraction for C4 Model."""

    def __init__(self, repo_path: Path, llm_manager=None, containers: dict[str, Any] = None):
        """Initialize Context Manager.

        Args:
            repo_path: Path to repository
            llm_manager: Optional LLM for generating descriptions
            containers: Optional dictionary of detected containers (for domain inference)
        """
        self.repo_path = Path(repo_path).resolve()
        self.llm_manager = llm_manager
        self.containers = containers or {}

        # Initialize detectors
        self.system_detector = SystemDetector(repo_path, llm_manager)
        self.dependency_detector = DependencyDetector(repo_path)
        self.metadata_detector = MetadataDetector(repo_path, llm_manager, containers)

    def extract_context(self) -> dict[str, Any]:
        """Extract complete system context (Level 1).

        Returns:
            Dictionary with system context information
        """
        logger.info("Extracting C4 Level 1: System Context")

        # System identification
        system_name = self.system_detector.detect_system_name()
        system_purpose = self.system_detector.generate_system_purpose()

        # External dependencies
        external_deps = self.dependency_detector.detect_external_dependencies()

        # Languages and frameworks
        languages = self.system_detector.detect_languages()
        frameworks = self.system_detector.detect_frameworks()

        # Actors
        actors = self.system_detector.detect_context_actors()

        # Git and repository metadata
        git_metadata = self.system_detector.extract_git_metadata()
        repository_url = self.system_detector.get_repository_root_url()
        context_sources = self.system_detector.collect_context_sources(frameworks)

        # IT Landscape metadata
        owner_team = self.metadata_detector.detect_owner_team()
        business_domain = self.metadata_detector.infer_business_domain()
        criticality = self.metadata_detector.determine_criticality()
        data_class = self.metadata_detector.infer_data_classification()

        # Service status and lifecycle
        status, status_evidence = self.metadata_detector.detect_service_status()

        # Active experts (bus factor)
        active_experts = self.metadata_detector.calculate_active_experts()

        # Git activity metrics
        git_activity = self.metadata_detector.get_git_activity_metrics()

        # Owner and contributor stats
        contributor_stats = self.metadata_detector.get_owner_contributor_stats(max_contributors=5)

        # Compliance risk assessment
        compliance = self.metadata_detector.assess_compliance_risk(
            domain=business_domain,
            data_class=data_class,
            owner=owner_team,
            tier=criticality,
        )

        context = {
            "c4_level": 1,
            "type": "system",
            "name": system_name,
            "purpose": system_purpose,
            "external_dependencies": external_deps,
            "actors": actors,
            "languages": languages,
            "frameworks": frameworks,
            "repository_url": repository_url,
            "git": git_metadata,
            "context_sources": context_sources,

            # ═══════════════════════════════════════════════════════════
            # PRIMARY SERVICE FIELDS (The 7 key attributes)
            # ═══════════════════════════════════════════════════════════

            # 1. domain - Business area
            "domain": business_domain,

            # 2. owner - Squad/team that owns the service
            "owner": owner_team,
            "owner_contributors": contributor_stats.get("owner_contributors", []),
            "owner_contributor_stats": contributor_stats.get("owner_contributor_stats", []),
            "contributor_count": git_activity.get("contributor_count", 0),

            # 3. status - Lifecycle stage
            "status": status,
            "status_evidence": status_evidence,

            # 4. tier - Criticality level
            "tier": criticality,

            # 5. data_class - Sensitive data classification
            "data_class": data_class,

            # 6. active_experts - Bus factor (contributors with 3+ commits in last 90 days)
            "active_experts": active_experts,

            # 7. compliance - Architectural compliance risk
            "compliance": compliance,

            # ═══════════════════════════════════════════════════════════
            # GIT ACTIVITY METRICS
            # ═══════════════════════════════════════════════════════════
            "last_commit_date": git_activity.get("last_commit_date"),
            "commit_count_30d": git_activity.get("commit_count_30d", 0),
            "commit_count_90d": git_activity.get("commit_count_90d", 0),
            "commit_count_180d": git_activity.get("commit_count_180d", 0),

            # Legacy field aliases for backwards compatibility
            "owner_team": owner_team,
            "business_domain": business_domain,
            "criticality": criticality,
        }

        logger.info(f"✓ System: {system_name}")
        logger.info(f"✓ Owner: {owner_team}")
        logger.info(f"✓ Domain: {business_domain}")
        logger.info(f"✓ Status: {status}")
        logger.info(f"✓ Tier: {criticality}")
        logger.info(f"✓ Data Class: {data_class}")
        logger.info(f"✓ Active Experts: {active_experts}")
        logger.info(f"✓ Compliance: {compliance}")
        logger.info(f"✓ External dependencies: {len(external_deps)}")

        return context

    def build_context_relationships(self, system_context: dict[str, Any]) -> list[dict[str, Any]]:
        """Build relationships for the Context diagram.

        Args:
            system_context: The extracted system context

        Returns:
            List of relationship dictionaries
        """
        relationships = []
        system_name = system_context.get('name', self.repo_path.name)

        # Actor -> System relationships
        for actor in system_context.get('actors', []):
            relationships.append({
                "source": actor.get('name', 'User'),
                "destination": system_name,
                "description": "uses",
                "relationship_type": "uses",
            })

        # System -> External dependency relationships
        for dep in system_context.get('external_dependencies', []):
            dep_name = dep.get('name') or dep.get('service') or 'External Service'
            dep_type = dep.get('type') or dep.get('category') or 'external'
            relationships.append({
                "source": system_name,
                "destination": dep_name,
                "description": f"uses {dep_type}",
                "relationship_type": "uses",
            })

        return relationships
