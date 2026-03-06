"""Context detection for C4 Model Level 1 (System Context)."""

from .context_manager import ContextManager
from .system_detector import SystemDetector
from .dependency_detector import DependencyDetector
from .metadata_detector import MetadataDetector
from .feature_flags import C4FeatureFlags
from .canonical_models import (
    CanonicalEntity,
    CanonicalEntityType,
    CanonicalRelationship,
    CanonicalRelationshipType,
)

__all__ = [
    'ContextManager',
    'SystemDetector',
    'DependencyDetector',
    'MetadataDetector',
    'C4FeatureFlags',
    'CanonicalEntity',
    'CanonicalEntityType',
    'CanonicalRelationship',
    'CanonicalRelationshipType',
]
