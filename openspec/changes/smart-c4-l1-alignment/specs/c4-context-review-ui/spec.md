## ADDED Requirements

### Requirement: Context review UI consumes backend review metadata
The UI SHALL open context review based on backend-provided `human_review` fields, with fallback to existing heuristics only when backend metadata is missing.

#### Scenario: Backend review metadata triggers dialog
- **WHEN** extraction results contain non-empty `human_review.needs_confirmation_fields`
- **THEN** the context review dialog opens with fields marked as needing confirmation

#### Scenario: Legacy payload fallback
- **WHEN** extraction results do not include `human_review`
- **THEN** the UI applies existing heuristic review trigger behavior

### Requirement: Expanded feedback submission
The UI SHALL submit expanded context feedback fields for business process and compliance confirmations.

#### Scenario: Dialog submits extended payload
- **WHEN** the reviewer applies corrections in context review
- **THEN** the payload includes `critical_business_processes`, `compliance_tags`, and optional `field_confirmations`

#### Scenario: Existing feedback fields remain supported
- **WHEN** the reviewer edits only actors or external dependencies
- **THEN** the payload remains valid and backend accepts it without requiring new fields

### Requirement: Node details show confidence and risk metadata
The UI SHALL display confidence/provenance indicators for canonical fields and the derived risk indicator in node details.

#### Scenario: System node with canonical metadata
- **WHEN** a system node is selected and canonical metadata exists
- **THEN** node details show confidence/source badges and risk indicator state

