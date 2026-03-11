"""Service Enhancers - Phase 8 of Service Extraction Pipeline.

Enriches extracted services with additional context-level fields:
- Bus factor
- Auth scanning
- Documentation quality
- Deployment targets
- Inter-service communications
- Business domain
- API surface types
"""

import logging
from pathlib import Path
from typing import Any, List

logger = logging.getLogger(__name__)


def enhance_with_bus_factor(services: List[Any], repo_path: Path) -> None:
    """Enrich services with bus factor scores."""
    from app.services.service_extraction.bus_factor_calculator import calculate_bus_factor

    result = calculate_bus_factor(repo_path)

    for svc in services:
        svc.bus_factor = result.bus_factor_score
        # Also set legacy field for compatibility
        if hasattr(svc, 'active_experts'):
            svc.active_experts = result.contributor_count


def enhance_with_auth_scanning(services: List[Any], repo_path: Path) -> None:
    """Enrich services with authentication types."""
    from app.services.service_extraction.auth_scanner import scan_auth

    auth_types = scan_auth(repo_path)

    for svc in services:
        svc.auth_types = auth_types
        # Set default if none detected
        if not auth_types or auth_types == ["None"]:
            svc.auth_types = ["None"]


def enhance_with_documentation_quality(services: List[Any], repo_path: Path) -> None:
    """Enrich services with documentation quality scores."""
    from app.services.service_extraction.documentation_quality_scorer import score_documentation_quality

    score = score_documentation_quality(repo_path)

    for svc in services:
        svc.documentation_quality = score


def enhance_with_deployment_targets(services: List[Any], repo_path: Path) -> None:
    """Enrich services with deployment targets."""
    from app.services.service_extraction.deployment_target_detector import detect_deployment_targets

    targets = detect_deployment_targets(repo_path)

    for svc in services:
        svc.deployment_targets = targets if targets else []


def enhance_with_inter_service_comms(services: List[Any], repo_path: Path) -> None:
    """Enrich services with inter-service communication patterns."""
    from app.services.service_extraction.inter_service_comm_detector import detect_inter_service_comms

    comms = detect_inter_service_comms(repo_path)

    for svc in services:
        svc.inter_service_comms = comms


def enhance_with_business_domain(services: List[Any], repo_path: Path) -> None:
    """Enrich services with business domain classification.

    Note: Uses metadata_detector.infer_business_domain() for C4 Context.
    This enhancer is for Service-level metadata.
    """
    # Business domain is primarily detected at C4 Context level via metadata_detector
    # This is a placeholder for service-level domain if needed
    for svc in services:
        if hasattr(svc, 'business_domain') and not svc.business_domain:
            # Fall back to generic if not already set
            svc.business_domain = "General"


def enhance_with_api_surface_types(services: List[Any], repo_path: Path) -> None:
    """Enrich services with API surface types."""
    from app.services.service_extraction.api_surface_detector import detect_api_surface_types

    api_types = detect_api_surface_types(repo_path)

    for svc in services:
        svc.api_surface_types = api_types if api_types else []
