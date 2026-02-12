"""Service extractor that identifies services from code and configuration files."""

import logging
from pathlib import Path
from typing import Any, Optional

from app.domain.models.services import Service
from app.services.service_extraction.extraction_config import ExtractionConfig
from app.services.service_extraction.domain_extractor import DomainExtractor
from app.services.service_extraction.dependency_extractor import DependencyExtractor
from app.services.service_extraction.description_generator import ServiceDescriptionGenerator
from app.services.service_extraction.llm_service_enricher import ServiceLLMEnricher
from app.services.service_extraction.llm_budget import LLMCallBudget
from app.services.service_extraction.git_contributor_analyzer import GitContributorAnalyzer
from app.services.service_extraction.git_status_analyzer import GitStatusAnalyzer
from app.services.service_extraction.source_extractors import (
    extract_from_docker_compose,
    extract_from_kubernetes,
    extract_from_api_routes,
    extract_from_service_configs,
    extract_from_microservice_patterns,
    extract_from_top_level_directories,
)
from app.services.service_extraction.service_enhancers import (
    enhance_with_git_status,
    enhance_with_domain_detection,
    enhance_with_dependencies,
    enhance_with_descriptions,
    enhance_with_llm_enrichment,
    enhance_with_api_surface_types,
    enhance_with_inter_service_comms,
    enhance_with_business_domain,
    enhance_with_documentation_quality,
    enhance_with_deployment_targets,
    enhance_with_bus_factor,
    enhance_with_auth_scanning,
)

logger = logging.getLogger(__name__)


class ServiceExtractor:
    """Extract services from repository code and configuration files."""

    def __init__(self, repo_root: Path, llm_manager: Optional[Any] = None):
        self.repo_root = Path(repo_root).resolve()
        self.services: list[Service] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.git_analyzer = GitStatusAnalyzer(self.repo_root)
        self.contributor_analyzer = GitContributorAnalyzer(self.repo_root)
        self.domain_extractor = DomainExtractor(self.repo_root)
        self.dependency_extractor: Optional[DependencyExtractor] = None
        self.llm_manager = llm_manager
        self.llm_budget: Optional[LLMCallBudget] = None
        if llm_manager and getattr(ExtractionConfig, 'LLM_BUDGET_TOKENS', 0) > 0:
            self.llm_budget = LLMCallBudget(getattr(ExtractionConfig, 'LLM_BUDGET_TOKENS', 0))
        self.description_generator = ServiceDescriptionGenerator(
            llm_manager=llm_manager,
            max_tokens=ExtractionConfig.LLM_MAX_TOKENS,
            budget=self.llm_budget,
        )
        self.llm_enricher = (
            ServiceLLMEnricher(
                llm_manager=llm_manager,
                max_tokens=ExtractionConfig.LLM_MAX_TOKENS,
                budget=self.llm_budget,
            )
            if llm_manager
            else None
        )

    def extract_services(self) -> list[Service]:
        """Extract all services from the repository."""
        self.services = []
        self.errors = []
        self.warnings = []

        logger.info(f"Starting service extraction from {self.repo_root}")

        # 6 extraction steps from different sources
        extraction_steps = [
            ("docker-compose files", extract_from_docker_compose),
            ("Kubernetes manifests", extract_from_kubernetes),
            ("API route files", extract_from_api_routes),
            ("service configuration files", extract_from_service_configs),
            ("microservice patterns", extract_from_microservice_patterns),
            ("top-level directories", extract_from_top_level_directories),
        ]

        for i, (label, extractor_fn) in enumerate(extraction_steps, 1):
            try:
                logger.info(f"Step {i}/6: Extracting from {label}...")
                new_services = extractor_fn(
                    self.repo_root, self.services, self.errors, self.warnings,
                )
                self.services.extend(new_services)
                logger.info(f"After {label}: {len(self.services)} services found")
            except Exception as e:
                logger.error(f"Error extracting from {label}: {e}", exc_info=True)
                self.errors.append(f"{label} extraction failed: {str(e)}")

        # Enhancement steps
        self._run_enhancements()

        logger.info(
            f"Extraction completed: {len(self.services)} services extracted, "
            f"{len(self.errors)} errors, {len(self.warnings)} warnings"
        )
        return self.services

    def _run_enhancements(self) -> None:
        """Run optional enhancement steps on extracted services."""
        if ExtractionConfig.ENABLE_GIT_ANALYSIS:
            try:
                logger.info("Enhancing with git status analysis...")
                enhance_with_git_status(
                    self.services, self.repo_root,
                    self.git_analyzer, self.contributor_analyzer,
                    ExtractionConfig.GIT_CONTRIBUTOR_LIMIT,
                )
                logger.info("Git status enhancement completed")
            except Exception as e:
                logger.error(f"Error in git status enhancement: {e}", exc_info=True)
                self.errors.append(f"git status enhancement failed: {str(e)}")

        if ExtractionConfig.ENABLE_DOMAIN_DETECTION:
            try:
                logger.info("Enhancing with domain detection...")
                enhance_with_domain_detection(
                    self.services, self.repo_root, self.domain_extractor,
                )
                logger.info("Domain detection enhancement completed")
            except Exception as e:
                logger.error(f"Error in domain detection: {e}", exc_info=True)
                self.errors.append(f"domain detection enhancement failed: {str(e)}")

        if ExtractionConfig.ENABLE_DEPENDENCY_SCAN:
            try:
                logger.info("Enhancing with dependency scan...")
                enhance_with_dependencies(
                    self.services, self.repo_root, DependencyExtractor,
                )
                logger.info("Dependency scan enhancement completed")
            except Exception as e:
                logger.error(f"Error in dependency scan: {e}", exc_info=True)
                self.errors.append(f"dependency scan enhancement failed: {str(e)}")

        try:
            logger.info("Detecting API surface types...")
            enhance_with_api_surface_types(self.services, self.repo_root)
            logger.info("API surface type detection completed")
        except Exception as e:
            logger.error(f"Error in API surface type detection: {e}", exc_info=True)
            self.errors.append(f"API surface type detection failed: {str(e)}")

        try:
            logger.info("Detecting inter-service communications...")
            enhance_with_inter_service_comms(self.services, self.repo_root)
            logger.info("Inter-service comm detection completed")
        except Exception as e:
            logger.error(f"Error in inter-service comm detection: {e}", exc_info=True)
            self.errors.append(f"Inter-service comm detection failed: {str(e)}")

        try:
            logger.info("Classifying business domains...")
            enhance_with_business_domain(self.services, self.repo_root, self.llm_manager)
            logger.info("Business domain classification completed")
        except Exception as e:
            logger.error(f"Error in business domain classification: {e}", exc_info=True)
            self.errors.append(f"Business domain classification failed: {str(e)}")

        try:
            logger.info("Scoring documentation quality...")
            enhance_with_documentation_quality(self.services, self.repo_root)
            logger.info("Documentation quality scoring completed")
        except Exception as e:
            logger.error(f"Error in documentation quality scoring: {e}", exc_info=True)
            self.errors.append(f"Documentation quality scoring failed: {str(e)}")

        try:
            logger.info("Detecting deployment targets...")
            enhance_with_deployment_targets(self.services, self.repo_root)
            logger.info("Deployment target detection completed")
        except Exception as e:
            logger.error(f"Error in deployment target detection: {e}", exc_info=True)
            self.errors.append(f"Deployment target detection failed: {str(e)}")

        try:
            logger.info("Computing bus factor scores...")
            enhance_with_bus_factor(self.services, self.repo_root)
            logger.info("Bus factor computation completed")
        except Exception as e:
            logger.error(f"Error computing bus factor: {e}", exc_info=True)
            self.errors.append(f"Bus factor computation failed: {str(e)}")

        try:
            logger.info("Scanning auth configurations...")
            enhance_with_auth_scanning(self.services, self.repo_root)
            logger.info("Auth scanning completed")
        except Exception as e:
            logger.error(f"Error in auth scanning: {e}", exc_info=True)
            self.errors.append(f"Auth scanning failed: {str(e)}")

        # LLM enrichment with availability check
        enable_llm = getattr(ExtractionConfig, 'ENABLE_LLM_DESCRIPTIONS', False)
        enable_llm_labels = getattr(ExtractionConfig, 'ENABLE_LLM_LABELS', False)

        llm_available = self._check_llm_availability() if (enable_llm_labels or enable_llm) else False

        if enable_llm_labels:
            try:
                if not llm_available:
                    logger.warning("LLM labels enabled but models probe failed; attempting enrichment anyway")
                if not self.llm_enricher:
                    logger.error("LLM labels enabled but llm_enricher is None")
                else:
                    logger.info("Enhancing with LLM labels...")
                    enhance_with_llm_enrichment(
                        self.services, self.repo_root, self.llm_enricher,
                    )
                logger.info("LLM labels enhancement completed")
            except Exception as e:
                logger.error(f"Error in LLM labels enrichment: {e}", exc_info=True)
                self.errors.append(f"LLM labels enhancement failed: {str(e)}")

        if enable_llm and llm_available:
            try:
                logger.info("Enhancing with LLM descriptions...")
                enhance_with_descriptions(
                    self.services, self.repo_root, self.description_generator,
                )
                logger.info("LLM descriptions enhancement completed")
            except Exception as e:
                logger.error(f"Error in LLM descriptions: {e}", exc_info=True)
                self.errors.append(f"LLM descriptions enhancement failed: {str(e)}")
        elif enable_llm and not llm_available:
            logger.info("Skipping LLM descriptions enrichment - LLM not available")

    def _check_llm_availability(self) -> bool:
        """Quick connectivity check for the LLM service."""
        try:
            if not self.llm_manager:
                return False
            import requests
            if not hasattr(self.llm_manager, 'base_url'):
                return False
            base_url = str(self.llm_manager.base_url).rstrip("/")
            test_url = f"{base_url}/v1/models" if not base_url.endswith("/v1") else f"{base_url}/models"
            headers = {}
            if getattr(self.llm_manager, "use_openai", False) and getattr(self.llm_manager, "openai_api_key", None):
                headers["Authorization"] = f"Bearer {self.llm_manager.openai_api_key}"
            response = requests.get(test_url, headers=headers, timeout=2)
            if headers:
                return response.status_code == 200
            return response.status_code in [200, 401, 403]
        except Exception as e:
            logger.warning(f"LLM availability check failed: {e}, skipping LLM enrichment")
            return False
