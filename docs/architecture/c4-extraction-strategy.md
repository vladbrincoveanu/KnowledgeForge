# KnowledgeForge — C4 Extraction Strategy

**Version:** 1.0
**Last Updated:** February 2026
**Audience:** Backend contributors, integration engineers, new joiners

---

## Overview

KnowledgeForge automatically builds a **C4 architecture model** from source code repositories.
It produces four levels of detail — Context, Container, Component, Code — plus a **Service Catalog** layer with 18 enriched metadata fields.

```
GitHub / ZIP / Local path
        │
        ▼
┌───────────────────┐
│  Download / Mount │  GitHubDownloader or safe_extract_zip
└────────┬──────────┘
         │
         ▼
┌───────────────────────────────────────────────────────┐
│               Service Extraction Pipeline              │
│  Phase 1: Service Discovery  (ServiceDiscoverer)      │
│  Phase 2: Language/Framework (LanguageDetectors)       │
│  Phase 3: Git Analysis       (GitFullAnalyzer)         │
│  Phase 4: Domain Extraction  (DomainExtractor)        │
│  Phase 5: Dependency Graph   (DependencyExtractor)     │
│  Phase 6: Context Nodes      (ContextNodeExtractor)    │
│  Phase 7: Compliance         (ComplianceScorer)        │
│  Phase 8: Enhancements       (service_enhancers.py)    │
│  Phase 9: LLM Enrichment     (LLMServiceEnricher)      │
└──────────────────────┬────────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────┐
│               C4 Architecture Extraction               │
│  Level 1: Context  (system_detector.py)               │
│  Level 2: Container (compose/helm/terraform detectors) │
│  Level 3: Component (component_extractor.py)           │
│  Level 4: Code      (llm_enrichment.py + AST)          │
└──────────────────────┬────────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────┐
│               Storage                                  │
│  JSON files  →  data/extractions/{task_id}/           │
│  Neo4j graph →  (feature-flagged)                     │
└───────────────────────────────────────────────────────┘
```

---

## Layer 1: Service Extraction Pipeline

**Entry point:** `app/services/service_extraction/service_extraction_pipeline.py`
**Triggered by:** `POST /api/v1/services/extract-from-github` (or -zip / -path)

### Phase-by-Phase Breakdown

| Phase | Class / Module | What It Does |
|-------|---------------|--------------|
| 1 | `ServiceDiscoverer` | Finds candidate service roots by scanning for `docker-compose.yml`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `.csproj`, `.sln` manifests |
| 2 | `LanguageDetectors` (`DotNetLanguageDetector`, heuristics) | Counts file extensions, reads `.csproj` TFM, maps to language + framework |
| 3 | `GitFullAnalyzer` → `GitStatusAnalyzer`, `GitContributorAnalyzer` | Extracts last commit date, 30/90/180d commit counts, contributor list |
| 4 | `DomainExtractor` | LLM classification of the service's business domain from README + file structure |
| 5 | `DependencyExtractor` | Reads `requirements.txt`, `package.json`, `go.mod`, `Cargo.toml`, `pom.xml`, NuGet packages; classifies each dep as BUSINESS or TECHNICAL |
| 6 | `ContextNodeExtractor` | Pulls README, OpenAPI specs, Dockerfiles, CI configs, `appsettings.json` as rich context nodes |
| 7 | `ComplianceScorer` | Runs 7-check weighted rubric; outputs 0-100 score + EXCELLENT/COMPLIANT/AT_RISK/NON_COMPLIANT tier |
| 8 | Enhancement chain (see below) | Runs 8 specialist detectors in order |
| 9 | `LLMServiceEnricher` | Batches remaining services to LLM for purpose/description enrichment; runs in parallel via `ThreadPoolExecutor` |

### Phase 8 — Enhancement Chain

All enhancements live in `app/services/service_extraction/service_enhancers.py` and are wired in `service_extractor.py:_run_enhancements()`.

| Order | Function | Detector Module | Output Fields |
|-------|----------|----------------|---------------|
| 1 | `enhance_with_git_status()` | `git_status_analyzer.py` + `owner_detector.py` | `status`, `status_evidence`, `owner`, `owner_detection_source` |
| 2 | `enhance_with_api_surface_types()` | `api_surface_detector.py` | `api_surface_types` (REST/GraphQL/gRPC/CLI/WebSocket/Event-Driven) |
| 3 | `enhance_with_deployment_targets()` | `deployment_target_detector.py` | `deployment_targets` (Container/K8s/Serverless/VM/Bare-Metal/PaaS) |
| 4 | `enhance_with_documentation_quality()` | `documentation_quality_scorer.py` | `documentation_quality` (0-100 score + tier) |
| 5 | `enhance_with_inter_service_comms()` | `inter_service_comm_detector.py` | `inter_service_comms` (list of {target, protocol, direction}) |
| 6 | `enhance_with_business_domain()` | `business_domain_classifier.py` | `business_domain` (Payments/Identity/Logistics/…) |
| 7 | `enhance_with_bus_factor()` | `bus_factor_calculator.py` | `bus_factor` (1-10 Gini-based score) |
| 8 | `enhance_with_auth_scanning()` | `auth_scanner.py` | `actors` list updated with auth types (OAuth/JWT/APIKey/mTLS/BasicAuth) |

**To add a new enhancer:**
1. Create `app/services/service_extraction/my_detector.py`
2. Add `enhance_with_my_field(services, repo_root)` to `service_enhancers.py`
3. Call it inside `_run_enhancements()` in `service_extractor.py`

---

## Layer 2: C4 Architecture Extraction

**Entry point:** `app/services/code_extraction/c4_extractor.py` (342-line orchestrator)
**Triggered by:** `POST /api/v1/code/extract-from-github` (or upload-repo)

### C4 Level 1 — Context

**Module:** `app/services/c4/context/system_detector.py`
**Data sources:** repo root name, README title, `package.json` name field, `.sln` stem
**Output:** `system_context` object with name, purpose, languages, frameworks, external dependencies

### C4 Level 2 — Containers

**Modules:** `app/services/c4/containers/`

| Detector | Files It Reads | Container Types |
|----------|---------------|----------------|
| `compose_detector.py` | `docker-compose.yml`, `docker-compose.*.yml` | web-app, api, database, message-queue, cache, worker |
| `helm_detector.py` | `Chart.yaml`, `values.yaml` | kubernetes deployments |
| `terraform_detector.py` | `*.tf` files | cloud infrastructure resources |
| `structure_detector.py` | directory structure + `Dockerfile` | inferred containers |

### C4 Level 3 — Components

**Module:** `app/services/code_extraction/component_extractor.py`
**Algorithm:** Scan directories → group by module pattern → detect routes via decorators (`@app.route`, `@router.get`, etc.)

### C4 Level 4 — Code

**Module:** `app/services/code_extraction/llm_enrichment.py`
**Algorithm:** Extract key files (routes, handlers, main entrypoints) → feed to LLM → generate per-node descriptions
**LLM prompt focus:** business purpose from code, not README boilerplate

---

## Data Flow: Full Request Lifecycle

```
1. Client → POST /api/v1/services/extract-from-github
   Body: { github_url: "https://github.com/org/repo" }

2. Route handler (service_extraction.py)
   → validates URL via validate_github_url()
   → creates task_id (format: YYYYMMDD-HHMM-xxxxxx)
   → returns 202 { task_id, status: "pending" }
   → enqueues BackgroundTask(run_service_extraction)

3. Background thread (run_service_extraction)
   → broadcasts WebSocket: status=extracting, progress=10%
   → GitHubDownloader.download_repository() → /tmp/service_extract_{task_id}/
   → broadcasts progress=30%
   → ServiceExtractionPipeline(repo_path).extract_services()
      → 9-phase pipeline (see above)
      → returns (services[], context_nodes[])
   → broadcasts progress=60%
   → ServiceRelationshipDiscoverer.discover_connections()
   → broadcasts progress=80%
   → ServiceGraph.build()
   → JSONResultStore.save() → data/extractions/{task_id}/*.json
   → (optional) Neo4jGraphManager.store_batch()
   → broadcasts status=completed, progress=100%

4. Client polls GET /api/v1/services/extraction/{task_id}
   → returns { status, progress, services_count, connections_count, errors }

5. Client fetches GET /api/v1/services/extraction/{task_id}/results
   → returns full service graph JSON
```

---

## Configuration Reference

Key extraction toggles in `sources/Api/config.yaml`:

| Setting | Default | Effect |
|---------|---------|--------|
| `extraction.store_to_json` | `true` | Write JSON output files |
| `extraction.store_to_neo4j` | `false` | Write to Neo4j graph DB |
| `extraction.enable_llm_descriptions` | `false` | LLM enrichment per service |
| `extraction.git_clone_for_analysis` | `true` | Full clone (enables git blame) |
| `lmstudio.base_url` | `http://lmstudio:1234` | LM Studio endpoint |
| `lmstudio.model_name` | `llama-3.1` | Default model |

Environment variable overrides: `OPENAI_API_KEY`, `OPENAI_MODEL`, `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`, `KF_LLM_PROVIDER` (`lmstudio` | `openai`), `GITHUB_TOKEN`.

---

## Security Constraints

- **ZIP uploads** — `safe_extract_zip()` rejects path traversal (`../`), symlinks, and zip bombs (>500 MB uncompressed)
- **Local paths** — `validate_local_repo_path()` resolves symlinks, enforces `/tmp|/repos|/data` allowlist
- **GitHub URLs** — `validate_github_url()` enforces HTTPS, strict `github.com` domain, valid owner/repo names

---

## Adding a New Language

1. Create `MyLanguageDetector` in `app/services/code_extraction/language_detectors.py`
2. Implement `detect(path: Path) -> dict | None` — return `{"language": "...", "version": "...", "framework": "..."}` or `None`
3. Register it in `C4ArchitectureExtractor._get_language_detectors()`
4. Add framework patterns to `FRAMEWORK_INDICATORS` in `language_detectors.py`
5. Add dependency mappings to `NUGET_DEPENDENCY_MAP` (or equivalent) in `dependency_detector.py`
6. Verify with `docker compose exec -T api python -m pytest tests/ -q`
