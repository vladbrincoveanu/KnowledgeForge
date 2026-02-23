## ADDED Requirements

### Requirement: Canonical C4 context properties with provenance
The system SHALL expose canonical C4 Level 1 properties in `system_context.canonical_properties`, where each property includes value, confidence, source, mandatory, confirmation-required, and human-confirmation metadata.

#### Scenario: Canonical properties are included in extraction results
- **WHEN** a C4 extraction task completes and results are retrieved
- **THEN** `system_context.canonical_properties` is present and contains canonical field objects

#### Scenario: Mandatory missing fields are review-gated
- **WHEN** a mandatory canonical field is missing
- **THEN** that field is marked with `requires_confirmation = true` and included in `human_review.missing_mandatory_fields`

### Requirement: Additive API compatibility for new context metadata
The system SHALL add new context metadata keys without removing existing legacy keys from current API payloads.

#### Scenario: Existing consumers continue receiving legacy fields
- **WHEN** clients call `GET /api/v1/code/architecture`
- **THEN** legacy context fields such as `owner`, `owner_team`, `status`, and `external_dependencies` remain available

#### Scenario: New metadata is returned in same payload
- **WHEN** clients call `GET /api/v1/code/scan/{task_id}/results`
- **THEN** the payload includes `canonical_properties`, `human_review`, `risk_indicator`, and `contributor_spread` in `system_context`

