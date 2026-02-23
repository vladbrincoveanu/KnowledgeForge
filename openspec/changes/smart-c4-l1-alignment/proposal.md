## Why

KnowledgeForge already extracts C4 Level 1 context data, but the output is not yet aligned with the Smart C4 L1 model required for high-confidence business review. We need deterministic canonical fields, confidence gating, and persisted human confirmations now so extraction quality is stable and auditable across runs.

## What Changes

- Add a canonical C4 L1 property schema with per-field value, source, confidence, and confirmation state.
- Add optional `service-universe.yaml` ingestion as a high-confidence source with fallback to existing detectors.
- Add persisted human confirmations in per-repo `facts.yml` and merge confirmations into subsequent runs.
- Extend context API payloads with `canonical_properties`, `human_review`, and derived metadata fields while preserving current fields.
- Extend context feedback endpoint to accept business process/compliance confirmations and field confirmation hints.
- Add deterministic confidence thresholds and review triggers (`< 0.70` or mandatory missing).
- Update UI context review and node detail surfaces to display confidence, review-needed markers, and additional confirmed fields.

## Capabilities

### New Capabilities

- `c4-context-canonical-properties`: Canonical C4 L1 fields with confidence/source metadata and additive API exposure.
- `c4-context-human-review-facts`: Persist and reapply human confirmations via per-repo `facts.yml`.
- `c4-context-review-ui`: UI-driven context review that surfaces confidence and submits expanded review payloads.

### Modified Capabilities

- None.

## Impact

- Backend:
  - `sources/Api/app/services/c4/context/context_manager.py`
  - `sources/Api/app/services/c4/context/metadata_detector.py`
  - `sources/Api/app/services/c4/context/feature_flags.py`
  - `sources/Api/app/endpoint/v1/routes/code_extraction.py`
  - New modules for canonical schema, service-universe parsing, and facts persistence.
- Frontend:
  - `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`
  - `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/ContextReviewDialog.tsx`
  - `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/NodeDetailsPanel.tsx`
  - `sources/UI/src/services/api.ts`
- Documentation and contract updates:
  - `sources/Api/http/code_architecture.http`
  - `docs/plans/SMART_C4_L1_PLAN.md`
