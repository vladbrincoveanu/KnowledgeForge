# WPS Quality Gate and Rollout Controls

## Purpose

This document defines executable quality checks and rollout guard policy for the
WPS-first context generation strategy.

## Scope

Applies to C4 Level-1 business context output before enabling non-WPS systems.

## Quality Checks

The WPS gate evaluates three checks:

1. `completeness`
- Definition: percentage of WPS services that have non-empty effective values
  for `owner`, `domain`, and `lifecycle`.
- Threshold: `>= 0.95`.

2. `provenance_coverage`
- Definition: percentage of non-null generated fields that include provenance
  entries.
- Threshold: `>= 0.98`.

3. `readability`
- Definition: percentage of service labels passing readability rules:
  - max length 60,
  - no slash-separated raw identifiers,
  - not machine-slug only.
- Threshold: `>= 0.90`.

## Rollout Guard Policy

Feature flags:

- `C4_ENABLE_WPS_QUALITY_GATE` (default `true`)
- `C4_ENABLE_WPS_ONLY_ROLLOUT` (default `true`)

Policy:

- WPS rollout is always allowed.
- For non-WPS systems:
  - if WPS quality gate is enabled and WPS-only rollout is enabled:
    rollout is blocked until WPS gate passes.
  - otherwise rollout is allowed.

## Implementation References

- `sources/Api/app/services/c4/context/quality_gate.py`
- `sources/Api/app/services/c4/context/feature_flags.py`
- `sources/Api/tests/unit/services/c4/test_wps_quality_gate.py`
- `sources/Api/tests/e2e/test_wps_quality_gate.py`

