## ADDED Requirements

### Requirement: Generated, override, and effective field views
The system SHALL expose and display generated values, override values, and
effective merged values for business context fields.

#### Scenario: Field shows generated and effective values
- **WHEN** a user opens system context details for WPS
- **THEN** each field presents generated and effective values, and override value when present

### Requirement: Field-level provenance visibility
The system SHALL display provenance details for generated business context
fields in the review UI.

#### Scenario: User inspects provenance for domain field
- **WHEN** a reviewer expands provenance for `domain`
- **THEN** the UI shows source metadata and confidence for the generated value

### Requirement: Override persistence with audit trail
The system SHALL persist field-level overrides with actor and timestamp audit
metadata.

#### Scenario: SME overrides owner field
- **WHEN** an editor submits an owner override with justification
- **THEN** the override is stored with `updated_by`, `field_updated_at`, and `override_reason`

### Requirement: Override lifecycle and stale detection
The system SHALL track override lifecycle states and flag stale overrides when
new extraction evidence materially conflicts.

#### Scenario: Override marked stale after conflicting higher-ranked source update
- **WHEN** a new snapshot introduces a conflicting value from a higher-ranked source
- **THEN** the existing override state is set to `stale` and `needs_review` is true

### Requirement: Review workflow state tracking
The system SHALL support system-level review status values `draft`,
`reviewed`, and `approved_for_publish`.

#### Scenario: Approver marks context ready
- **WHEN** an approver updates review status to `approved_for_publish`
- **THEN** the system records the new status and audit metadata

### Requirement: Snapshot diff and conflict highlighting
The system SHALL provide a diff view between extraction snapshots and highlight
fields that conflict with active overrides.

#### Scenario: Reviewer opens latest snapshot diff
- **WHEN** extracted values changed between current and previous snapshots
- **THEN** the UI highlights changed fields and identifies override conflicts
