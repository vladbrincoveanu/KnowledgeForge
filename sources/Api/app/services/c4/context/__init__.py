"""Context detection for C4 Model Level 1 (System Context)."""

from importlib import import_module

__all__ = [
    "ContextManager",
    "SystemDetector",
    "DependencyDetector",
    "MetadataDetector",
    "C4FeatureFlags",
    "QualityGateThresholds",
    "WpsQualityGateResult",
    "evaluate_wps_quality_gate",
    "can_rollout_system",
]


_LAZY_IMPORTS = {
    "ContextManager": ("app.services.c4.context.context_manager", "ContextManager"),
    "SystemDetector": ("app.services.c4.context.system_detector", "SystemDetector"),
    "DependencyDetector": ("app.services.c4.context.dependency_detector", "DependencyDetector"),
    "MetadataDetector": ("app.services.c4.context.metadata_detector", "MetadataDetector"),
    "C4FeatureFlags": ("app.services.c4.context.feature_flags", "C4FeatureFlags"),
    "QualityGateThresholds": ("app.services.c4.context.quality_gate", "QualityGateThresholds"),
    "WpsQualityGateResult": ("app.services.c4.context.quality_gate", "WpsQualityGateResult"),
    "evaluate_wps_quality_gate": ("app.services.c4.context.quality_gate", "evaluate_wps_quality_gate"),
    "can_rollout_system": ("app.services.c4.context.quality_gate", "can_rollout_system"),
}


def __getattr__(name: str):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _LAZY_IMPORTS[name]
    module = import_module(module_name)
    return getattr(module, attribute_name)
