"""Unit tests for WPS quality gate and rollout guard."""

from app.services.c4.context.feature_flags import C4FeatureFlags
from app.services.c4.context.quality_gate import (
    QualityGateThresholds,
    can_rollout_system,
    evaluate_wps_quality_gate,
)


def test_quality_gate_passes_with_high_quality_inputs():
    services = [
        {
            "name": "WPS Payments API",
            "display_name": "WPS Payments API",
            "owner": "Platform Team",
            "domain": "Payments",
            "lifecycle": "ACTIVE",
        },
        {
            "name": "WPS Checkout Service",
            "display_name": "WPS Checkout Service",
            "owner": "Checkout Team",
            "domain": "Commerce",
            "lifecycle": "ACTIVE",
        },
    ]
    generated = [
        {"field": "owner", "value": "Platform Team", "provenance": [{"source_type": "codeowners"}]},
        {"field": "domain", "value": "Payments", "provenance": [{"source_type": "service_universe"}]},
        {"field": "lifecycle", "value": "ACTIVE", "provenance": [{"source_type": "service_universe"}]},
    ]
    result = evaluate_wps_quality_gate(services, generated)
    assert result.passed is True
    assert result.failed_checks == []


def test_quality_gate_fails_when_completeness_low():
    services = [
        {"name": "WPS Service A", "display_name": "WPS Service A", "owner": "A", "domain": "Payments", "lifecycle": "ACTIVE"},
        {"name": "wps-service-b", "display_name": "wps-service-b", "owner": None, "domain": "Payments", "lifecycle": ""},
    ]
    generated = [
        {"field": "owner", "value": "A", "provenance": [{"source_type": "codeowners"}]},
    ]
    result = evaluate_wps_quality_gate(services, generated)
    assert result.passed is False
    assert "completeness" in result.failed_checks


def test_rollout_guard_blocks_non_wps_when_wps_gate_fails():
    services = [{"name": "WPS", "display_name": "wps", "owner": None, "domain": None, "lifecycle": None}]
    generated = [{"field": "owner", "value": "unknown", "provenance": []}]
    failing = evaluate_wps_quality_gate(services, generated, thresholds=QualityGateThresholds())
    allowed = can_rollout_system(
        target_system="Billing",
        wps_result=failing,
        flags=C4FeatureFlags(enable_wps_quality_gate=True, enable_wps_only_rollout=True),
    )
    assert allowed is False


def test_rollout_guard_allows_non_wps_when_flag_disabled():
    allowed = can_rollout_system(
        target_system="Billing",
        wps_result=None,
        flags=C4FeatureFlags(enable_wps_quality_gate=True, enable_wps_only_rollout=False),
    )
    assert allowed is True

