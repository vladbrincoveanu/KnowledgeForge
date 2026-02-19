"""Context Manager for C4 Model Level 1 (System Context).

Orchestrates the detection of:
- System name and purpose
- External dependencies
- Actors (users, systems)
- Languages and frameworks
- All 7 primary Service model fields:
  1. domain - Business area
  2. owner - Team/squad (with contributor stats)
  3. status - Lifecycle stage (ACTIVE, MAINTENANCE, DEPRECATED, ARCHIVED)
  4. tier - Criticality level
  5. data_class - Data sensitivity classification
  6. active_experts - Bus factor indicator
  7. compliance - Architectural compliance risk
- Git activity metrics (commits, dates, contributors)
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .canonical_models import (
    CanonicalEntity,
    CanonicalEntityType,
    CanonicalFieldValue,
    CanonicalRelationship,
    CanonicalRelationshipType,
    CanonicalSnapshot,
    EffectiveFieldValue,
    FieldCandidate,
    deterministic_id,
)
from .system_detector import SystemDetector
from .dependency_detector import DependencyDetector
from .feature_flags import C4FeatureFlags
from .harvesters import RepositoryArtifactHarvester, ServiceUniverseHarvester
from .merge_engine import ContextMergeEngine
from .metadata_detector import MetadataDetector
from .precedence import FieldPrecedenceResolver
from .stores import CanonicalSnapshotStore, OverrideStore

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
        self.flags = C4FeatureFlags.from_env()

        # Initialize detectors
        self.system_detector = SystemDetector(repo_path, llm_manager)
        self.dependency_detector = DependencyDetector(repo_path, llm_manager)
        self.metadata_detector = MetadataDetector(repo_path, llm_manager, containers)
        self.service_universe_harvester = ServiceUniverseHarvester(self.repo_path)
        self.repo_artifact_harvester = RepositoryArtifactHarvester(self.repo_path)
        self.precedence_resolver = FieldPrecedenceResolver()
        self.snapshot_store = CanonicalSnapshotStore()
        self.override_store = OverrideStore()
        self.merge_engine = ContextMergeEngine()

    def extract_context(self) -> dict[str, Any]:
        """Extract complete system context (Level 1).

        Returns:
            Dictionary with system context information
        """
        logger.info("Extracting C4 Level 1: System Context")

        # System identification
        system_name = self.system_detector.detect_system_name()
        system_purpose = self.system_detector.generate_system_purpose()
        system_environment = self.system_detector.detect_environments()
        system_app_version = self.system_detector.detect_app_version()
        system_tags = self.system_detector.detect_tags()
        system_api_spec_url = self.system_detector.detect_api_spec_url()
        system_documentation_url = self.system_detector.detect_documentation_url()
        system_monitoring_url = self.system_detector.detect_monitoring_url()
        regulatory_frameworks = self.system_detector.detect_regulatory_frameworks()

        # External dependencies
        external_deps = self.dependency_detector.detect_external_dependencies()
        deployment_deps = self.dependency_detector.detect_deployment_dependencies()
        dependency_freshness_alerts = self.dependency_detector.detect_dependency_freshness_alerts()

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

        # If the repository looks infrastructure-focused, prefer General data class to avoid false positives
        if business_domain and business_domain.lower().startswith('infrastructure'):
            data_class = 'General'

        # Service status and lifecycle
        status, status_evidence = self.metadata_detector.detect_service_status()

        # Active experts (bus factor)
        active_experts = self.metadata_detector.calculate_active_experts()

        # Git activity metrics
        git_activity = self.metadata_detector.get_git_activity_metrics()
        dora_metrics = self.metadata_detector.get_dora_metrics()

        # Owner and contributor stats
        contributor_stats = self.metadata_detector.get_owner_contributor_stats(max_contributors=5)
        on_call_channel = self.metadata_detector.detect_on_call_channel()
        data_steward = (
            self.metadata_detector.detect_data_steward(owner_team)
            if self.flags.enable_owner_steward
            else None
        )
        squad = (
            self.metadata_detector.detect_squad(owner_team)
            if self.flags.enable_owner_steward
            else None
        )
        sensitivity_tags = (
            self.metadata_detector.infer_sensitivity_tags(data_class)
            if self.flags.enable_sensitivity_tags
            else []
        )
        quality_score = (
            self.metadata_detector.get_quality_score()
            if self.flags.enable_quality_score
            else None
        )
        usage_stats = (
            self.metadata_detector.get_usage_stats()
            if self.flags.enable_usage_stats
            else {}
        )
        column_lineage_summary = (
            self.metadata_detector.get_column_lineage_summary()
            if self.flags.enable_column_lineage
            else {}
        )

        # Compliance risk assessment (pure calculation from extracted metadata)
        compliance, compliance_confidence, compliance_factors = self.metadata_detector.assess_compliance_risk(
            domain=business_domain,
            data_class=data_class,
            owner=owner_team,
            tier=criticality,
            status=status,
            active_experts=active_experts
        )

        # Generate rich LLM description with all metadata context
        llm_description = self._generate_llm_description(
            system_name=system_name,
            purpose=system_purpose,
            domain=business_domain,
            owner=owner_team,
            tier=criticality,
            status=status,
            languages=languages,
            frameworks=frameworks,
        )

        context = {
            "c4_level": 1,
            "type": "system",
            "name": system_name,
            "purpose": system_purpose,
            "description": llm_description or system_purpose,
            "llm_description": llm_description or system_purpose,
            "external_dependencies": external_deps,
            "deployment_dependencies": deployment_deps,
            "dependency_freshness_alerts": dependency_freshness_alerts,
            "actors": actors,
            "languages": languages,
            "frameworks": frameworks,
            "repository_url": repository_url,
            "git": git_metadata,
            "context_sources": context_sources,
            "environment": system_environment,
            "app_version": system_app_version,
            "tags": system_tags,
            "api_spec_url": system_api_spec_url,
            "documentation_url": system_documentation_url,
            "monitoring_url": system_monitoring_url,
            "regulatory_frameworks": regulatory_frameworks,

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
            "compliance_confidence": compliance_confidence,
            "compliance_factors": compliance_factors,

            # ═══════════════════════════════════════════════════════════
            # GIT ACTIVITY METRICS
            # ═══════════════════════════════════════════════════════════
            "last_commit_date": git_activity.get("last_commit_date"),
            "commit_count_30d": git_activity.get("commit_count_30d", 0),
            "commit_count_90d": git_activity.get("commit_count_90d", 0),
            "commit_count_180d": git_activity.get("commit_count_180d", 0),
            "dora_metrics": dora_metrics,
            "on_call_channel": on_call_channel,
            "data_steward": data_steward,
            "sensitivity_tags": sensitivity_tags,
            "quality_score": quality_score,
            "usage_stats": usage_stats,
            "column_lineage_summary": column_lineage_summary,
            "squad": squad,
            "feature_flags": {
                "owner_steward": self.flags.enable_owner_steward,
                "sensitivity_tags": self.flags.enable_sensitivity_tags,
                "quality_score": self.flags.enable_quality_score,
                "usage_stats": self.flags.enable_usage_stats,
                "column_lineage": self.flags.enable_column_lineage,
            },

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
        logger.info(f"✓ Compliance: {compliance} ({compliance_confidence})")
        logger.info(f"✓ External dependencies: {len(external_deps)}")

        return context

    def extract_canonical_snapshot(self) -> CanonicalSnapshot:
        """Extract and persist a canonical snapshot for the current system."""
        context = self.extract_context()
        system_name = context.get("name", self.repo_path.name)
        system_id = deterministic_id("system", system_name)

        raw_candidates = self._collect_candidates(context)
        canonical_fields: dict[str, CanonicalFieldValue] = {}
        for field_name in (
            "owner",
            "domain",
            "lifecycle",
            "tier",
            "data_class",
            "experts",
            "compliance_flags",
        ):
            field_candidates = [
                candidate
                for candidate in raw_candidates
                if candidate.field_name == field_name
            ]
            canonical_fields[field_name] = self.precedence_resolver.resolve(
                field_name, field_candidates
            )

        system_entity = CanonicalEntity(
            entity_id=system_id,
            entity_type=CanonicalEntityType.SOFTWARE_SYSTEM,
            name=system_name,
            fields=canonical_fields,
        )

        external_entities: list[CanonicalEntity] = []
        relationships: list[CanonicalRelationship] = []
        for dependency in context.get("external_dependencies", []):
            dependency_name = dependency.get("name") or dependency.get("service")
            if not dependency_name:
                continue
            external_id = deterministic_id("external", dependency_name)
            external_entities.append(
                CanonicalEntity(
                    entity_id=external_id,
                    entity_type=CanonicalEntityType.EXTERNAL_SYSTEM,
                    name=dependency_name,
                    fields={},
                )
            )
            relationships.append(
                CanonicalRelationship(
                    relationship_id=deterministic_id(
                        system_id,
                        CanonicalRelationshipType.DEPENDS_ON.value,
                        external_id,
                    ),
                    source_entity_id=system_id,
                    relation_type=CanonicalRelationshipType.DEPENDS_ON,
                    target_entity_id=external_id,
                    confidence=float(dependency.get("classification_confidence", 1.0)),
                    provenance=[],
                )
            )

        extracted_at = datetime.now(timezone.utc)
        snapshot_id = deterministic_id(
            system_id,
            extracted_at.isoformat(),
            ",".join(sorted(entity.entity_id for entity in [system_entity, *external_entities])),
        )
        snapshot = CanonicalSnapshot(
            system_id=system_id,
            snapshot_id=snapshot_id,
            extracted_at=extracted_at,
            entities=[system_entity, *external_entities],
            relationships=relationships,
        )
        return self.snapshot_store.save(snapshot)

    def build_effective_view(
        self, system_id: str, snapshot_id: str
    ) -> dict[str, EffectiveFieldValue]:
        """Build generated+override effective field view for a snapshot."""
        snapshot = self.snapshot_store.get(system_id, snapshot_id)
        if snapshot is None:
            return {}
        system_entities = [
            entity
            for entity in snapshot.entities
            if entity.entity_type == CanonicalEntityType.SOFTWARE_SYSTEM
        ]
        if not system_entities:
            return {}

        system_entity = system_entities[0]
        merged: dict[str, EffectiveFieldValue] = {}
        for field_name, generated in system_entity.fields.items():
            field_path = f"system.{field_name}"
            override = self.override_store.get(system_id, field_path)
            merged[field_name] = self.merge_engine.merge_field(generated, override)
        return merged

    def _collect_candidates(self, context: dict[str, Any]) -> list[FieldCandidate]:
        """Collect candidates from harvesters and deterministic context mappings."""
        system_name = context.get("name", self.repo_path.name)
        candidates = self.service_universe_harvester.harvest(system_name)
        candidates.extend(self.repo_artifact_harvester.harvest())

        context_map = {
            "owner": ("owner", 0.7),
            "domain": ("domain", 0.7),
            "lifecycle": ("status", 0.7),
            "tier": ("tier", 0.7),
            "data_class": ("data_class", 0.7),
            "experts": ("active_experts", 0.75),
        }
        now = datetime.now(timezone.utc)
        for field_name, (context_key, confidence) in context_map.items():
            value = context.get(context_key)
            if value in (None, "", []):
                continue
            candidates.append(
                FieldCandidate(
                    field_name=field_name,
                    value=value,
                    source_type="heuristic",
                    source_path="context_manager",
                    source_hash="",
                    artifact_version="",
                    extraction_rule=f"context_map:{context_key}",
                    confidence=confidence,
                    last_seen=now,
                )
            )

        compliance_factors = context.get("compliance_factors", [])
        if compliance_factors:
            candidates.append(
                FieldCandidate(
                    field_name="compliance_flags",
                    value=compliance_factors,
                    source_type="heuristic",
                    source_path="context_manager",
                    source_hash="",
                    artifact_version="",
                    extraction_rule="context_map:compliance_factors",
                    confidence=0.6,
                    last_seen=now,
                )
            )

        return candidates

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
            dep_name = self._normalize_logical_name(
                dep.get('name') or dep.get('service') or 'External Service'
            )
            dep_type = dep.get('type') or dep.get('category') or 'external'
            relationships.append({
                "source": system_name,
                "destination": dep_name,
                "description": f"uses {dep_type}",
                "relationship_type": "uses",
            })

        return relationships

    def _normalize_logical_name(self, value: str) -> str:
        """Normalize raw endpoint/container-style names to a logical label."""
        label = str(value or "").strip()
        if not label:
            return "External Service"

        # Strip scheme/path if URL-like
        label = re.sub(r"^https?://", "", label, flags=re.IGNORECASE)
        label = label.split("/", 1)[0]

        # Remove trailing :port
        label = re.sub(r":\d{2,5}$", "", label)

        # Keep only host/service token and prettify
        label = label.split(".", 1)[0]
        label = label.replace("_", " ").replace("-", " ").strip()
        if not label:
            return "External Service"

        return label.title()

    def _generate_llm_description(self, system_name: str, purpose: str, domain: str, 
                                   owner: str, tier: str, status: str, 
                                   languages: list, frameworks: list) -> Optional[str]:
        """Generate rich LLM description using all metadata context."""
        if not self.llm_manager:
            return None

        # Build context for LLM
        langs_str = ", ".join([l.get("language", "") for l in languages[:3]]) if languages else "unknown"
        frameworks_str = ", ".join([f.get("framework", "") for f in frameworks[:3]]) if frameworks else "none detected"
        
        prompt = f"""Generate a concise 2-3 sentence description for this system.

System: {system_name}
Purpose: {purpose}
Domain: {domain}
Owner: {owner}
Tier: {tier}
Status: {status}
Languages: {langs_str}
Frameworks: {frameworks_str}

Provide a clear, technical description that explains what this system does, who owns it, and its current state.
Do not include metadata labels, just write the description naturally.

Description:"""

        try:
            response = self.llm_manager.generate_text(
                prompt,
                max_tokens=120,
                temperature=0.3,
                use_cache=True
            )

            if response:
                # Clean up response
                description = response.strip()
                # Remove any markdown or XML artifacts
                description = re.sub(r'<[^>]+>', '', description)
                description = re.sub(r'\*\*|__', '', description)
                # Ensure it ends properly
                if description and not description.endswith('.'):
                    description += '.'
                return description if len(description) > 20 else None

        except Exception as e:
            logger.debug(f"Failed to generate LLM description: {e}")

        return None
