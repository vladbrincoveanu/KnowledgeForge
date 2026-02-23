## Context

KnowledgeForge currently provides C4 L1 extraction via `ContextManager` with detector-based heuristics and human feedback patching per task. It lacks a canonical field model that tracks source/confidence per field, lacks persisted per-repo confirmations, and triggers review primarily from UI heuristics rather than explicit backend review metadata.

The target implementation is a Phase 1 additive slice:
- Keep all existing API fields and behavior intact for compatibility.
- Add canonical field metadata and confidence-driven review state.
- Persist human confirmations to `sources/data/c4_facts/<repo_key>/facts.yml`.
- Reapply confirmations deterministically in future extractions.

Constraints:
- `service-universe.yaml` may be absent and must remain optional.
- Existing scan/task workflows must continue to function.
- Batch/org extraction keeps current behavior; complete facts semantics are single-repo-first.

## Goals / Non-Goals

**Goals:**
- Introduce canonical C4 L1 field objects with deterministic confidence and source provenance.
- Add backend-owned review state (`human_review`) and expose it in existing context endpoints.
- Persist human-reviewed context fields in per-repo `facts.yml` and merge into later runs.
- Expand context feedback payload to include business process/compliance confirmations.
- Surface confidence/review signals in context review and node details UI.
- Validate artifacts with OpenSpec strict validation.

**Non-Goals:**
- No breaking replacement of legacy field names.
- No Phase 2/3 features (telemetry ingestion, real-time pipelines, lineage platform rollout).
- No full multi-repo facts reconciliation for batch extraction in this slice.

## Decisions

1. Additive contract strategy
- Decision: Add new keys (`canonical_properties`, `human_review`, `lifecycle_status`, etc.) while retaining legacy aliases and existing field names.
- Rationale: Prevent frontend/API regressions while enabling incremental adoption.
- Alternative considered: canonical-only breaking schema; rejected due migration cost and immediate UI break risk.

2. Canonical field wrapper model
- Decision: Represent each canonical field as `{value, confidence, source, mandatory, requires_confirmation, confirmed_by_human, confirmed_at}`.
- Rationale: Enables deterministic gating and traceability.
- Alternative considered: separate confidence map; rejected because it fragments provenance and complicates API/UI joins.

3. Facts persistence boundary
- Decision: Store per-repo facts under `sources/data/c4_facts/<repo_key>/facts.yml` and merge before final context response composition.
- Rationale: Repo-scoped continuity across scans without coupling to ephemeral `task_id`.
- Alternative considered: per-task facts files; rejected because it does not provide reuse across runs.

4. Optional service-universe source
- Decision: Parse `service-universe.yaml` only when present and treat as authoritative/high-confidence for overlapping canonical fields.
- Rationale: Supports planned source without hard dependency.
- Alternative considered: required YAML; rejected because current repos do not contain it.

5. Backend-owned review trigger
- Decision: Generate `human_review.needs_confirmation_fields` in backend and let UI consume it first, with heuristic fallback for legacy payloads.
- Rationale: Centralizes gating logic and keeps UI deterministic.
- Alternative considered: UI-only review heuristics; rejected for inconsistency and duplication.

6. Risk indicator derivation
- Decision: Compute `risk_indicator` from docs signal, tests signal, and contributor spread using fixed weighted formula.
- Rationale: Matches plan requirements with deterministic explainability.
- Alternative considered: model-based risk scoring; rejected for Phase 1 complexity.

## Risks / Trade-offs

- [Risk] Canonical and legacy fields diverge over time.
  - Mitigation: Define one canonical-to-legacy mapping table in `canonical_schema.py` and cover with mapping tests.
- [Risk] Repo key collisions for facts files.
  - Mitigation: Use deterministic normalized keys from repository URL when available, else normalized absolute path hash.
- [Risk] UI review behavior changes unexpectedly.
  - Mitigation: Preserve existing heuristic path as fallback and add explicit tests for new backend-driven trigger path.
- [Risk] Confidence heuristics can be over/under-sensitive.
  - Mitigation: Encode thresholds as constants and add tests around boundary values (0.69/0.70/0.95).
- [Risk] Batch extraction still lacks full facts semantics.
  - Mitigation: Keep scope explicit (single-repo-first) and avoid partial multi-repo persistence logic.
