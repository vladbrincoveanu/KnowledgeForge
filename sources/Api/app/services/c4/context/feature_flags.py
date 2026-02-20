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
    """Runtime flags for WPS-first rollout controls."""

    enable_wps_quality_gate: bool = True
    enable_wps_only_rollout: bool = True

    @classmethod
    def from_env(cls) -> "C4FeatureFlags":
        return cls(
            enable_wps_quality_gate=_env_bool("C4_ENABLE_WPS_QUALITY_GATE", True),
            enable_wps_only_rollout=_env_bool("C4_ENABLE_WPS_ONLY_ROLLOUT", True),
        )

