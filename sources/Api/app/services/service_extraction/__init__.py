"""Compatibility exports for legacy service extraction imports."""

from app.utils.github_downloader import GitHubDownloader

# Import new modules for Agent 3
from app.services.service_extraction.api_surface_detector import detect_api_surface_types
from app.services.service_extraction.deployment_target_detector import detect_deployment_targets
from app.services.service_extraction.documentation_quality_scorer import score_documentation_quality
from app.services.service_extraction.inter_service_comm_detector import detect_inter_service_comms
from app.services.service_extraction.auth_scanner import scan_auth, AUTH_NONE, AUTH_JWT, AUTH_OAUTH, AUTH_APIKEY, AUTH_MTLS
from app.services.service_extraction.compliance_scorer import ComplianceScorer
from app.services.service_extraction.bus_factor_calculator import calculate_bus_factor
from app.services.service_extraction.service_enhancers import (
    enhance_with_bus_factor,
    enhance_with_auth_scanning,
    enhance_with_documentation_quality,
    enhance_with_deployment_targets,
    enhance_with_inter_service_comms,
    enhance_with_business_domain,
    enhance_with_api_surface_types,
)

__all__ = [
    "GitHubDownloader",
    "detect_api_surface_types",
    "detect_deployment_targets",
    "score_documentation_quality",
    "detect_inter_service_comms",
    "scan_auth",
    "AUTH_NONE",
    "AUTH_JWT",
    "AUTH_OAUTH",
    "AUTH_APIKEY",
    "AUTH_MTLS",
    "ComplianceScorer",
    "calculate_bus_factor",
    "enhance_with_bus_factor",
    "enhance_with_auth_scanning",
    "enhance_with_documentation_quality",
    "enhance_with_deployment_targets",
    "enhance_with_inter_service_comms",
    "enhance_with_business_domain",
    "enhance_with_api_surface_types",
]
