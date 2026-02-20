"""Feature flags for C4 context quality gate and rollout behavior."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class C4FeatureFlags:
    """Runtime feature flags controlling context extraction and rollout."""

    enable_owner_steward: bool = True
    enable_sensitivity_tags: bool = True
    enable_quality_score: bool = False
    enable_usage_stats: bool = False
    enable_column_lineage: bool = False
    enable_platform_collapse: bool = True
    enable_structurizr_export: bool = True
    enable_mermaid_export: bool = True

    enable_wps_quality_gate: bool = True
    enable_wps_only_rollout: bool = True

    @classmethod
    def from_env(cls) -> "C4FeatureFlags":
        """Load feature flags from environment with safe defaults."""
        return cls(
            enable_owner_steward=_env_bool("KF_ENABLE_OWNER_STEWARD", cls.enable_owner_steward),
            enable_sensitivity_tags=_env_bool(
                "KF_ENABLE_SENSITIVITY_TAGS",
                cls.enable_sensitivity_tags,
            ),
            enable_quality_score=_env_bool("KF_ENABLE_QUALITY_SCORE", cls.enable_quality_score),
            enable_usage_stats=_env_bool("KF_ENABLE_USAGE_STATS", cls.enable_usage_stats),
            enable_column_lineage=_env_bool(
                "KF_ENABLE_COLUMN_LINEAGE",
                cls.enable_column_lineage,
            ),
            enable_platform_collapse=_env_bool(
                "KF_ENABLE_PLATFORM_COLLAPSE",
                cls.enable_platform_collapse,
            ),
            enable_structurizr_export=_env_bool(
                "KF_ENABLE_STRUCTURIZR_EXPORT",
                cls.enable_structurizr_export,
            ),
            enable_mermaid_export=_env_bool(
                "KF_ENABLE_MERMAID_EXPORT",
                cls.enable_mermaid_export,
            ),
            enable_wps_quality_gate=_env_bool(
                "C4_ENABLE_WPS_QUALITY_GATE",
                cls.enable_wps_quality_gate,
            ),
            enable_wps_only_rollout=_env_bool(
                "C4_ENABLE_WPS_ONLY_ROLLOUT",
                cls.enable_wps_only_rollout,
            ),
        )
