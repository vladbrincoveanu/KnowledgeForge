"""WPS quality gate evaluation and rollout guard logic."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .feature_flags import C4FeatureFlags


@dataclass
class QualityGateThresholds:
    """Thresholds for WPS-first quality gate checks."""

    completeness_min: float = 0.95
    provenance_coverage_min: float = 0.98
    readability_min: float = 0.90


@dataclass
class WpsQualityGateResult:
    """Result of WPS quality gate checks."""

    completeness_score: float
    provenance_coverage: float
    readability_score: float
    passed_checks: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.failed_checks) == 0


def evaluate_wps_quality_gate(
    service_records: list[dict[str, Any]],
    generated_field_records: list[dict[str, Any]],
    thresholds: QualityGateThresholds | None = None,
) -> WpsQualityGateResult:
    """Evaluate completeness, provenance, and readability checks for WPS."""
    checks = thresholds or QualityGateThresholds()

    completeness = _calculate_completeness(service_records)
    provenance_coverage = _calculate_provenance_coverage(generated_field_records)
    readability = _calculate_readability(service_records)

    passed_checks: list[str] = []
    failed_checks: list[str] = []

    if completeness >= checks.completeness_min:
        passed_checks.append("completeness")
    else:
        failed_checks.append("completeness")

    if provenance_coverage >= checks.provenance_coverage_min:
        passed_checks.append("provenance_coverage")
    else:
        failed_checks.append("provenance_coverage")

    if readability >= checks.readability_min:
        passed_checks.append("readability")
    else:
        failed_checks.append("readability")

    return WpsQualityGateResult(
        completeness_score=completeness,
        provenance_coverage=provenance_coverage,
        readability_score=readability,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
    )


def can_rollout_system(
    target_system: str,
    wps_result: WpsQualityGateResult | None,
    flags: C4FeatureFlags | None = None,
) -> bool:
    """Return whether rollout is allowed for a target system."""
    cfg = flags or C4FeatureFlags.from_env()
    if not cfg.enable_wps_quality_gate:
        return True
    if target_system.upper() == "WPS":
        return True

    if cfg.enable_wps_only_rollout:
        return bool(wps_result and wps_result.passed)

    return True


def _calculate_completeness(service_records: list[dict[str, Any]]) -> float:
    if not service_records:
        return 0.0
    required_fields = ("owner", "domain", "lifecycle")
    complete = 0
    for service in service_records:
        if all(_is_present(service.get(field)) for field in required_fields):
            complete += 1
    return complete / len(service_records)


def _calculate_provenance_coverage(generated_field_records: list[dict[str, Any]]) -> float:
    if not generated_field_records:
        return 0.0
    covered = 0
    for field in generated_field_records:
        value = field.get("value")
        provenance = field.get("provenance")
        if value in (None, "", "unknown"):
            continue
        if isinstance(provenance, list) and provenance:
            covered += 1
    non_null = len([field for field in generated_field_records if field.get("value") not in (None, "", "unknown")])
    if non_null == 0:
        return 1.0
    return covered / non_null


def _calculate_readability(service_records: list[dict[str, Any]]) -> float:
    if not service_records:
        return 0.0
    readable = 0
    for service in service_records:
        label = str(service.get("display_name") or service.get("name") or "").strip()
        if _is_readable(label):
            readable += 1
    return readable / len(service_records)


def _is_present(value: Any) -> bool:
    return value not in (None, "", "unknown", "UNKNOWN")


def _is_readable(label: str) -> bool:
    if not label:
        return False
    if len(label) > 60:
        return False
    if "/" in label:
        return False
    if re.fullmatch(r"[a-z0-9_.-]+", label):
        return False
    return True

