"""Container detection for C4 Model Level 2 (Containers)."""

from .container_manager import ContainerManager
from .base_detector import BaseContainerDetector
from .structure_detector import StructureDetector
from .compose_detector import ComposeDetector
from .helm_detector import HelmDetector
from .terraform_detector import TerraformDetector
from .utils import is_deployable_service
from .llm_enrichment import (
    enrich_containers,
    build_evidence_bundle,
    build_enrichment_prompt,
    parse_llm_enrichment_response,
    apply_enrichments,
)

__all__ = [
    'ContainerManager',
    'BaseContainerDetector',
    'StructureDetector',
    'ComposeDetector',
    'HelmDetector',
    'TerraformDetector',
    'is_deployable_service',
    'enrich_containers',
    'build_evidence_bundle',
    'build_enrichment_prompt',
    'parse_llm_enrichment_response',
    'apply_enrichments',
]
