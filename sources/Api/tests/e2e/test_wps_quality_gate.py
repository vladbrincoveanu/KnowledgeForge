"""E2E-style verification of WPS quality gate and rollout controls."""

from app.services.c4.context.feature_flags import C4FeatureFlags
from app.services.c4.context.quality_gate import can_rollout_system, evaluate_wps_quality_gate


def test_wps_gate_blocks_non_wps_rollout_until_quality_passes():
    # Simulated extracted effective records from WPS pipeline.
    wps_services = [
        {
            "name": "WPS Payments API",
            "display_name": "WPS Payments API",
            "owner": "Platform Team",
            "domain": "Payments",
            "lifecycle": "ACTIVE",
        },
        {
            "name": "wps-checkout",
            "display_name": "wps-checkout",  # intentionally poor readability
            "owner": "",
            "domain": "Commerce",
            "lifecycle": "ACTIVE",
        },
    ]
    wps_fields = [
        {"field": "owner", "value": "Platform Team", "provenance": [{"source_type": "codeowners"}]},
        {"field": "domain", "value": "Payments", "provenance": [{"source_type": "service_universe"}]},
        {"field": "lifecycle", "value": "ACTIVE", "provenance": [{"source_type": "service_universe"}]},
    ]
    failing_result = evaluate_wps_quality_gate(wps_services, wps_fields)
    assert failing_result.passed is False

    blocked = can_rollout_system(
        target_system="Billing",
        wps_result=failing_result,
        flags=C4FeatureFlags(enable_wps_quality_gate=True, enable_wps_only_rollout=True),
    )
    assert blocked is False

    # After SME validation/augmentation improved extraction output.
    fixed_services = [
        {
            "name": "WPS Payments API",
            "display_name": "WPS Payments API",
            "owner": "Platform Team",
            "domain": "Payments",
            "lifecycle": "ACTIVE",
        },
        {
            "name": "WPS Checkout",
            "display_name": "WPS Checkout",
            "owner": "Checkout Team",
            "domain": "Commerce",
            "lifecycle": "ACTIVE",
        },
    ]
    fixed_fields = [
        {"field": "owner", "value": "Platform Team", "provenance": [{"source_type": "codeowners"}]},
        {"field": "domain", "value": "Payments", "provenance": [{"source_type": "service_universe"}]},
        {"field": "lifecycle", "value": "ACTIVE", "provenance": [{"source_type": "service_universe"}]},
        {"field": "owner", "value": "Checkout Team", "provenance": [{"source_type": "codeowners"}]},
        {"field": "domain", "value": "Commerce", "provenance": [{"source_type": "service_universe"}]},
        {"field": "lifecycle", "value": "ACTIVE", "provenance": [{"source_type": "service_universe"}]},
    ]
    passing_result = evaluate_wps_quality_gate(fixed_services, fixed_fields)
    assert passing_result.passed is True

    allowed = can_rollout_system(
        target_system="Billing",
        wps_result=passing_result,
        flags=C4FeatureFlags(enable_wps_quality_gate=True, enable_wps_only_rollout=True),
    )
    assert allowed is True

