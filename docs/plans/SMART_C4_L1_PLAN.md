# Phase 1 Plan: Smart C4 L1 Alignment for KnowledgeForge

## Summary
Implement a Phase 1, additive-only upgrade of C4 Level 1 extraction to match the PDF: canonical property model, field-level confidence, confidence-based human review, and Git-backed `facts.yml` persistence.
This plan keeps existing API/UI behavior compatible while adding new fields and review mechanics.

## Public API and Interface Changes
1. Extend `system_context` in `GET /api/v1/code/scan/{task_id}/results` and `GET /api/v1/code/architecture` with:
   - `canonical_properties: Record<string, CanonicalField>`
   - `human_review: { threshold: number, needs_confirmation_fields: string[], missing_mandatory_fields: string[] }`
   - `lifecycle_status: "Active" | "Deprecated" | "Planned"`
   - `critical_business_processes: string[]`
   - `compliance_tags: string[]`
   - `hosting_footprint: { cluster?: string, region?: string, platform?: string }`
   - `contributor_spread: number | null`
   - `risk_indicator: "Red" | "Yellow" | "Green"`
   - `last_updated: string | null`
2. Add optional fields to `POST /api/v1/code/scan/{task_id}/context-feedback` request model:
   - `critical_business_processes?: string[]`
   - `compliance_tags?: string[]`
   - `field_confirmations?: string[]`
3. Keep all existing fields (`owner`, `owner_team`, `status`, `tier`, `external_dependencies`, etc.) unchanged.
4. Update `sources/Api/http/code_architecture.http` with new feedback payload examples and retrieval validation.
5. Validate `.http` file using:
   - `docker run --rm -i -t -v $PWD:/workdir jetbrains/intellij-http-client sources/Api/http/code_architecture.http`

`CanonicalField` shape:
```ts
type CanonicalField = {
  value: unknown;
  confidence: number; // 0..1
  source: string; // e.g. "service-universe.yaml", "git", "readme", "heuristic", "human"
  mandatory: boolean;
  requires_confirmation: boolean; // confidence < 0.70 or mandatory missing
  confirmed_by_human: boolean;
  confirmed_at?: string; // ISO timestamp
};
```

## Implementation Design

### 1) New backend modules
1. Add `sources/Api/app/services/c4/context/canonical_schema.py` with:
   - Canonical field constants.
   - Mandatory fields list.
   - Confidence thresholds (`review_threshold=0.70`, `confirmed_floor=0.95`).
   - Mapping between canonical fields and legacy context fields.
2. Add `sources/Api/app/services/c4/context/service_universe_detector.py`:
   - Optional parse of `service-universe.yaml` / `.yml`.
   - Extract: name, description, owner, lifecycle, actors, dependencies, tags.
   - Return normalized canonical values + source/confidence metadata.
3. Add `sources/Api/app/services/c4/context/facts_store.py`:
   - Repo key generation from `repository_url` or normalized local path.
   - Load/save `sources/data/c4_facts/<repo_key>/facts.yml`.
   - Merge confirmed values into canonical fields with confidence floor `0.95`.

### 2) Context extraction orchestration
1. Refactor `sources/Api/app/services/c4/context/context_manager.py` to produce canonical properties first, then legacy aliases.
2. Merge priority:
   - `facts.yml` human overrides > `service-universe.yaml` > deterministic detectors > fallback heuristics.
3. Populate `human_review` with field-level gating:
   - `requires_confirmation = true` when confidence `< 0.70` or mandatory field missing.
4. Keep existing relationship generation but improve labels:
   - Actor edges: use actor description/action when available, default `Uses`.
   - External edges: derive readable verb from dependency/protocol, default `Calls API of`.
5. Add "max 8 external systems" collapse behavior (remaining grouped into `Other Systems`).

### 3) Confidence and derived metrics
1. Implement deterministic confidence assignment per canonical field:
   - YAML exact values: `0.9-1.0`.
   - Structured parse (git/manifests): `0.7-0.9`.
   - README heuristics: `0.6`.
   - Manual gap defaults (critical processes): `0.3`.
   - Human-confirmed values: min `0.95`.
2. Add `contributor_spread` in `sources/Api/app/services/c4/context/metadata_detector.py`:
   - `top3_commit_share = top3_commits / total_commits`.
3. Add `risk_indicator` formula:
   - `docs_signal`: 1.0 if README/doc checks pass, else 0.0.
   - `tests_signal`: 1.0 if test presence checks pass, else 0.0.
   - `spread_risk = top3_commit_share`.
   - `risk_score = 0.40*(1-docs_signal) + 0.35*(1-tests_signal) + 0.25*spread_risk`.
   - `Red >= 0.66`, `Yellow >= 0.33`, else `Green`.

### 4) Feedback persistence path
1. In `sources/Api/app/endpoint/v1/routes/code_extraction.py`, update `apply_context_feedback` to:
   - Save to existing task JSON.
   - Save merged feedback to per-repo `facts.yml`.
   - Mark confirmed fields in `canonical_properties` (`confirmed_by_human=true`, `confirmed_at` set).
2. In extraction flow (`run_c4_extraction`), load `facts.yml` and merge before final context assembly.

### 5) UI changes
1. Update `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`:
   - Replace heuristic-only review trigger with backend `human_review` first, heuristic fallback second.
   - Include new feedback fields in payload assembly.
2. Update `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/ContextReviewDialog.tsx`:
   - Add editable sections for `critical_business_processes` and `compliance_tags`.
   - Display confidence and `Needs confirmation` markers.
3. Update `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/NodeDetailsPanel.tsx`:
   - Show canonical field confidence/source and risk indicator badge.
4. Update `sources/UI/src/services/api.ts` payload typing for extended feedback contract.

### 6) Feature flags and rollout
1. Extend `sources/Api/app/services/c4/context/feature_flags.py` with:
   - `enable_service_universe_yaml`
   - `enable_facts_persistence`
   - `enable_confidence_review`
2. Default flags ON for Phase 1; keep legacy behavior fallback when flag disabled.

## Test Cases and Scenarios

### Backend
1. `service_universe_detector` parses valid YAML and maps canonical fields.
2. Missing YAML falls back to current detectors without failure.
3. `facts_store` round-trip save/load and merge precedence.
4. Confidence gating marks expected fields below threshold.
5. Context feedback persists to `facts.yml` and applies on next extraction.
6. Relationship label derivation and `Other Systems` collapse with >8 externals.
7. API route tests for extended feedback payload and response fields in `sources/Api/tests/unit/endpoint/v1/routes/test_code_extraction.py`.

### UI
1. Viewer opens review dialog when `human_review.needs_confirmation_fields` is non-empty.
2. Dialog submits new fields (`critical_business_processes`, `compliance_tags`) in payload.
3. Node details render confidence/source badges and risk indicator.
4. Existing smoke tests remain green in `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.test.tsx`.

### Validation commands
1. `cd sources/Api && pytest tests/unit/services/c4 tests/unit/endpoint/v1/routes/test_code_extraction.py -v`
2. `cd sources/UI && npm run test -- CodeArchitectureViewer`
3. `make quick-check`
4. IntelliJ HTTP client run against `sources/Api/http/code_architecture.http`

## Assumptions and Defaults
1. Delivery scope is Phase 1 only.
2. `service-universe.yaml` is optional; extraction must still work without it.
3. `facts.yml` is stored per repo at `sources/data/c4_facts/<repo_key>/facts.yml`.
4. Changes are additive-only; no breaking contract removals.
5. Confidence thresholds are fixed at `0.70` (review) and `0.95` (post-human confirmation floor).
6. Batch/org extraction keeps current behavior; full multi-repo facts semantics are deferred.
