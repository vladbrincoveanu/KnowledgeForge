## Context

KnowledgeForge currently has extraction and C4 context capabilities, but the
flow from raw service metadata to stakeholder-validated business context is not
fully standardized end-to-end. The target change introduces a reliable pipeline
that ingests service-universe YAML and repository-adjacent artifacts, builds a
normalized context model, generates C4 Level-1 context output per system
(starting with WPS), and exposes a concise UI for SME review and augmentation.

Constraints and stakeholders:
- Scope ownership is centered on `sources/Api/app/services/c4/context/`; avoid
  uncoordinated changes in `sources/Api/app/services/c4/containers/`.
- Metadata quality is uneven across repositories and must be represented with
  confidence and provenance to support expert validation.
- Primary consumers are platform engineers, architects, and business/domain
  SMEs who need both technical and human-readable context.

## Goals / Non-Goals

**Goals:**
- Define a deterministic ingestion and enrichment flow that extracts rich
  metadata (domain, owner, status/lifecycle, tier, data class, experts,
  compliance, external system relations).
- Generate accurate C4 Level-1 context structures for each software system,
  with WPS as the first quality benchmark.
- Provide an interactive, business-friendly review experience for SMEs to
  validate, correct, and augment generated context.
- Preserve provenance for every generated field so edits and confidence can be
  traced back to source artifacts.
- Enable repeatable e2e validation across API, UI, and pipeline tests.

**Non-Goals:**
- Building deeper diagram levels (C4 Level-2/Level-3) in this change.
- Replacing existing repository metadata standards or YAML authoring practices.
- Automating SME approval workflows outside the KnowledgeForge UI.
- Refactoring unrelated API/UI modules with no impact on context extraction or
  validation flow.

## Decisions

### 1) Canonical Context Model with Provenance

Decision:
- Introduce/standardize a canonical internal model in API context services that
  stores normalized business/architecture fields plus provenance and audit
  metadata.

Rationale:
- A canonical model isolates extraction variability from downstream C4 and UI
  logic and enables deterministic rendering and auditing.

Alternatives considered:
- Directly rendering from raw YAML/repository parse trees.
  - Rejected because it tightly couples rendering to source formats and makes
    validation/augmentation persistence fragile.

Canonical model specification:
- Entity types: `SoftwareSystem`, `ExternalSystem`, `OrganizationUnit`,
  `Person`, `DataStore`.
- Stable identifiers:
  - `system_id`: deterministic key from canonical system key/repo slug.
  - `entity_id`: deterministic key from `(entity_type, normalized_name, scope)`.
  - Relationship IDs: deterministic key from
    `(source_entity_id, relation_type, target_entity_id)`.
- Core field schema (system level): `name`, `description`, `owner`, `domain`,
  `lifecycle`, `tier`, `data_class`, `compliance_flags`, `experts`,
  `external_dependencies`.
- Relationship taxonomy: `uses`, `depends_on`, `publishes_events_to`,
  `consumes_from`, `integrates_with`, `owned_by`.
- Provenance fields per generated field:
  - `source_type`, `source_path`, `source_hash`, `artifact_version`,
    `extraction_rule`, `confidence`, `last_seen`.
- Audit fields for overrides:
  - `field_updated_at`, `updated_by`, `override_reason`.

### 2) Two-Phase Pipeline: Extract/Enrich then Render

Decision:
- Separate processing into:
  - Phase A: harvest + enrich + normalize metadata
  - Phase B: generate C4 Level-1 context representation for a target system

Rationale:
- Decoupling enables targeted testing, reuse across systems, and easier tuning
  of enrichment heuristics without destabilizing rendering output.

Alternatives considered:
- Single-pass generation from raw inputs to final diagram payload.
  - Rejected due to poor debuggability and lower testability.

Pipeline contract:
- Phase A output: versioned canonical snapshot for a target system.
- Phase B output: C4 Level-1 context payload and business summary projection
  generated from a specific snapshot version.
- UI merges generated fields with persisted overrides at read time, producing
  an effective model deterministically.

### 3) WPS-first Quality Gate

Decision:
- Treat WPS as the baseline system with explicit acceptance checks for entity
  completeness, relationship correctness, and business-label readability before
  enabling broader rollout.

Rationale:
- A single reference system gives measurable quality criteria and avoids
  propagating weak extraction assumptions across the full portfolio.

Alternatives considered:
- Immediate multi-system rollout.
  - Rejected because it increases surface area before validation criteria are
    proven.

WPS acceptance criteria (must pass before broader rollout):
- Completeness:
  - At least 95% of WPS services have non-empty `owner`, `domain`, and
    `lifecycle` in effective values.
- Relationship correctness:
  - Golden fixtures for curated WPS relationships pass with no unexpected new
    edges in regression tests.
- Provenance coverage:
  - At least 98% of non-null generated fields include provenance metadata.
- Readability:
  - Display labels use human casing and do not default to raw repo slugs unless
    no better name exists.
- Determinism:
  - Re-running extraction on unchanged inputs produces byte-equivalent canonical
    snapshot output for WPS.

### 4) UI Review with Human-in-the-Loop Overrides

Decision:
- Add interactive UI review surfaces that show concise business summaries and
  allow SME edits/augmentations, persisted as explicit overrides on top of
  machine-generated values.

Rationale:
- Machine extraction alone is insufficient for business context quality;
  override-aware UX ensures expert knowledge is captured and retained.

Alternatives considered:
- Read-only UI with external/manual feedback channels.
  - Rejected due to slow iteration and poor traceability.

UI review model:
- Field state: `generated`, `overridden`, `missing`.
- Review status per system: `draft`, `reviewed`, `approved_for_publish`.
- Diff mode:
  - Show snapshot-to-snapshot extracted changes.
  - Highlight conflicts between new extraction and active overrides.

### 5) API Contract for Generated + Overridden Views

Decision:
- Expose API responses that include generated values, override values, and
  effective merged values per field.

Rationale:
- This supports transparent UI rendering and reduces ambiguity in reviews.

Alternatives considered:
- Returning only effective values.
  - Rejected because provenance and auditability would be lost.

Minimum role model (V1):
- `viewer`: read generated/effective context.
- `editor`: create/update overrides.
- `approver`: update review status to `approved_for_publish`.

### 6) Merge and Precedence Rules

Decision:
- Define explicit per-field source precedence with deterministic tie-breakers.

Rationale:
- Prevent accidental policy drift in implementation and make behavior testable.

Field precedence matrix (highest to lowest):
- `owner`: CODEOWNERS/service-universe owner -> repo metadata -> commit-history
  inference.
- `lifecycle`: service-universe lifecycle -> release/tag metadata ->
  heuristic inference.
- `domain`: service-universe domain -> curated team-domain mapping ->
  heuristic inference.
- `tier`: explicit architecture metadata -> service-universe tags ->
  heuristic inference.
- `data_class` and `compliance_flags`: explicit compliance artifacts/tags ->
  service-universe declarations -> heuristic inference (heuristic cannot
  auto-upgrade to high-criticality class without explicit source).

Tie-breakers:
- Prefer higher-ranked source.
- If same rank, choose higher `confidence`.
- If confidence delta <= 0.1, choose newest `last_seen`.
- If still tied, choose deterministic lexicographic source key and mark field as
  `contested`.

### 7) Override Lifecycle and Drift Handling

Decision:
- Overrides do not auto-expire; they can become stale when upstream evidence
  materially conflicts.

Rationale:
- Preserves expert trust while surfacing drift for revalidation.

Override lifecycle:
- `active`: override matches or safely supersedes generated evidence.
- `stale`: new extraction conflicts beyond configured threshold.
- `superseded`: override replaced by a newer override for the same field.

Drift detection:
- Mark override `stale` when generated value changes and either:
  - Source rank is higher than prior generated source rank, or
  - Confidence increase is >= 0.2 and value differs.
- Set `needs_review = true` for stale overrides and surface in UI diff.

### 8) Persistence and Versioning

Decision:
- Store extraction snapshots and overrides separately, compute effective context
  at read time.

Rationale:
- Simplifies auditability, replay, and deterministic merging.

Storage model:
- Canonical snapshots: versioned records per ingestion run (append-only),
  keyed by `(system_id, snapshot_id, extracted_at)`.
- Overrides: field-level records keyed by `(system_id, field_path)` with status,
  audit, and actor metadata.
- Effective view: generated + overrides merged by precedence and lifecycle rules
  during API reads.

## Risks / Trade-offs

- [Incomplete or inconsistent source metadata] -> Mitigation: introduce field
  confidence scoring, fallback heuristics, and explicit "unknown" states.
- [False-positive relationships in C4 generation] -> Mitigation: add
  relationship validation rules and WPS regression fixtures in e2e tests.
- [UI complexity from generated vs overridden states] -> Mitigation: use a
  simple three-state presentation (`generated`, `overridden`, `missing`) and
  clear field-level provenance.
- [Performance overhead from multi-source harvesting] -> Mitigation: cache
  parsed artifacts and support incremental refresh for changed repositories.
- [Scope drift into non-owned C4 modules] -> Mitigation: confine implementation
  to context-owned paths and only extend adjacent modules through explicit,
  minimal interfaces.

## Migration Plan

1. Implement canonical context model and extraction/enrichment pipeline in
   `sources/Api/app/services/c4/context/` with unit tests.
2. Add/extend API endpoints to return generated, overridden, and effective
   context fields for a target system (starting with WPS).
3. Implement UI business-summary and validation/augmentation flows in
   `sources/UI/src/`, including field-level provenance display.
4. Add e2e coverage under `sources/e2e/` validating ingestion -> C4 generation
   -> UI validation loop for WPS.
5. Run regression gate (`make quick-check`) and fix failures.
6. Roll out behind a feature toggle or system-scoped activation (WPS-only),
   then incrementally enable additional systems.

Rollback strategy:
- Disable feature toggle/system activation to return to current behavior.
- Preserve captured overrides and extraction snapshots for forensic analysis and
  reprocessing after fixes.

## Open Questions

- Exact confidence threshold for auto-blocking relationship edges in C4
  generation (proposed default: block when `confidence < 0.6`).
- Material-change threshold tuning for stale override detection in low-signal
  repositories.
- Whether `approver` role is required in V1 launch or can be deferred behind a
  feature flag.
