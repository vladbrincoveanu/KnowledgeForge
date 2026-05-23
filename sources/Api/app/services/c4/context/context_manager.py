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
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from app.services.c4.enrichment import worker as enrichment_worker
from app.services.c4.enrichment.evidence_corpus import EvidenceCorpus, DepEvidence
from app.services.c4.context.decision_models import C4ElementType

from .system_detector import SystemDetector
from .dependency_detector import DependencyDetector
from .metadata_detector import MetadataDetector
from app.domain.review_queue import enqueue_review_item_if_low_confidence

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages Level 1 Context extraction for C4 Model."""

    def __init__(self, repo_path: Path, llm_manager=None,
                 containers: dict[str, Any] = None,
                 task_id: str = None):
        """Initialize Context Manager.

        Args:
            repo_path: Path to repository
            llm_manager: Optional LLM for generating descriptions
            containers: Optional dictionary of detected containers (for domain inference)
            task_id: Optional task ID for enrichment worker enqueue
        """
        self.repo_path = Path(repo_path).resolve()
        self.llm_manager = llm_manager
        self.containers = containers or {}
        self.task_id = task_id

        # Initialize detectors
        self.system_detector = SystemDetector(repo_path, llm_manager)
        self.dependency_detector = DependencyDetector(repo_path, llm_manager)
        self.metadata_detector = MetadataDetector(repo_path, llm_manager, containers)

    def _enrich_actors_with_element_type(self, actors: list[dict]) -> list[dict]:
        """Tag each actor with c4_element_type = Person."""
        for actor in actors:
            actor["c4_element_type"] = C4ElementType.PERSON
        return actors

    def _enrich_deps_with_element_type(self, deps: list[dict]) -> list[dict]:
        """Tag each dependency with its C4 element type.

        BUSINESS_SYSTEM → SoftwareSystem
        OWNED_CONTAINER → Container
        TECHNICAL_INFRA → Container (it's infrastructure you run, not an external SaaS)
        UNKNOWN         → SoftwareSystem (safer default for context diagram)
        """
        _type_map = {
            "BUSINESS_SYSTEM": C4ElementType.SOFTWARE_SYSTEM,
            "OWNED_CONTAINER": C4ElementType.CONTAINER,
            "TECHNICAL_INFRA": C4ElementType.CONTAINER,
            "UNKNOWN": C4ElementType.SOFTWARE_SYSTEM,
        }
        for dep in deps:
            dep_type = dep.get("dependency_type", "UNKNOWN")
            dep["c4_element_type"] = _type_map.get(dep_type, C4ElementType.SOFTWARE_SYSTEM)
        return deps

    def extract_context(self) -> dict[str, Any]:
        """Extract complete system context (Level 1).

        Returns:
            Dictionary with system context information
        """
        logger.info("Extracting C4 Level 1: System Context")

        extraction_run_id = str(uuid4())

        # System identification
        system_name = self.system_detector.detect_system_name()
        system_purpose = self.system_detector.generate_system_purpose()
        regulatory_frameworks = self.system_detector.detect_regulatory_frameworks()

        # External dependencies
        external_deps = self.dependency_detector.detect_external_dependencies()
        # Without LLM, drop documentation-only evidence — URLs in READMEs and
        # docs are indistinguishable from tutorial links and don't prove a
        # runtime integration (C4 Context shows only what the system calls).
        if self.llm_manager is None:
            external_deps = [
                d for d in external_deps
                if d.get("evidence_type") != "documentation_reference"
            ]
        external_deps = self._enrich_deps_with_element_type(external_deps)
        external_dep_reviews = self.dependency_detector.get_last_review_items()
        deployment_deps = self.dependency_detector.detect_deployment_dependencies()
        dependency_freshness_alerts = self.dependency_detector.detect_dependency_freshness_alerts()

        # Languages and frameworks
        languages = self.system_detector.detect_languages()
        frameworks = self.system_detector.detect_frameworks()

        # Actors
        actors = self.system_detector.detect_context_actors()
        actors = self._enrich_actors_with_element_type(actors)

        # Git and repository metadata
        git_metadata = self.system_detector.extract_git_metadata()
        repository_url = self.system_detector.get_repository_root_url()
        context_sources = self.system_detector.collect_context_sources(frameworks)

        # IT Landscape metadata
        owner_team, owner_provenance = self.metadata_detector.detect_owner_team()
        business_domain = self.metadata_detector.infer_business_domain()

        owner_confidence = owner_provenance.get("confidence", 0.0)
        if owner_confidence < 0.70:
            try:
                enqueue_review_item_if_low_confidence(
                    extraction_run_id=extraction_run_id,
                    field="owner",
                    candidate_values=[owner_team] if owner_team else [],
                    llm_suggestion=None,
                    confidence=owner_confidence,
                    evidence=[owner_provenance],
                )
            except Exception as exc:
                logger.debug("Review queue insert skipped (table may not exist): %s", exc)
        criticality = self.metadata_detector.determine_criticality(languages)
        data_class = self.metadata_detector.infer_data_classification()

        # If the repository looks infrastructure-focused, prefer General data class
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

        # Compliance risk assessment
        compliance, compliance_confidence, compliance_factors = self.metadata_detector.assess_compliance_risk(
            domain=business_domain,
            data_class=data_class,
            owner=owner_team,
            tier=criticality,
            status=status,
            active_experts=active_experts
        )

        # Generate LLM description
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
            "c4_element_type": C4ElementType.SOFTWARE_SYSTEM,
            "type": "system",
            "name": system_name,
            "purpose": system_purpose,
            "description": llm_description or system_purpose,
            "external_dependencies": external_deps,
            "external_dependency_review_items": external_dep_reviews,
            "deployment_dependencies": deployment_deps,
            "dependency_freshness_alerts": dependency_freshness_alerts,
            "actors": actors,
            "languages": languages,
            "frameworks": frameworks,
            "repository_url": repository_url,
            "git": git_metadata,
            "context_sources": context_sources,
            "regulatory_frameworks": regulatory_frameworks,

            # Primary Service Fields
            "domain": business_domain,
            "owner": owner_team,
            "owner_provenance": owner_provenance,
            "owner_contributors": contributor_stats.get("owner_contributors", []),
            "owner_contributor_stats": contributor_stats.get("owner_contributor_stats", []),
            "contributor_count": git_activity.get("contributor_count", 0),
            "status": status,
            "status_evidence": status_evidence,
            "tier": criticality,
            "data_class": data_class,
            "active_experts": active_experts,
            "compliance": compliance,
            "compliance_confidence": compliance_confidence,
            "compliance_factors": compliance_factors,

            # Git activity metrics
            "last_commit_date": git_activity.get("last_commit_date"),
            "commit_count_30d": git_activity.get("commit_count_30d", 0),
            "commit_count_90d": git_activity.get("commit_count_90d", 0),
            "commit_count_180d": git_activity.get("commit_count_180d", 0),
            "dora_metrics": dora_metrics,
            "on_call_channel": on_call_channel,

            # Legacy aliases
            "owner_team": owner_team,
            "business_domain": business_domain,
            "criticality": criticality,
        }

        logger.info(f"✓ System: {system_name}")
        logger.info(f"✓ Owner: {owner_team}")
        logger.info(f"✓ Domain: {business_domain}")
        logger.info(f"✓ Status: {status}")
        logger.info(f"✓ External dependencies: {len(external_deps)}")

        if self.task_id:
            evidence = EvidenceCorpus(
                repo_path=self.repo_path,
                task_id=self.task_id,
                languages=[l.get("language", "") for l in languages],
                frameworks=[f.get("framework", "") for f in frameworks],
                deterministic_deps=[
                    DepEvidence(
                        name=d.get("name") or d.get("context_name") or "",
                        type=d.get("dependency_type") or d.get("type") or "",
                        confidence=float(d.get("confidence", 0.5)),
                        files_found_in=[],
                    )
                    for d in external_deps
                ],
                entrypoints=[],
                detected_urls=[d.get("url") for d in external_deps if d.get("url")],
                env_vars=[],
                docker_images=[],
                package_files=[],
            )
            try:
                enrichment_worker.enqueue(
                    task_id=self.task_id,
                    repo_path=self.repo_path,
                    evidence=evidence,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("enrichment enqueue failed: %s", e)

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
                "description": self._relationship_description_from_actor(actor),
                "relationship_type": "uses",
            })

        # Names that are dev/docs tooling, not runtime software systems.
        # Per C4 book: L1 shows only systems the software *integrates with at runtime*.
        # Build tools, CI platforms, documentation sites, and GitOps descriptors belong
        # on deployment diagrams or are out of scope entirely.
        _dev_only_names = frozenset({
            "gitbook", "readthedocs", "confluence", "notion", "mkdocs",
            "gitops", "argocd", "argo", "flux", "kustomize",
            "github actions", "gitlab ci", "jenkins", "circleci", "travis",
            "docker hub", "ghcr", "quay",
            "localtest", "localhost", "example", "test",
            "ac",  # too short / ambiguous
        })

        # System -> External dependency relationships
        for dep in system_context.get('external_dependencies', []):
            if dep.get("review_status") == "needs_review":
                continue
            if dep.get("dependency_type") == "TECHNICAL_INFRA":
                continue
            dep_name = self._normalize_logical_name(
                dep.get('context_name')
                or dep.get('name')
                or dep.get('service')
                or 'External Service'
            )
            if dep_name.lower() in _dev_only_names:
                continue
            relationships.append({
                "source": system_name,
                "destination": dep_name,
                "description": self._relationship_description_from_dependency(
                    dep, dep_name,
                ),
                "relationship_type": "uses",
            })

        return relationships

    def _relationship_description_from_actor(self, actor: dict[str, Any]) -> str:
        """Return a business-focused sentence for an actor relationship."""
        description = self._clean_relationship_sentence(
            actor.get("description") or actor.get("role") or ""
        )
        return description or "Uses the system"

    def _relationship_description_from_dependency(
        self, dep: dict[str, Any], dep_name: str,
    ) -> str:
        """Return a business-focused sentence for an external dependency."""
        description = self._clean_relationship_sentence(dep.get("description"))
        if description:
            return description

        category = str(dep.get("category") or dep.get("type") or "").strip().lower()
        category_descriptions = {
            "ai": f"Uses {dep_name} for AI-powered capabilities",
            "analytics": f"Uses {dep_name} for analytics and insights",
            "authentication": f"Uses {dep_name} for authentication and identity",
            "communication": f"Uses {dep_name} for communication workflows",
            "crm": f"Uses {dep_name} for customer data workflows",
            "developer-platform": f"Uses {dep_name} for developer platform workflows",
            "edge": f"Uses {dep_name} for edge delivery",
            "email": f"Uses {dep_name} for email delivery",
            "incident-management": f"Uses {dep_name} for incident management",
            "maps": f"Uses {dep_name} for mapping and geolocation",
            "payment": f"Uses {dep_name} for payment processing",
            "project-management": f"Uses {dep_name} for project coordination",
            "search": f"Uses {dep_name} for search and discovery",
            "support": f"Uses {dep_name} for customer support workflows",
        }
        return category_descriptions.get(category, f"Integrates with {dep_name}")

    def _clean_relationship_sentence(self, value: Any) -> str:
        """Normalize relationship copy for edge labels."""
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        return text.rstrip(".")

    def _normalize_logical_name(self, value: str) -> str:
        """Normalize raw endpoint/container-style names to a logical label."""
        label = str(value or "").strip()
        if not label:
            return "External Service"

        # Strip scheme/path if URL-like
        label = re.sub(r"^https?://", "", label, flags=re.IGNORECASE)
        label = label.split("/", 1)[0]
        label = re.sub(r":\d{2,5}$", "", label)
        label = label.split(".", 1)[0]
        label = label.replace("_", " ").replace("-", " ").strip()
        label = re.sub(r"\s+\(([^)]+)\)$", "", label).strip()
        label = re.sub(r"\s+(api|sdk|client|endpoint|webhook)$", "", label, flags=re.IGNORECASE)
        if not label:
            return "External Service"

        return label.title()

    def _generate_llm_description(self, system_name: str, purpose: str, domain: str,
                                   owner: str, tier: str, status: str,
                                   languages: list, frameworks: list) -> Optional[str]:
        """Generate rich LLM description using all metadata context."""
        if not self.llm_manager:
            return None

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
                description = response.strip()
                description = re.sub(r'<[^>]+>', '', description)
                description = re.sub(r'\*\*|__', '', description)
                if description and not description.endswith('.'):
                    description += '.'
                return description if len(description) > 20 else None

        except Exception as e:
            logger.debug(f"Failed to generate LLM description: {e}")

        return None
