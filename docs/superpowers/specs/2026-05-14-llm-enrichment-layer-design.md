# LLM Enrichment Layer — Design Spec
**Date:** 2026-05-14
**Scope:** C4 Context level (Container/Component follow same pattern in v2)
**Status:** Approved

---

## Problem

Current extraction pipeline is fully deterministic: hardcoded package maps, regex URL patterns, NUGET/npm/pip dependency lists. Fails on:
- Unknown package names (internal company wrappers)
- Novel ecosystems (Go, Rust, Elixir — no hardcoded maps)
- Dynamic call patterns (HTTP via internal wrappers, no static imports)
- Any combination of the above

## Solution

Async LLM enrichment layer that runs after the deterministic pipeline, streams results progressively to the UI, and writes LLM-discovered nodes/edges into Neo4j alongside deterministic results.

---

## Architecture

### Two-Phase Pipeline

```
Phase 1 — Deterministic (sync, unchanged, instant):
  GitHub URL
    → DependencyDetector + SystemDetector + MetadataDetector
    → Neo4j (initial graph)
    → UI renders immediately

  ContextManager.extract_context() adds one line at end:
    LLMEnrichmentWorker.enqueue(task_id, repo_path, evidence_corpus)

Phase 2 — LLM Enrichment (async, progressive):
  LLMEnrichmentWorker.run(task_id, repo_path, evidence_corpus)
    → WarmContextBuilder.build()       # Phase 2a: warm start
    → LLMAgentLoop.run()               # Phase 2b: bounded agentic loop
    → GraphMerger.merge()              # Phase 2c: merge + rollback on fail
    → EnrichmentSSE streams each emit to frontend
```

### Key Invariant

**Deterministic detector logic is untouched.** `ContextManager.extract_context()` gets one line added at its end. All existing tests remain valid.

---

## Components

### Module: WarmContextBuilder
- **Responsibility:** Builds warm starting context for the LLM agent before tool loop begins
- **Interface:** `build(repo_path, evidence_corpus) → WarmContext`
- **Dependencies:** filesystem (read-only). Entrypoints read from `evidence_corpus` passed in — no direct `SystemDetector` dependency.
- **Size target:** ≤200 lines, single responsibility
- **Output:**
  - File tree (all paths, no content)
  - Deterministic evidence corpus (what detectors already found: packages, URLs, env vars, docker images)
  - Top-K pre-grepped signal files: grep results (matching lines + 3-line context), NOT full content
  - K = 10, configurable via `ENRICHMENT_TOP_K` env var
  - Priority order: `docker-compose.yml`, `package.json`, `requirements.txt`, `*.csproj`, CI yaml (`*.github/workflows/*.yml`), `Dockerfile`, `README.md`, main entrypoints

### Module: ExtractionToolRegistry
- **Responsibility:** Sandboxed tool implementations exposed to the LLM agent
- **Interface:** `get_tools() → list[Tool]` (Anthropic tool_use format)
- **Dependencies:** filesystem (read-only), Neo4j writer (for emit tools)
- **Size target:** ≤200 lines
- **Tools exposed:**

| Tool | Signature | Notes |
|------|-----------|-------|
| `read_file` | `(path: str) → str` | Repo-sandboxed. Rejects paths outside repo root. |
| `grep` | `(pattern: str, path: str = ".", recursive: bool = True) → list[Match]` | Returns matching lines + 3-line context. Max 50 matches. |
| `list_dir` | `(path: str = ".") → list[Entry]` | Returns name, type (file/dir), size. |
| `emit_node` | `(type: str, name: str, props: dict) → NodeResult` | Validates props against ExtractionDecision schema. Upserts by (type, name). |
| `emit_edge` | `(from_name: str, to_name: str, relationship: str, props: dict) → EdgeResult` | Tags with enrichment_run_id. |

### Module: LLMAgentLoop
- **Responsibility:** Bounded agentic loop — calls Claude API with tool_use, enforces budget
- **Interface:** `run(warm_context: WarmContext, tools: list[Tool], budget: Budget) → LoopResult`
- **Dependencies:** Anthropic SDK, `ExtractionToolRegistry`, `EnrichmentSSE`
- **Size target:** ≤200 lines
- **Budget enforcement:**
  - Max tool calls: 15 (configurable via `ENRICHMENT_MAX_TOOL_CALLS`)
  - Max tokens: 50,000 (configurable via `ENRICHMENT_MAX_TOKENS`)
  - After each API response: check `usage.input_tokens + usage.output_tokens` cumulative
  - If over budget → send `stop_reason: budget_exceeded` → exit loop, trigger merge
- **Model:** `claude-sonnet-4-6` (cost/intelligence balance; Opus reserved for future high-stakes runs)

### Module: GraphMerger
- **Responsibility:** Confidence-aware merge of LLM-emitted nodes/edges into Neo4j; rollback on failure
- **Interface:** `merge(enrichment_run_id: str) → MergeResult`, `rollback(enrichment_run_id: str)`
- **Dependencies:** Neo4j writer, `decision_models.DecisionMode`, `decision_models.ReviewStatus`
- **Size target:** ≤150 lines
- **Merge rules:**
  - LLM found dep deterministic missed → new node, `DecisionMode.LLM_ADJUDICATED`
  - Both found same dep → MERGE evidence lists, keep higher confidence value, `DecisionMode.LLM_ADJUDICATED`
  - Conflict (LLM contradicts deterministic) → `ReviewStatus.NEEDS_REVIEW`, enqueue human review
- **Rollback:** All LLM-emitted nodes/edges tagged with `enrichment_run_id`. On failure → `DELETE WHERE enrichment_run_id = {id}`. Tags persist on success for audit trail.

### Module: LLMEnrichmentWorker
- **Responsibility:** Async job orchestrator — receives task_id, runs phases 2a–2c
- **Interface:** `enqueue(task_id: str, repo_path: Path, evidence: dict)`, `run(job)`
- **Dependencies:** `WarmContextBuilder`, `LLMAgentLoop`, `GraphMerger`, `EnrichmentSSE`
- **Size target:** ≤100 lines
- **Failure behavior:** LLM worker failure is non-fatal. Deterministic results already in Neo4j. Worker logs error, SSE sends `{event: "enrichment_failed", reason: "..."}`. UI shows deterministic results unchanged.
- **Frontend wiring:** Extraction API response (`POST /api/v1/extract`) includes `enrichment_stream_url: "/api/v1/enrichment/stream/{task_id}"`. Frontend subscribes to this URL automatically after extraction starts — no additional user action required.

### Module: EnrichmentSSE
- **Responsibility:** Streams progressive enrichment updates to frontend via Server-Sent Events
- **Interface:** `GET /api/v1/enrichment/stream/{task_id}` (new FastAPI endpoint)
- **Dependencies:** FastAPI `StreamingResponse`, asyncio queue per task_id
- **Size target:** ≤100 lines
- **Events emitted:**

| Event | Payload |
|-------|---------|
| `enrichment_started` | `{task_id, timestamp}` |
| `node_added` | `{type, name, props, decision_mode}` |
| `edge_added` | `{from, to, relationship, props}` |
| `budget_exceeded` | `{tool_calls_used, tokens_used}` |
| `enrichment_complete` | `{nodes_added, edges_added, duration_s}` |
| `enrichment_failed` | `{reason}` |

---

## emit_node Schema Validation

`props` validated against allowed fields before Neo4j write. Invalid fields logged + skipped (no emit failure):

```python
ALLOWED_NODE_PROPS = {
    "confidence": float,        # 0.0–1.0
    "detection_source": str,
    "decision_mode": DecisionMode,
    "review_status": ReviewStatus,
    "evidence": list,
    "dep_type": str,            # "database", "messaging", "payment", etc.
    "description": str,
}
```

Upsert behavior: `MERGE (n {type: $type, name: $name})` — if exists, update props, append evidence. If new, create.

---

## Token Budget Breakdown (default)

| Component | Tokens |
|-----------|--------|
| System prompt | ~1K |
| File tree | ~2K |
| Evidence corpus | ~5K |
| Top-10 pre-grepped signal files | ~10K |
| Warm context total | ~18K |
| 15 tool calls × ~2K per response | ~30K |
| **Total budget** | **~50K** |

---

## Out of Scope (v1)

- Container/Component level enrichment (same pattern, v2)
- Parallel LLM workers per repo (single worker per extraction)
- LLM-directed re-extraction (LLM cannot trigger a full re-run)
- Frontend subscription management UI (frontend subscribes automatically on extraction start)

---

## Testing

| Test | Type | Validates |
|------|------|-----------|
| `test_warm_context_builder.py` | Unit | Top-K file selection, grep output format |
| `test_llm_agent_loop.py` | Unit (mock LLM) | Budget enforcement: stops at 15 calls + 50K tokens |
| `test_graph_merger.py` | Unit | Merge rules: upsert, conflict flagging, rollback |
| `test_enrichment_sse.py` | Integration | SSE event stream for a full mock extraction |
| `test_llm_enrichment_worker.py` | Integration | Worker failure non-fatal, deterministic results preserved |

---

## Edge Cases

- **LLM emits malformed JSON** → tool handler catches, logs, skips field. Emit continues.
- **Neo4j write fails mid-loop** → SSE `enrichment_failed`, `GraphMerger.rollback(enrichment_run_id)` deletes all tagged nodes.
- **Repo has no known signal files** → `WarmContextBuilder` falls back to top-10 largest files at repo root.
- **All extraction refactors:** every module that touches this pipeline must be updated — not just the primary one (learned from cleanup.py incident).
