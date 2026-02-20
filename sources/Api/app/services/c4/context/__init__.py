"""Context detection for C4 Model Level 1 (System Context)."""

from importlib import import_module

__all__ = [
    "ContextManager",
    "SystemDetector",
    "DependencyDetector",
    "MetadataDetector",
    "C4FeatureFlags",
    "CanonicalEntity",
    "CanonicalFieldValue",
    "CanonicalRelationship",
    "CanonicalSnapshot",
    "EffectiveFieldValue",
    "FieldCandidate",
    "FieldOverride",
    "OverrideStatus",
    "FieldPrecedenceResolver",
    "CanonicalSnapshotStore",
    "OverrideStore",
    "ContextMergeEngine",
    "APPROVED_RELATIONSHIP_TYPES",
    "REVIEW_STATUSES",
    "VALID_ROLES",
    "InMemoryContextStore",
    "Level1ContextResponse",
    "Level1ContextService",
    "Level1Relationship",
    "OverrideRequest",
    "ReviewStatusRequest",
]


_LAZY_IMPORTS = {
    "ContextManager": ("app.services.c4.context.context_manager", "ContextManager"),
    "SystemDetector": ("app.services.c4.context.system_detector", "SystemDetector"),
    "DependencyDetector": ("app.services.c4.context.dependency_detector", "DependencyDetector"),
    "MetadataDetector": ("app.services.c4.context.metadata_detector", "MetadataDetector"),
    "C4FeatureFlags": ("app.services.c4.context.feature_flags", "C4FeatureFlags"),
    "CanonicalEntity": ("app.services.c4.context.canonical_models", "CanonicalEntity"),
    "CanonicalFieldValue": ("app.services.c4.context.canonical_models", "CanonicalFieldValue"),
    "CanonicalRelationship": ("app.services.c4.context.canonical_models", "CanonicalRelationship"),
    "CanonicalSnapshot": ("app.services.c4.context.canonical_models", "CanonicalSnapshot"),
    "EffectiveFieldValue": ("app.services.c4.context.canonical_models", "EffectiveFieldValue"),
    "FieldCandidate": ("app.services.c4.context.canonical_models", "FieldCandidate"),
    "FieldOverride": ("app.services.c4.context.canonical_models", "FieldOverride"),
    "OverrideStatus": ("app.services.c4.context.canonical_models", "OverrideStatus"),
    "FieldPrecedenceResolver": ("app.services.c4.context.precedence", "FieldPrecedenceResolver"),
    "CanonicalSnapshotStore": ("app.services.c4.context.stores", "CanonicalSnapshotStore"),
    "OverrideStore": ("app.services.c4.context.stores", "OverrideStore"),
    "ContextMergeEngine": ("app.services.c4.context.merge_engine", "ContextMergeEngine"),
    "APPROVED_RELATIONSHIP_TYPES": (
        "app.services.c4.context.level1_context_service",
        "APPROVED_RELATIONSHIP_TYPES",
    ),
    "REVIEW_STATUSES": ("app.services.c4.context.level1_context_service", "REVIEW_STATUSES"),
    "VALID_ROLES": ("app.services.c4.context.level1_context_service", "VALID_ROLES"),
    "InMemoryContextStore": (
        "app.services.c4.context.level1_context_service",
        "InMemoryContextStore",
    ),
    "Level1ContextResponse": (
        "app.services.c4.context.level1_context_service",
        "Level1ContextResponse",
    ),
    "Level1ContextService": (
        "app.services.c4.context.level1_context_service",
        "Level1ContextService",
    ),
    "Level1Relationship": (
        "app.services.c4.context.level1_context_service",
        "Level1Relationship",
    ),
    "OverrideRequest": (
        "app.services.c4.context.level1_context_service",
        "OverrideRequest",
    ),
    "ReviewStatusRequest": (
        "app.services.c4.context.level1_context_service",
        "ReviewStatusRequest",
    ),
}


def __getattr__(name: str):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _LAZY_IMPORTS[name]
    module = import_module(module_name)
    return getattr(module, attribute_name)
