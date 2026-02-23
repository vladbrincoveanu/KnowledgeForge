# KnowledgeForge Feature Roadmap - Implementation Plan

## 1. Goal
Add business-facing metadata and visualization controls without regressing existing C4 extraction.

Target outcomes:
- Add: owner/steward accountability, sensitivity tags, quality score, usage metrics, column lineage.
- Remove/de-emphasize: raw ports, docker service IDs, low-level infra clutter.
- Add export paths: Structurizr DSL + Mermaid C4 snippet.

## 2. Current Baseline (repo reality)
- Context extraction pipeline exists in `sources/Api/app/services/c4/context/`.
- UI graph/viewer exists in `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/`.
- Dependency classification already distinguishes `BUSINESS_SYSTEM` vs `TECHNICAL_INFRA`.
- Existing fields already include `owner` and `data_class` but not explicit steward, quality score, usage stats, or column lineage entities.

## 3. Scope and Priorities (MoSCoW)
## Must-have
- Logical-name resolution (replace raw port/service IDs with logical names).
- Owner/Steward extraction.
- Sensitivity tagging model + UI surfacing.

## Should-have
- Data quality scoring.
- Usage analytics overlay.
- Column-level lineage.

## Could-have
- Structurizr DSL exporter.
- Mermaid C4 exporter/live preview.

## Won't-have (first increment)
- Deep HR/catalog hard dependency; ship pluggable connectors with fallback heuristics first.

## 4. Target Data Model Changes
Primary model update file:
- `sources/Api/app/domain/models/services.py`

Add fields/entities:
- `owner` (existing, normalize semantics to logical team/squad)
- `data_steward: Optional[str]`
- `sensitivity_tags: list[str]` (e.g., `PII`, `PCI`, `Confidential`)
- `quality_score: Optional[int]` (0-100)
- `usage_stats: dict[str, Any]` (window, calls, percentile_bucket, last_seen)
- `domain: Optional[str]` (already present, enforce taxonomy + grouping usage)
- `squad: Optional[str]`
- `column_lineage: list[dict[str, Any]]` (source, target, transform_hint, confidence)

Graph-level additions:
- Node labels/types: `Owner`, `SensitivityTag`, `QualityScore`, `UsageStats`.
- Relationship types: `OWNED_BY`, `STEWARDED_BY`, `HAS_SENSITIVITY`, `HAS_QUALITY`, `HAS_USAGE`, `COLUMN_FLOWS_TO`.

## 5. Architecture Workstreams
## WS1: Extraction Pipeline Extensions (API)
Files:
- `sources/Api/app/services/c4/context/metadata_detector.py`
- `sources/Api/app/services/c4/context/context_manager.py`
- `sources/Api/app/services/c4/context/dependency_detector.py`
- `sources/Api/app/services/service_extraction/service_enhancers.py`

Tasks:
1. Owner/Steward
- Keep current `owner` chain (CODEOWNERS -> README -> git -> LLM fallback).
- Add `data_steward` resolver:
  - Catalog lookup (if configured) -> CI/env hints -> README patterns (`data steward`, `governance`, `contact`) -> fallback `owner`.

2. Sensitivity tags
- Keep `data_class` for backward compatibility.
- Emit normalized `sensitivity_tags` list, mapped from existing `data_class` + additional policy/DLP tags.

3. Quality score
- Add parser(s) for Great Expectations/DBT outputs.
- Compute 0-100 score with recency weighting and test volume guardrails.

4. Usage stats
- Add ingestion adapter for API gateway/query logs.
- Compute rolling-window counts (7d/30d), percentile bucket, and trend delta.

5. Column lineage
- Add pluggable lineage extraction from SQL/ETL metadata, dbt manifest/run artifacts.
- Store per-column links with confidence and transformation hint.

## WS2: Logical Name Resolution + Infra Collapse
Files:
- `sources/Api/app/services/c4/context/dependency_detector.py`
- `sources/Api/app/services/code_extraction/component_extractor.py`
- `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`

Tasks:
1. Build canonical name resolver:
- Input: docker compose service, k8s annotations, labels, known aliases, ports.
- Output: one logical service name + aliases list.

2. De-emphasize infra noise:
- Collapse low-level infra nodes under virtual boundary node `Platform Services`.
- Keep details available in side panel metadata, not primary graph nodes.

3. Hide raw ports and docker IDs by default:
- Preserve in metadata/debug only.

## WS3: UI/UX Enhancements
Files:
- `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx`
- `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/FiltersSidebar.tsx`
- `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/NodeDetailsPanel.tsx`
- `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/EdgeDetailsPanel.tsx`

Tasks:
1. View mode toggle
- Add `Developer` vs `Executive` mode.
- `Executive`: hide infra-level nodes, collapse internals by domain/squad.
- `Developer`: show full technical graph.

2. Metadata side panel
- On hover/select, show: Owner/Steward, Sensitivity, Quality, Usage, Lineage coverage.
- Add icon mapping (shield/gauge/chart/link/person).

3. Auto-layout behavior
- External systems in outer ring.
- Internal services clustered by `domain` then `squad`.
- Platform boundary node anchored near internal clusters.

## WS4: Exporters
API files:
- `sources/Api/app/endpoint/v1/routes/code_extraction.py`
- New exporter module: `sources/Api/app/services/code_extraction/exporters/`

UI files:
- `sources/UI/src/services/api.ts`
- `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/components/ArchitectureHeader.tsx`

Tasks:
1. Structurizr DSL exporter
- Endpoint returns workspace DSL from internal C4 model.
- Include tags for sensitivity/domain/squad.

2. Mermaid exporter
- Endpoint returns C4Context/C4Container snippet.
- Optional preview component in UI.

## 6. API Contract Additions
Add to architecture payload:
- `system_context.data_steward`
- `system_context.sensitivity_tags`
- `system_context.quality_score`
- `system_context.usage_stats`
- `system_context.column_lineage_summary`
- optional `entities.owner[]`, `entities.sensitivity_tag[]`, `entities.quality_score[]`, `entities.usage_stats[]`

New endpoints:
- `GET /api/v1/code/architecture/export/structurizr`
- `GET /api/v1/code/architecture/export/mermaid`

## 7. Delivery Plan (phased)
## Phase 0 - Foundations (1 sprint)
- Finalize schemas and enums.
- Add feature flags and migration adapters.
- Define fallback behavior when external inputs (catalog/logs) absent.

## Phase 1 - Must-have extraction + graph cleanup (1-2 sprints)
- Logical-name resolution.
- Owner + data steward.
- Sensitivity tags.
- Platform Services collapse.
- Executive/Developer toggle.

## Phase 2 - Should-have enrichment (1-2 sprints)
- Quality score ingestion and scoring.
- Usage stats ingestion and overlay.
- Column-level lineage extraction + impact paths.

## Phase 3 - Export interoperability (1 sprint)
- Structurizr exporter endpoint.
- Mermaid exporter endpoint + UI copy/download.

## 8. Feature Flags
Add flags in API config:
- `KF_ENABLE_OWNER_STEWARD`
- `KF_ENABLE_SENSITIVITY_TAGS`
- `KF_ENABLE_QUALITY_SCORE`
- `KF_ENABLE_USAGE_STATS`
- `KF_ENABLE_COLUMN_LINEAGE`
- `KF_ENABLE_PLATFORM_COLLAPSE`
- `KF_ENABLE_STRUCTURIZR_EXPORT`
- `KF_ENABLE_MERMAID_EXPORT`

Rollout policy:
- Default off for new ingestion-dependent features.
- Default on for logical-name resolution and infra de-emphasis once validated.

## 9. Acceptance Criteria
1. Logical naming
- No primary graph node displayed as `:port` or raw docker service ID unless debug mode.

2. Accountability
- >= 90% of services show `owner`; >= 70% show `data_steward` when catalog configured.

3. Sensitivity
- All services emit `sensitivity_tags` (possibly empty), with deterministic mapping from `data_class`.

4. Quality and usage
- Quality score and usage stats visible in side panel and available via API payload.

5. Lineage
- Column lineage traversable for supported SQL/ETL artifacts; impact path visible from selected column.

6. UX
- Toggle between Executive and Developer mode updates graph density and infra visibility.

7. Export
- Structurizr DSL and Mermaid snippets generated from same internal model and pass basic syntax validation.

## 10. Risks and Mitigations
- Missing external data sources (HR/catalog/logs): provide connector abstraction + fallback heuristics.
- Model drift and payload bloat: version API payload and keep legacy aliases during migration.
- Graph overload from lineage: gate with lazy-load and depth limits.
- UI performance: apply virtualization/collapse by default in executive mode.

## 11. Recommended Implementation Order
1. Data model + feature flags.
2. Logical-name resolution + platform collapse.
3. Owner/steward + sensitivity tags.
4. UI toggle + side-panel metadata.
5. Quality + usage ingest.
6. Column lineage.
7. Structurizr + Mermaid exporters.
