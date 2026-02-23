## ADDED Requirements

### Requirement: Backend-owned confidence review state
The system SHALL compute field-level review requirements in backend extraction output based on confidence threshold and mandatory field presence.

#### Scenario: Low-confidence fields trigger review
- **WHEN** a canonical field confidence is below `0.70`
- **THEN** the field is marked `requires_confirmation = true` and listed in `human_review.needs_confirmation_fields`

#### Scenario: High-confidence fields are not forced into review
- **WHEN** a canonical field confidence is `0.70` or higher and the field is present
- **THEN** the field is not included in `human_review.needs_confirmation_fields`

### Requirement: Human confirmations persist as repo facts
The system SHALL persist confirmed context corrections in a per-repo `facts.yml` file and reapply them in subsequent extractions.

#### Scenario: Feedback writes per-repo facts
- **WHEN** `POST /api/v1/code/scan/{task_id}/context-feedback` succeeds for a single-repo scan
- **THEN** the system writes merged confirmations to `sources/data/c4_facts/<repo_key>/facts.yml`

#### Scenario: Subsequent extraction reuses confirmed facts
- **WHEN** the same repository is extracted again
- **THEN** confirmed fields from facts are merged before response assembly and surfaced with source `human`

### Requirement: Optional service-universe input
The system SHALL use `service-universe.yaml` as an optional source and SHALL fall back to existing detector sources when it is absent or invalid.

#### Scenario: YAML source present
- **WHEN** `service-universe.yaml` is present and parseable
- **THEN** overlapping canonical fields are populated from YAML with high confidence metadata

#### Scenario: YAML source absent
- **WHEN** `service-universe.yaml` is not present
- **THEN** extraction completes successfully using existing detector and heuristic sources

