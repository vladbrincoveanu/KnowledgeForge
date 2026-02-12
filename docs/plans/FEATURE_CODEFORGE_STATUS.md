# feature/CODEFORGE — Final Status

**Branch:** `feature/CODEFORGE`
**Date:** February 12, 2026
**Test Suite:** Backend 251/251 ✅ | Frontend 84/84 ✅

---

## Summary

Complete delivery of the KnowledgeForge context-level extraction engine. This branch covers three months of work: foundational refactoring (Waves 1–4), context-level feature additions (Waves 5–6), and gap-task cleanup.

**Scope:** We own the **Context Level** only. Container-level (`c4/containers/`) files are untouched and owned by a separate squad.

---

## What Was Shipped

### Backend — New Modules

| File | What It Does |
|------|-------------|
| `app/domain/exceptions.py` | Typed exception hierarchy replacing bare `except Exception` |
| `app/domain/constants/technologies.py` | Centralised tech vocabulary (frameworks, languages, signals) |
| `app/endpoint/v1/dependencies.py` | FastAPI DI: `get_neo4j_manager`, `get_llm_manager`, etc. |
| `app/utils/security.py` | `validate_github_url`, `validate_local_repo_path`, `safe_extract_zip` |
| `app/utils/request_id_middleware.py` | Request-ID header injection for correlation |
| `app/services/code_extraction/language_detectors.py` | Per-language detector classes (split from 2835-line `c4_extractor.py`) |
| `app/services/code_extraction/component_extractor.py` | Component-level extraction (split from `c4_extractor.py`) |
| `app/services/code_extraction/llm_enrichment.py` | LLM enrichment logic (split from `c4_extractor.py`) |
| `app/services/service_extraction/extraction_helpers.py` | Shared field helpers: `extract_field_value`, `extract_status`, `extract_tier` |
| `app/services/service_extraction/service_enhancers.py` | `enhance_with_*` chain: 7 specialist enhancer functions |
| `app/services/service_extraction/api_surface_detector.py` | Detects REST/GraphQL/gRPC/CLI/WebSocket from code patterns |
| `app/services/service_extraction/deployment_target_detector.py` | Detects Container/K8s/Serverless/VM from Dockerfile, Helm, Terraform |
| `app/services/service_extraction/documentation_quality_scorer.py` | 0-100 composite: README depth, OpenAPI spec, ADRs, inline docs |
| `app/services/service_extraction/inter_service_comm_detector.py` | HTTP client + queue pattern scanner for runtime dependencies |
| `app/services/service_extraction/business_domain_classifier.py` | LLM classification into fixed taxonomy (Payments, Identity, etc.) |
| `app/services/service_extraction/compliance_scorer.py` | Weighted 7-check rubric (0-100 + COMPLIANT/AT_RISK/NON_COMPLIANT) |
| `app/services/service_extraction/bus_factor_calculator.py` | Gini-coefficient composite: expert count × (1-gini). Scale 1-10. |
| `app/services/service_extraction/auth_scanner.py` | OAuth2/JWT/APIKey/mTLS from OpenAPI schemes, source patterns, env vars |
| `app/services/service_extraction/owner_detector.py` | 4-step fallback: CODEOWNERS → git blame → CI config → UNKNOWN |

### Backend — Key Modifications

| File | Key Changes |
|------|-------------|
| `app/domain/models/services.py` | Added `APISurfaceType`, `DeploymentTarget`, `CommDirection`, `BusinessDomain` enums. Added `ARCHIVED` to `ServiceStatus`. Renamed `ACTIVE_DEV→ACTIVE`, `MAINTENANCE_ONLY→MAINTENANCE` (values `"ACTIVE"`, `"MAINTENANCE"`). New fields: `api_surface_types`, `inter_service_comms`, `documentation_quality`, `deployment_targets`, `business_domain`, `bus_factor`, `compliance_score`, `owner_detection_source`. |
| `app/services/service_extraction/service_extraction_pipeline.py` | Added Phase 5 parallel LLM enrichment. Added Phase 8: all 7 `enhance_with_*` specialist functions. |
| `app/services/service_extraction/service_extractor.py` | Refactored from 1529-line monolith → 197-line orchestrator using extracted helpers. |
| `app/services/code_extraction/c4_extractor.py` | Refactored from 2835-line monolith → 342-line orchestrator importing split modules. |
| `app/services/c4/context/context_manager.py` | Added 9 new detection calls: environment, app_version, tags, api_spec_url, documentation_url, monitoring_url, regulatory_frameworks, dora_metrics, on_call_channel. Removed YAGNI container fallback block and integration_endpoints block. |
| `app/services/c4/context/metadata_detector.py` | Updated ServiceStatus string values. Added `detect_on_call_channel()`. |
| `app/services/c4/context/system_detector.py` | Added: `detect_environments()`, `detect_app_version()`, `detect_tags()`, `detect_api_spec_url()`, `detect_documentation_url()`, `detect_monitoring_url()`, `detect_regulatory_frameworks()`. |
| `app/services/c4/context/dependency_detector.py` | Added `detect_dependency_freshness_alerts()`. |
| `app/infrastructure/graph/neo4j_manager.py` | Simplified index-drop error handling. Removed debug `get_config()` call from except clause. |
| `app/infrastructure/storage/embedding_manager.py` | Restored `info` logs to `debug` (cache hit, generation). |
| `app/infrastructure/llm/llm_manager.py` | Restored rate-limit log to `debug`. |
| `app/endpoint/v1/routes/service_extraction.py` | OpenAPI enrichment: `summary`, `description`, `responses`, `status_code=202`. |
| `app/endpoint/v1/routes/code_extraction.py` | OpenAPI enrichment + DI wiring. |

### Frontend

| File | Key Changes |
|------|-------------|
| `CodeArchitectureViewer.tsx` | Decomposed: 2419 → 1737 lines. Extracted 5 sub-components. |
| `CodeArchitectureViewer/components/` | New: `ArchitectureHeader.tsx`, `GraphView.tsx`, `NodeDetailsPanel.tsx`, `EdgeDetailsPanel.tsx`, `FiltersSidebar.tsx` |
| `ArchitectureMap.tsx` | Removed 29 hardcoded `fetch()` calls to `127.0.0.1:7243` (debug telemetry). |
| `api.ts` | Removed 28 `console.log` debug statements. |
| `Graph.tsx` | Fixed O(n×m) link-filtering → O(n+m) Set lookup. |

### Tests

| File | Coverage |
|------|---------|
| `tests/e2e/test_e2e_extraction.py` | 29 E2E tests: FastAPI/Express/Monorepo/.NET fixtures, field completeness, enum validity |
| `tests/unit/services/test_context_fields.py` | 66 tests: all 8 specialist detectors + enhancer wiring |
| `tests/unit/services/test_dotnet_extraction.py` | .NET/C# extraction: 15 tests |
| `tests/unit/services/test_parallel_enrichment.py` | Parallel LLM enrichment: 8 tests |
| `tests/unit/endpoint/v1/routes/test_service_extraction.py` | Route layer: 12 tests |
| `tests/unit/endpoint/v1/routes/test_code_extraction.py` | Route layer: 12 tests |
| `sources/UI/src/**/**.test.tsx` | Frontend: 84 tests across 10 files |

---

## What Was Deliberately NOT Done

| Item | Why |
|------|-----|
| `c4/containers/` changes | Container squad scope — reverted to HEAD. |
| Typed `Container` Pydantic model | Container squad scope (ITIL Phase 1.1). |
| `sla_target` field | Explicitly deferred in `docs/architecture/field-mapping.md` — container level. |
| `replica_count`, `resource_limits`, `region` | Container/infra level fields. |
| Tasks #21 (DI refactor), #26 (config mgmt), #27 (structured logging) | Not in scope for this sprint. |

---

## Open Refactoring Tasks (3 remaining)

| Task | Description | Effort |
|------|-------------|--------|
| **#21** | FastAPI dependency injection — remove globals, use `Depends()` throughout | 2-3 days |
| **#26** | Centralised config management (replace scattered `config.yaml` reads) | 2 days |
| **#27** | Structured logging with correlation IDs (request_id propagation) | 2 days |

---

## Field Coverage — Context Level

| # | Field | Status | Detection Method |
|---|-------|--------|-----------------|
| 1 | System Name | ✅ | Dir name → README title → package.json |
| 2 | External Dependencies | ✅ | Package managers + import scanning |
| 3 | Dep. Classification | ✅ | LLM: BUSINESS vs TECHNICAL |
| 4 | Criticality Tier | ✅ | SLA markers + README keywords |
| 5 | Data Classification | ✅ | PII/PCI regex patterns |
| 6 | System Purpose | ✅ | LLM: README + route handlers + entrypoints |
| 7 | Owner / Team | ✅ | 4-step: CODEOWNERS → git blame → CI → UNKNOWN |
| 8 | Languages | ✅ | Extension counting + shebang lines |
| 9 | Frameworks + Versions | ✅ | requirements.txt, package.json, go.mod, Cargo.toml |
| 10 | Actors | ✅ | README + OAuth scopes + OpenAPI securitySchemes |
| 11 | Business Domain | ✅ | LLM → fixed taxonomy (10 values) |
| 12 | Service Status | ✅ | Git activity windows: ACTIVE/MAINTENANCE/DEPRECATED/ARCHIVED |
| 13 | Compliance Score | ✅ | Weighted 7-check rubric (0-100 + tier) |
| 14 | Bus Factor | ✅ | Gini coefficient composite (1-10 scale) |
| 15 | API Surface Type | ✅ | Route decorators, .proto files, GraphQL schemas |
| 16 | Inter-Service Comms | ✅ | HTTP client + queue producer/consumer patterns |
| 17 | Documentation Quality | ✅ | 0-100: README depth + OpenAPI + ADRs + inline docs |
| 18 | Deployment Target | ✅ | Dockerfile, Helm, Terraform, serverless.yml |
| + | Environment | ✅ | Helm values files, namespace labels, env names |
| + | App Version | ✅ | Chart.yaml appVersion, package.json version |
| + | Tags | ✅ | K8s labels, Helm labels |
| + | API Spec URL | ✅ | README links, route definitions |
| + | Documentation URL | ✅ | README wiki/Confluence/Notion links |
| + | Monitoring URL | ✅ | Grafana annotations, README links |
| + | Regulatory Frameworks | ✅ | COMPLIANCE.md, README badges (SOC2, GDPR, HIPAA) |
| + | DORA Metrics | ✅ | Git commit history proxy |
| + | Dependency Freshness Alerts | ✅ | Unpinned/range version detection |
| + | on_call_channel | ✅ | CI env vars (SLACK_CHANNEL, PAGERDUTY_SERVICE_KEY) + README |

**All 14 context_improvements.md tasks: 14/14 complete.**

---

## Key Engineering Decisions

1. **Two pipeline classes exist** — `ServiceExtractor` and `ServiceExtractionPipeline`. Both must wire Phase 8. Adding enhancers to only one causes silent data loss for callers of the other.

2. **Python 3.11 enum membership** — `"REST" in APISurfaceType` raises `TypeError`. Always use `{e.value for e in SomeEnum}` for string membership checks.

3. **Log levels** — Failed/fallback paths in detectors stay at `debug`. Promoting them to `info` creates noise in production logs.

4. **YAGNI on integrations** — Do not add `integration_endpoints` blocks or container ITIL field fallbacks until those systems actually exist. They create dead code paths and confuse future developers.
