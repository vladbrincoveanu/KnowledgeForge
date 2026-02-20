## ADDED Requirements

### Requirement: Canonical context snapshot generation
The system SHALL harvest metadata from service-universe YAML and repository-adjacent
artifacts and produce a versioned canonical snapshot per software system.

#### Scenario: Snapshot produced for WPS
- **WHEN** the ingestion pipeline runs for system `WPS`
- **THEN** a canonical snapshot is stored with deterministic `system_id` and `snapshot_id`

### Requirement: Stable entity and relationship identifiers
The system SHALL assign deterministic identifiers for entities and relationships
to ensure idempotent processing and diff-safe comparisons across runs.

#### Scenario: Identifiers remain stable across unchanged inputs
- **WHEN** the pipeline is executed multiple times over unchanged source artifacts
- **THEN** generated entity and relationship identifiers are byte-equivalent

### Requirement: Field-level provenance capture
The system SHALL record provenance metadata for each non-null generated field,
including source location and extraction confidence.

#### Scenario: Provenance attached to generated owner
- **WHEN** owner is extracted for a service from service-universe YAML
- **THEN** the field includes `source_type`, `source_path`, `source_hash`, `artifact_version`, `extraction_rule`, `confidence`, and `last_seen`

### Requirement: Source conflict resolution by precedence
The system SHALL resolve conflicting source values using the configured
field-specific precedence matrix and deterministic tie-breakers.

#### Scenario: Higher-ranked owner source overrides lower-ranked source
- **WHEN** `owner` is available from both service-universe YAML and commit inference
- **THEN** the effective generated owner uses the higher-ranked service-universe value

### Requirement: Unknown-state preservation
The system SHALL represent missing or low-confidence metadata as explicit unknown
states rather than inferring fabricated values.

#### Scenario: Unknown lifecycle retained when no trusted source exists
- **WHEN** no source provides lifecycle above the minimum confidence threshold
- **THEN** lifecycle is emitted as `unknown` with provenance indicating unresolved extraction
