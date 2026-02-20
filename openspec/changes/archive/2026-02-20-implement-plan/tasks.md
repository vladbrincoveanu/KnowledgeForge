## 1. Canonical Model and Metadata Harvesting

- [ ] 1.1 Define canonical context entities, stable ID generation rules, and relationship taxonomy in `sources/Api/app/services/c4/context/`.
- [ ] 1.2 Implement field schema and provenance model (`source_type`, `source_path`, `source_hash`, `artifact_version`, `extraction_rule`, `confidence`, `last_seen`) for generated values.
- [ ] 1.3 Implement harvesting/parsing adapters for service-universe YAML and adjacent repository artifacts within context-owned modules.
- [ ] 1.4 Implement field-level conflict resolution with precedence matrix and deterministic tie-breakers (`confidence`, `last_seen`, lexicographic source key).
- [ ] 1.5 Implement explicit unknown-state handling for unresolved/low-confidence fields instead of fabricated defaults.
- [ ] 1.6 Add unit tests for deterministic IDs, provenance attachment, precedence resolution, and unknown-state behavior.

## 2. Snapshot Persistence and Merge Engine

- [ ] 2.1 Implement versioned canonical snapshot persistence keyed by `(system_id, snapshot_id, extracted_at)`.
- [ ] 2.2 Implement field-level override persistence keyed by `(system_id, field_path)` with audit fields (`updated_by`, `field_updated_at`, `override_reason`).
- [ ] 2.3 Implement deterministic generated+override merge engine that returns generated, override, and effective values per field.
- [ ] 2.4 Implement override lifecycle states (`active`, `stale`, `superseded`) and `needs_review` drift detection rules.
- [ ] 2.5 Add integration tests covering snapshot creation, override updates, stale detection, and effective-view correctness.

## 3. C4 Level-1 Context Generation

- [x] 3.1 Implement system-scoped Level-1 context generation from explicit snapshot versions (starting with WPS).
- [x] 3.2 Enforce approved relationship taxonomy in rendering and emit validation signals for unsupported relation types.
- [x] 3.3 Implement confidence-threshold edge gating for automatic relationships in default Level-1 output.
- [x] 3.4 Add deterministic rendering checks to guarantee equivalent output for unchanged inputs and snapshot references.
- [x] 3.5 Add WPS relationship golden fixtures/regression tests to block rollout on unexpected edges.

## 4. API Contracts and Authorization Model

- [x] 4.1 Add/extend API endpoints to fetch context with generated, override, effective values and provenance metadata.
- [x] 4.2 Add/extend API endpoints for creating/updating overrides with audit metadata and validation.
- [x] 4.3 Add/extend API endpoints for review status transitions (`draft`, `reviewed`, `approved_for_publish`).
- [x] 4.4 Implement V1 role checks for `viewer`, `editor`, and `approver` actions in relevant endpoints.
- [x] 4.5 Add API tests for contract shape, validation failures, role restrictions, and merge behavior.

## 5. Business Context Validation UI

- [x] 5.1 Implement business-facing context view that displays concise labels and field states (`generated`, `overridden`, `missing`).
- [x] 5.2 Implement provenance inspection UI for generated fields and confidence display.
- [x] 5.3 Implement override editing UX with reason capture and optimistic update/error handling.
- [x] 5.4 Implement system review-status controls and status visualization in the UI.
- [x] 5.5 Implement snapshot diff view highlighting extracted changes and conflicts with active overrides.
- [x] 5.6 Add UI tests for field-state rendering, provenance view, override flows, and diff conflict indicators.

## 6. WPS-first Quality Gate and Rollout Controls

- [ ] 6.1 Implement WPS completeness checks (owner/domain/lifecycle coverage threshold) as executable validation.
- [ ] 6.2 Implement provenance-coverage and readability validations for WPS outputs.
- [ ] 6.3 Add rollout guard logic to keep non-WPS systems blocked until WPS gate criteria pass.
- [ ] 6.4 Add feature toggle or system-scoped activation path for WPS-only rollout.
- [ ] 6.5 Add regression tests validating gate pass/fail behavior and rollout blocking.

## 7. End-to-End Verification and Documentation

- [ ] 7.1 Add e2e tests in `sources/e2e/` for ingestion -> snapshot -> Level-1 generation -> UI validation loop on WPS.
- [ ] 7.2 Document canonical model, precedence policy, override lifecycle, and API contracts in `docs/architecture/`.
- [ ] 7.3 Run `make quick-check` and fix any regressions across API, UI, and e2e layers.
- [ ] 7.4 Validate OpenSpec change completeness with `openspec validate --type change implement-plan --strict`.
