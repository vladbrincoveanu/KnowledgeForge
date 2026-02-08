"""Service extraction pipeline using discovery + git intelligence."""

import json
import logging
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from app.utils.fs_utils import limited_rglob
from app.domain.constants.technologies import LANGUAGE_EXTENSIONS, FRAMEWORK_INDICATORS
from app.domain.models.services import Service, ServiceStatus, ServiceTier, ContextNode
from app.services.service_extraction.dependency_extractor import DependencyExtractor
from app.services.service_extraction.domain_extractor import DomainExtractor
from app.services.service_extraction.extraction_config import ExtractionConfig
from app.services.service_extraction.git_full_analyzer import GitFullAnalyzer
from app.services.service_extraction.llm_budget import LLMCallBudget
from app.services.service_extraction.llm_service_enricher import ServiceLLMEnricher
from app.services.service_extraction.service_discoverer import ServiceDiscoverer
from app.services.service_extraction.smart_llm_enricher import SmartLLMEnricher
from app.services.service_extraction.description_generator import ServiceDescriptionGenerator
from app.services.service_extraction.context_node_extractor import ContextNodeExtractor

logger = logging.getLogger(__name__)


class ServiceExtractionPipeline:
    """Orchestrate service discovery, git intelligence, and enrichment."""

    def __init__(self, repo_root: Path, llm_manager: Optional[Any] = None):
        self.repo_root = Path(repo_root).resolve()
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.llm_manager = llm_manager
        self.llm_budget: Optional[LLMCallBudget] = None

        if llm_manager and getattr(ExtractionConfig, "LLM_BUDGET_TOKENS", 0) > 0:
            self.llm_budget = LLMCallBudget(getattr(ExtractionConfig, "LLM_BUDGET_TOKENS", 0))

        self.discoverer = ServiceDiscoverer(self.repo_root)
        self.git_analyzer = GitFullAnalyzer(self.repo_root)
        self.domain_extractor = DomainExtractor(self.repo_root)
        self.context_node_extractor = ContextNodeExtractor(self.repo_root)
        self.llm_label_enricher = ServiceLLMEnricher(
            llm_manager=llm_manager,
            max_tokens=ExtractionConfig.LLM_MAX_TOKENS,
            budget=self.llm_budget,
        ) if llm_manager else None
        self.note_enricher = SmartLLMEnricher(
            llm_manager=llm_manager,
            max_tokens=ExtractionConfig.LLM_MAX_TOKENS,
            budget=self.llm_budget,
        ) if llm_manager else None
        self.description_generator = ServiceDescriptionGenerator(
            llm_manager=llm_manager,
            max_tokens=ExtractionConfig.LLM_MAX_TOKENS,
            budget=self.llm_budget,
        )

    def extract_services(self) -> tuple[list[Service], list[ContextNode]]:
        """Run the full extraction pipeline and return services + context nodes."""
        logger.info("=" * 60)
        logger.info("STARTING SERVICE EXTRACTION PIPELINE")
        logger.info("=" * 60)
        logger.info(f"Repository root: {self.repo_root}")
        logger.info(f"Config: GIT_ANALYSIS={ExtractionConfig.ENABLE_GIT_ANALYSIS}, "
                   f"DOMAIN_DETECTION={ExtractionConfig.ENABLE_DOMAIN_DETECTION}, "
                   f"LLM_LABELS={getattr(ExtractionConfig, 'ENABLE_LLM_LABELS', False)}")
        
        services = self.discoverer.discover_services()
        self.errors.extend(self.discoverer.errors)
        self.warnings.extend(self.discoverer.warnings)
        logger.info(f"Discovered {len(services)} services")
        for svc in services:
            logger.info(f"  - {svc.name} (source={svc.source}, path={svc.file_path})")

        # Phase 1: Language detection (always runs)
        logger.info("-" * 40)
        logger.info("Phase 1: Language detection")
        for service in services:
            if not service.language:
                service_path = self._resolve_service_path(service)
                lang, framework = self._detect_language_and_framework(service_path)
                if lang:
                    service.language = lang
                    service.attributes.setdefault("inferred_fields", {})["language"] = {
                        "confidence": "medium",
                        "source": "file_analysis",
                    }
                    logger.info(f"  {service.name}: language={lang}")
                if framework and not service.framework:
                    service.framework = framework
                    service.attributes.setdefault("inferred_fields", {})["framework"] = {
                        "confidence": "medium",
                        "source": "dependency_analysis",
                    }
                    logger.info(f"  {service.name}: framework={framework}")

        # Phase 2: Git analysis
        logger.info("-" * 40)
        logger.info("Phase 2: Git analysis")
        if ExtractionConfig.ENABLE_GIT_ANALYSIS:
            for service in services:
                service_path = self._resolve_service_path(service)
                logger.info(f"  Analyzing {service.name} at {service_path}")
                self.git_analyzer.enrich_service(
                    service=service,
                    service_path=service_path,
                    max_contributors=max(1, ExtractionConfig.GIT_CONTRIBUTOR_LIMIT),
                )
                logger.info(f"    owner={service.owner}, status={service.status.value}, "
                           f"commits_30d={service.commit_count_30d}")
                
                # Always apply status fallback if still unknown
                if service.status == ServiceStatus.UNKNOWN:
                    self._apply_status_fallback(service)
                    logger.info(f"    status after fallback={service.status.value}")
        else:
            logger.info("  Git analysis disabled, applying status fallbacks anyway")
            for service in services:
                self._apply_status_fallback(service)

        # Phase 3: Domain detection
        logger.info("-" * 40)
        logger.info("Phase 3: Domain detection")
        if ExtractionConfig.ENABLE_DOMAIN_DETECTION:
            for service in services:
                if service.domain:
                    logger.info(f"  {service.name}: domain already set to {service.domain}")
                    continue
                service_path = self._resolve_service_path(service)
                if not service_path:
                    logger.info(f"  {service.name}: no service path, skipping domain detection")
                    continue
                scan_path = service_path if service_path.is_dir() else service_path.parent
                
                # Try code/import analysis first
                domain = self.domain_extractor.extract_domain(scan_path, service.name)
                if domain:
                    service.domain = domain
                    service.attributes.setdefault("inferred_fields", {})["domain"] = {
                        "confidence": "medium",
                        "source": "code_analysis",
                    }
                    logger.info(f"  {service.name}: domain={domain} (from code_analysis)")
                
                # Try README text if still missing
                if not service.domain:
                    readme_text = self._read_readme_text(service_path)
                    if readme_text:
                        inferred = self.domain_extractor.extract_domain_from_text(readme_text)
                        if inferred:
                            service.domain = inferred
                            service.attributes.setdefault("inferred_fields", {})["domain"] = {
                                "confidence": "low",
                                "source": "readme",
                            }
                            logger.info(f"  {service.name}: domain={inferred} (from readme)")
                
                # Fallback to Unclassified
                if not service.domain:
                    service.domain = "Unclassified"
                    service.attributes.setdefault("inferred_fields", {})["domain"] = {
                        "confidence": "low",
                        "source": "fallback",
                    }
                    logger.info(f"  {service.name}: domain=Unclassified (fallback)")

        # Phase 4: Dependency scanning
        logger.info("-" * 40)
        logger.info("Phase 4: Dependency scanning")
        if ExtractionConfig.ENABLE_DEPENDENCY_SCAN and services:
            dependency_extractor = DependencyExtractor(self.repo_root, services)
            for service in services:
                deps = dependency_extractor.extract_dependencies(service)
                if not deps:
                    continue
                merged = sorted(set(service.direct_depends or []) | set(deps))
                service.direct_depends = merged
                logger.info(f"  {service.name}: dependencies={deps}")
                for dep_id in deps:
                    if dep_id not in service.dependencies:
                        service.dependencies.append(dep_id)
                    target_service = dependency_extractor.service_map.get(dep_id)
                    if target_service and service.id not in target_service.dependents:
                        target_service.dependents.append(service.id)

        # Phase 5: LLM enrichment (if enabled)
        logger.info("-" * 40)
        logger.info("Phase 5: LLM enrichment")
        if getattr(ExtractionConfig, "ENABLE_LLM_LABELS", False) and self.llm_label_enricher:
            for service in services:
                if not self._needs_llm_labels(service):
                    logger.info(f"  {service.name}: all fields populated, skipping LLM")
                    continue
                service_path = self._resolve_service_path(service)
                if not service_path:
                    continue
                scan_path = service_path if service_path.is_dir() else service_path.parent
                logger.info(f"  {service.name}: calling LLM for enrichment...")
                enrichment = self._enrich_with_llm_labels(service, scan_path)
                if enrichment:
                    self._apply_llm_enrichment(service, enrichment)
                    logger.info(f"    LLM enrichment: {enrichment}")

                if not service.notes and self.note_enricher:
                    notes = self._generate_notes_with_timeout(service, scan_path)
                    if notes:
                        service.notes = notes
                        if not service.description:
                            service.description = notes
                        logger.info(f"    LLM notes: {notes[:100]}...")
        else:
            logger.info("  LLM enrichment disabled or no LLM manager")

        # Phase 6: Description generation
        logger.info("-" * 40)
        logger.info("Phase 6: Description generation")
        if getattr(ExtractionConfig, "ENABLE_LLM_DESCRIPTIONS", False):
            for service in services:
                if service.description:
                    continue
                service_path = self._resolve_service_path(service)
                if not service_path:
                    continue
                scan_path = service_path if service_path.is_dir() else service_path.parent
                description = self.description_generator.generate_description(
                    service_name=service.name,
                    service_path=scan_path,
                    language=service.language,
                    repo_root=self.repo_root,
                )
                if description:
                    service.description = description
                    logger.info(f"  {service.name}: description generated")

        # Phase 7: Final fallbacks for missing fields + Risk calculations
        logger.info("-" * 40)
        logger.info("Phase 7: Applying final fallbacks and calculating risk metrics")
        for service in services:
            self._apply_missing_field_fallbacks(service)

            # Calculate compliance risk (architectural compliance)
            service.compliance = self._calculate_compliance_risk(service)

        # Log final state
        logger.info("=" * 60)
        logger.info("EXTRACTION COMPLETE - FINAL SERVICE STATE")
        logger.info("=" * 60)
        for service in services:
            inferred = service.attributes.get("inferred_fields", {})
            logger.info(f"Service: {service.name}")
            logger.info(f"  domain={service.domain} (inferred={inferred.get('domain', {}).get('source', 'N/A')})")
            logger.info(f"  owner={service.owner}")
            logger.info(f"  status={service.status.value} (inferred={inferred.get('status', {}).get('source', 'N/A')})")
            logger.info(f"  tier={service.tier.value}")
            logger.info(f"  data_class={service.data_class}")
            logger.info(f"  active_experts={service.active_experts}, compliance={service.compliance}")
            logger.info(f"  language={service.language}, framework={service.framework}")
            logger.info(f"  notes={service.notes[:80] if service.notes else None}...")
            logger.info(f"  inferred_fields={list(inferred.keys())}")

        # Phase 6: Extract context nodes for architecture visualization
        logger.info("-" * 40)
        logger.info("Phase 6: Context node extraction")
        context_nodes: list[ContextNode] = []
        
        # Extract repo-level context nodes (README, Dockerfile, etc. at root)
        repo_nodes = self.context_node_extractor.extract_context_nodes(
            service_path=None,  # Use repo root
            service_id=None,
        )
        context_nodes.extend(repo_nodes)
        logger.info(f"  Found {len(repo_nodes)} repository-level context nodes")
        
        # Extract service-level context nodes
        for service in services:
            service_path = self._resolve_service_path(service)
            if service_path:
                service_nodes = self.context_node_extractor.extract_context_nodes(
                    service_path=service_path,
                    service_id=service.id,
                )
                context_nodes.extend(service_nodes)
                if service_nodes:
                    logger.info(f"  {service.name}: found {len(service_nodes)} context nodes")
        
        logger.info(f"Total context nodes extracted: {len(context_nodes)}")
        logger.info("=" * 60)
        logger.info("EXTRACTION COMPLETE")
        logger.info("=" * 60)

        return services, context_nodes

    def _needs_llm_labels(self, service: Service) -> bool:
        """Return True if any core field or notes are missing."""
        if not service.domain:
            return True
        if not service.owner:
            return True
        if service.status == ServiceStatus.UNKNOWN:
            return True
        if service.tier == ServiceTier.UNKNOWN:
            return True
        if not service.data_class:
            return True
        if not service.notes and not service.description:
            return True
        return False

    def _enrich_with_llm_labels(self, service: Service, scan_path: Path, timeout: int = 8) -> dict[str, Optional[str]]:
        """Run LLM label enrichment with a timeout to avoid hangs."""
        if not self.llm_label_enricher:
            return {}

        result: dict[str, Optional[str]] = {}
        error_container: dict[str, Optional[str]] = {"error": None}

        def _run():
            nonlocal result
            try:
                result = self.llm_label_enricher.enrich_service(
                    service,
                    scan_path,
                    repo_root=self.repo_root,
                )
            except Exception as e:
                error_container["error"] = str(e)
                logger.warning(f"LLM enrichment failed for {service.name}: {e}")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            self.warnings.append(f"LLM label enrichment timed out for service '{service.name}' after {timeout}s")
            logger.warning(f"LLM enrichment timed out for {service.name} after {timeout}s")
            return {}
        
        if error_container["error"]:
            self.warnings.append(f"LLM enrichment error for '{service.name}': {error_container['error']}")
            return {}

        return result or {}

    def _apply_llm_enrichment(self, service: Service, enrichment: dict[str, Optional[str]]) -> None:
        """Apply LLM enrichment and tag low-confidence fields."""
        if not enrichment:
            return

        inferred = service.attributes.setdefault("inferred_fields", {})

        domain = enrichment.get("domain")
        if not service.domain and domain:
            service.domain = domain
            inferred["domain"] = {"confidence": "low", "source": "llm"}

        owner = enrichment.get("owner")
        if not service.owner and owner:
            service.owner = owner
            inferred["owner"] = {"confidence": "low", "source": "llm"}

        status = enrichment.get("status")
        if service.status == ServiceStatus.UNKNOWN and status:
            service.status = self._normalize_status(status)
            inferred["status"] = {"confidence": "low", "source": "llm"}

        tier = enrichment.get("tier")
        if service.tier == ServiceTier.UNKNOWN and tier:
            service.tier = self._normalize_tier(tier)
            inferred["tier"] = {"confidence": "low", "source": "llm"}

        data_class = enrichment.get("data_class")
        if not service.data_class and data_class:
            service.data_class = data_class
            inferred["data_class"] = {"confidence": "low", "source": "llm"}

        notes = enrichment.get("notes")
        if notes and not service.notes:
            service.notes = notes
            if not service.description:
                service.description = notes
            inferred["notes"] = {"confidence": "low", "source": "llm"}

    def _normalize_status(self, value: str) -> ServiceStatus:
        lowered = value.strip().lower()
        if "deprecat" in lowered or "frozen" in lowered or "eol" in lowered:
            return ServiceStatus.DEPRECATED
        if "maint" in lowered or "bugfix" in lowered or "support" in lowered:
            return ServiceStatus.MAINTENANCE_ONLY
        if "active" in lowered or "dev" in lowered or "feature" in lowered:
            return ServiceStatus.ACTIVE_DEV
        return ServiceStatus.UNKNOWN

    def _normalize_tier(self, value: str) -> ServiceTier:
        lowered = value.strip().lower()
        if "tier 1" in lowered or "tier1" in lowered or "t1" == lowered or "critical" in lowered:
            return ServiceTier.TIER_1
        if "tier 2" in lowered or "tier2" in lowered or "t2" == lowered or "important" in lowered:
            return ServiceTier.TIER_2
        if "tier 3" in lowered or "tier3" in lowered or "t3" == lowered or "minor" in lowered:
            return ServiceTier.TIER_3
        return ServiceTier.UNKNOWN

    def _generate_notes_with_timeout(self, service: Service, scan_path: Path, timeout: int = 5) -> Optional[str]:
        """Run LLM notes generation with a timeout to avoid hangs."""
        if not self.note_enricher:
            return None

        result: dict[str, Optional[str]] = {"notes": None}

        def _run():
            result["notes"] = self.note_enricher.generate_notes(service, scan_path)

        thread = threading.Thread(target=_run)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            self.warnings.append(f"LLM notes timed out for service '{service.name}'")
            return None

        return result["notes"]

    def _apply_status_fallback(self, service: Service) -> None:
        """Infer status from commit counts when analyzer returns unknown."""
        if service.status != ServiceStatus.UNKNOWN:
            return

        inferred = service.attributes.setdefault("inferred_fields", {})

        # Active development: commits in last 30 days
        if service.commit_count_30d > 0:
            service.status = ServiceStatus.ACTIVE_DEV
            inferred["status"] = {"confidence": "medium", "source": "commit_counts"}
            return
        
        # Maintenance mode: commits in last 90 days but not 30
        if service.commit_count_90d > 0:
            service.status = ServiceStatus.MAINTENANCE_ONLY
            inferred["status"] = {"confidence": "low", "source": "commit_counts"}
            return
        
        # Low activity but not dead: commits in last 180 days but not 90
        if service.commit_count_180d > 0:
            service.status = ServiceStatus.MAINTENANCE_ONLY
            inferred["status"] = {"confidence": "low", "source": "commit_counts"}
            return
        
        # No commits in 180 days = deprecated/frozen
        if service.last_commit_date:
            service.status = ServiceStatus.DEPRECATED
            inferred["status"] = {"confidence": "low", "source": "commit_counts"}
            return
        
        # No commit history at all - mark as unknown but tag it
        inferred["status"] = {"confidence": "low", "source": "no_git_history"}

    def _apply_missing_field_fallbacks(self, service: Service) -> None:
        """Fill remaining fields with permissive guesses."""
        inferred = service.attributes.setdefault("inferred_fields", {})
        context_text = self._read_readme_text(self._resolve_service_path(service))

        if not service.owner:
            service.owner = "Unassigned"
            inferred["owner"] = {"confidence": "low", "source": "fallback"}

        if not service.notes and not service.description:
            description = None
            service_path = self._resolve_service_path(service)
            if service_path:
                scan_path = service_path if service_path.is_dir() else service_path.parent
                description = self.description_generator.generate_description(
                    service_name=service.name,
                    service_path=scan_path,
                    language=service.language,
                    repo_root=self.repo_root,
                )
            if description:
                service.notes = description
                service.description = description
                inferred["notes"] = {"confidence": "low", "source": "readme"}

        if not service.data_class:
            data_class = self._infer_data_class(context_text)
            if data_class:
                service.data_class = data_class
                inferred["data_class"] = {"confidence": "low", "source": "readme"}
            else:
                service.data_class = "Unknown"
                inferred["data_class"] = {"confidence": "low", "source": "fallback"}

        if service.tier == ServiceTier.UNKNOWN:
            tier = self._infer_tier(context_text)
            if tier != ServiceTier.UNKNOWN:
                service.tier = tier
                inferred["tier"] = {"confidence": "low", "source": "readme"}
            else:
                service.tier = ServiceTier.UNKNOWN
                inferred["tier"] = {"confidence": "low", "source": "fallback"}

    def _calculate_compliance_risk(self, service: Service) -> str:
        """
        Determine architectural compliance risk based on data sensitivity vs. service treatment.

        This checks if services handling sensitive data are properly prioritized and maintained.
        NOT about legal compliance (GDPR/SOC2) - about architectural best practices.

        Logic:
        - Sensitive data (PII/CC) + Low priority (Tier 3) → AT_RISK
        - Sensitive data (PII/CC) + Deprecated status → AT_RISK
        - Sensitive data (PII/CC) + No owner → NON_COMPLIANT
        - Sensitive data (PII/CC) + Tier 1/2 + Active + Has owner → COMPLIANT
        - Non-sensitive data → COMPLIANT (no risk)
        - Unknown data_class or tier → UNKNOWN

        Returns:
            "COMPLIANT" | "AT_RISK" | "NON_COMPLIANT" | "UNKNOWN"
        """
        data_class = service.data_class
        tier = service.tier
        status = service.status
        owner = service.owner

        # Unknown data classification or tier
        if not data_class or data_class == "Unknown" or tier == ServiceTier.UNKNOWN:
            return "UNKNOWN"

        # Check if service handles sensitive data
        is_sensitive = data_class in ["PII", "Credit-Card", "Secret"]

        if not is_sensitive:
            # Non-sensitive data is always compliant
            return "COMPLIANT"

        # Sensitive data checks
        # CRITICAL: No owner for sensitive data
        if not owner or owner == "Unassigned":
            logger.warning(f"Service {service.name} handles {data_class} but has no owner - NON_COMPLIANT")
            return "NON_COMPLIANT"

        # AT_RISK: Low priority for sensitive data
        if tier == ServiceTier.TIER_3:
            logger.warning(f"Service {service.name} handles {data_class} but is Tier 3 - AT_RISK")
            return "AT_RISK"

        # AT_RISK: Deprecated/frozen service with sensitive data
        if status in [ServiceStatus.DEPRECATED, ServiceStatus.UNKNOWN]:
            logger.warning(f"Service {service.name} handles {data_class} but status is {status.value} - AT_RISK")
            return "AT_RISK"

        # COMPLIANT: Sensitive data properly handled
        # (Tier 1/2, Active/Maintenance, Has owner)
        logger.info(f"Service {service.name} handles {data_class} and is properly managed - COMPLIANT")
        return "COMPLIANT"

    def _read_readme_text(self, service_path: Optional[Path]) -> str:
        """Read README content from service path or repo root."""
        if not service_path:
            service_path = self.repo_root
        if service_path.exists() and service_path.is_file():
            service_path = service_path.parent
        bases = [service_path, self.repo_root]
        for base in bases:
            for name in ["README.md", "README.rst", "readme.md", "readme.rst"]:
                candidate = base / name
                if candidate.exists():
                    try:
                        return candidate.read_text(encoding="utf-8", errors="ignore")[:4000]
                    except Exception:
                        continue
        return ""

    def _infer_data_class(self, text: str) -> Optional[str]:
        """Infer data class from README text."""
        if not text:
            return None
        lowered = text.lower()
        if any(token in lowered for token in ["credit card", "cardholder", "pci", "payment card"]):
            return "Credit-Card"
        if any(token in lowered for token in ["pii", "personally identifiable", "user data", "personal data"]):
            return "PII"
        if any(token in lowered for token in ["secret", "token", "credential", "password", "api key"]):
            return "Secret"
        if "public api" in lowered or "open api" in lowered:
            return "Public"
        if lowered:
            return "Internal"
        return None

    def _infer_tier(self, text: str) -> ServiceTier:
        """Infer service tier from README text."""
        if not text:
            return ServiceTier.UNKNOWN
        lowered = text.lower()
        if any(token in lowered for token in ["critical", "core", "auth", "identity", "payment", "billing", "checkout"]):
            return ServiceTier.TIER_1
        if any(token in lowered for token in ["api", "service", "worker", "queue", "processor"]):
            return ServiceTier.TIER_2
        return ServiceTier.TIER_3

    def _resolve_service_path(self, service: Service) -> Optional[Path]:
        """Resolve the filesystem path for a service based on known metadata."""
        if service.file_path:
            potential_path = self.repo_root / service.file_path
            if potential_path.exists():
                return potential_path
            fallback = self.repo_root / service.name
            if fallback.exists() and fallback.is_dir():
                return fallback
        else:
            potential_path = self.repo_root / service.name
            if potential_path.exists() and potential_path.is_dir():
                return potential_path
        return None

    def _detect_language_and_framework(self, service_path: Optional[Path]) -> tuple[Optional[str], Optional[str]]:
        """Detect primary language and framework from file extensions and manifests."""
        if not service_path:
            service_path = self.repo_root
        
        if service_path.is_file():
            service_path = service_path.parent
        
        if not service_path.exists():
            return None, None
        
        # Count file extensions
        ext_counts: Counter[str] = Counter()
        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".tox"}

        for file in limited_rglob(service_path, "*"):
            if any(part in skip_dirs for part in file.parts):
                continue
            if file.is_file():
                ext = file.suffix.lower()
                if ext in LANGUAGE_EXTENSIONS:
                    ext_counts[ext] += 1
        
        # Determine primary language from file count
        language = None
        if ext_counts:
            top_ext, _ = ext_counts.most_common(1)[0]
            language = LANGUAGE_EXTENSIONS.get(top_ext)
        
        # Check for framework indicators in manifests
        framework = None
        
        # Check package.json for JS/TS frameworks
        pkg_json = service_path / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                for dep_name in deps:
                    dep_lower = dep_name.lower()
                    for indicator, (lang, fw) in FRAMEWORK_INDICATORS.items():
                        if indicator in dep_lower:
                            if not language:
                                language = lang
                            framework = fw
                            break
                    if framework:
                        break
            except Exception:
                pass
        
        # Check requirements.txt / pyproject.toml for Python frameworks
        for manifest_name in ["requirements.txt", "pyproject.toml", "Pipfile"]:
            manifest = service_path / manifest_name
            if manifest.exists():
                try:
                    content = manifest.read_text(encoding="utf-8").lower()
                    for indicator, (lang, fw) in FRAMEWORK_INDICATORS.items():
                        if indicator in content:
                            if not language:
                                language = lang
                            framework = fw
                            break
                except Exception:
                    pass
                if framework:
                    break
        
        # Check go.mod for Go frameworks
        go_mod = service_path / "go.mod"
        if go_mod.exists():
            language = language or "Go"
            try:
                content = go_mod.read_text(encoding="utf-8").lower()
                for indicator, (lang, fw) in FRAMEWORK_INDICATORS.items():
                    if indicator in content:
                        framework = fw
                        break
            except Exception:
                pass
        
        # Check Cargo.toml for Rust frameworks
        cargo_toml = service_path / "Cargo.toml"
        if cargo_toml.exists():
            language = language or "Rust"
            try:
                content = cargo_toml.read_text(encoding="utf-8").lower()
                for indicator, (lang, fw) in FRAMEWORK_INDICATORS.items():
                    if indicator in content:
                        framework = fw
                        break
            except Exception:
                pass
        
        return language, framework
