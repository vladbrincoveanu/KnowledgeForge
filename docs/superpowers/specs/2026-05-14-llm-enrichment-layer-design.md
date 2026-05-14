# LLM Enrichment Layer — Design Spec
**Date:** 2026-05-14
**Scope:** C4 Context level (Container/Component follow same pattern in v2)
**Status:** Approved (post-grill, 12 design questions resolved)

---

## Problem

Current extraction pipeline is fully deterministic: hardcoded package maps, regex URL patterns, NUGET/npm/pip dependency lists. Fails on:
- Unknown package names (internal company wrappers)
- Novel ecosystems (Go, Rust, Elixir — no hardcoded maps)
- Dynamic call patterns (HTTP via internal wrappers, no static imports)
- Any combination of the above

## Solution

Async LLM enrichment layer that runs after the deterministic pipeline, streams results progressively to the UI via the existing WebSocket, and writes LLM-discovered nodes/edges into Neo4j + JSON alongside deterministic results.

---

## Architecture

### Two-Phase Pipeline

```
Phase 1 — Deterministic (sync, unchanged, instant):
  GitHub URL
    → DependencyDetector + SystemDetector + MetadataDetector
    → Neo4j (initial graph) + {task_id}.json
    → UI renders immediately

  ContextManager.extract_context() adds one line at end:
    LLMEnrichmentWorker.enqueue(task_id, repo_path, evidence_corpus)

Phase 2 — LLM Enrichment (async, progressive):
  LLMEnrichmentWorker.run(task_id, repo_path, evidence_corpus)
    → WarmContextBuilder.build()                # 2a: warm start
    → LLMAgentLoop.run()                        # 2b: bounded agentic loop
    → GraphMerger.merge() + JSONPersister       # 2c: persist + rollback on fail
    → EnrichmentWSEvents streams each emit via existing WebSocket
```

### Runtime Placement

Worker runs via `asyncio.create_task(LLMEnrichmentWorker.run(...))` from inside the existing extraction `BackgroundTask`. In-process, single uvicorn loop. Worker registers itself in a process-local `active_enrichments: dict[task_id, asyncio.Task]` for cancellation on DELETE.

Wall-clock outer timeout: `asyncio.wait_for(worker.run(), timeout=ENRICHMENT_TIMEOUT_S)`. Default 300s.

### Key Invariant

**Deterministic detector logic is untouched.** `ContextManager.extract_context()` gets one line added at its end. All existing tests remain valid. Existing `{task_id}.json` is never mutated by the worker.

### Concurrency / Race Model

Each extraction has a unique `task_id` UUID. `graph_writer` namespaces Neo4j writes by `extraction_task_id`. No two extractions share a task_id ⇒ no same-repo race possible. The enrichment worker writes within the same `task_id` namespace, tagged with its own `enrichment_run_id` for rollback isolation.

Process-global semaphore caps concurrent enrichments. Process-global 5h rolling request counter caps MiniMax usage.

---

## Components

### Module: WarmContextBuilder
- **Responsibility:** Builds warm starting context for the LLM agent before tool loop begins
- **Interface:** `build(repo_path, evidence_corpus: EvidenceCorpus) → WarmContext`
- **Dependencies:** filesystem (read-only). No detector dependency — entrypoints read from `evidence_corpus`.
- **Size target:** ≤200 lines
- **Output:**
  - File tree (all paths, no content)
  - Deterministic evidence corpus (rendered from `EvidenceCorpus`)
  - Top-K pre-grepped signal files: grep results (matching lines + 3-line context), NOT full content
  - K = 10, configurable via `ENRICHMENT_TOP_K`
  - Priority order: `docker-compose.yml`, `package.json`, `requirements.txt`, `*.csproj`, CI yaml (`*.github/workflows/*.yml`), `Dockerfile`, `README.md`, main entrypoints
  - Fallback: if none of the priority files exist, use top-10 largest text files at repo root.

### Module: EvidenceCorpus (pydantic model)
- **Responsibility:** Strict typed contract passed from deterministic phase to worker
- **Interface:** pydantic `BaseModel` — schema below
- **Size target:** ≤80 lines
- **Schema:**

```python
class DepEvidence(BaseModel):
    name: str
    type: str                # "package" | "url" | "docker_image" | ...
    confidence: float
    files_found_in: list[Path]

class EvidenceCorpus(BaseModel):
    repo_path: Path
    task_id: str
    languages: list[str]
    frameworks: list[str]
    deterministic_deps: list[DepEvidence]
    entrypoints: list[Path]
    detected_urls: list[str]
    env_vars: list[str]
    docker_images: list[str]
    package_files: list[Path]
```

### Module: ExtractionToolRegistry
- **Responsibility:** Sandboxed tool implementations exposed to the LLM agent
- **Interface:** `get_tools() → list[Tool]` (Anthropic tool_use format)
- **Dependencies:** filesystem (read-only), `EnrichmentGraphWriter`, `EnrichmentJSONPersister`
- **Size target:** ≤200 lines
- **Tools exposed:**

| Tool | Signature | Notes |
|------|-----------|-------|
| `read_file` | `(path: str) → str` | Repo-sandboxed via `Path.resolve().is_relative_to(repo_path)`. Binary → first 1KB + flag. >50KB → truncate + flag. |
| `grep` | `(pattern: str, path: str = ".", recursive: bool = True) → list[Match]` | Matching lines + 3-line context. Cap 50 matches → `truncated: true` flag. |
| `list_dir` | `(path: str = ".") → list[Entry]` | Name, type, size. Cap 200 entries. |
| `emit_node` | `(type: str, name: str, props: dict) → NodeResult` | Validates `props` against `ALLOWED_NODE_PROPS`. Requires non-empty `evidence`. Upserts by `(type, canonical_name)`. |
| `emit_edge` | `(from_name: str, to_name: str, relationship: str, props: dict) → EdgeResult` | Tags with `enrichment_run_id`. Errors if `from`/`to` unknown. |

**Tool error semantics:** all failures return Anthropic `tool_result(is_error=True, content=json.dumps({error, msg}))`. Loop continues, LLM adapts. Path-escape attempts return generic `invalid_path` (no filesystem leak).

**Hard reject:** `emit_node` without `evidence` array is rejected (prevents hallucination). LLM must grep/read before emitting.

### Module: EnrichmentLLMClient
- **Responsibility:** Thin wrapper around Anthropic SDK, pointed at MiniMax Anthropic-compatible proxy
- **Interface:** `messages_create(messages, tools, system, **kwargs) → APIResponse`
- **Dependencies:** `anthropic.Anthropic(base_url, api_key)`, request-rate counter
- **Size target:** ≤100 lines
- **Config:**
  - `MINIMAX_API_KEY` (required-or-skip)
  - `MINIMAX_BASE_URL=https://api.minimax.io/anthropic`
  - `ENRICHMENT_MODEL=MiniMax-M2.7-highspeed`
- **Rate handling:** every `messages_create` first calls `record_request()` on the process-global 5h rolling deque. On HTTP 429, return special `RateLimitMidrunError` to caller.

### Module: LLMAgentLoop
- **Responsibility:** Bounded agentic loop — calls LLM with tool_use, enforces per-run budget
- **Interface:** `run(warm_context: WarmContext, tools: list[Tool], budget: Budget) → LoopResult`
- **Dependencies:** `EnrichmentLLMClient`, `ExtractionToolRegistry`, `EnrichmentWSEvents`
- **Size target:** ≤200 lines
- **Budget enforcement:**
  - Max tool calls: 15 (`ENRICHMENT_MAX_TOOL_CALLS`)
  - Max tokens: 50,000 (`ENRICHMENT_MAX_TOKENS`)
  - After each API response: cumulate `usage.input_tokens + usage.output_tokens`
  - Over budget → `stop_reason: budget_exceeded` → exit loop, finalize partial results
- **Turn 1 tool-forcing:** `tool_choice={"type": "any"}` on first call to prevent no-op chat responses.
- **System prompt:** strict role + objective + DO/DO-NOT + output contract + confidence rubric + 1–2 few-shot examples. Lists `deterministic_deps.names` so LLM doesn't re-emit.

### Module: EnrichmentGraphWriter
- **Responsibility:** Streaming per-emit writes to Neo4j with `enrichment_run_id` tagging
- **Interface:** `upsert_node(...)`, `upsert_edge(...)`, `rollback(enrichment_run_id)`
- **Dependencies:** existing Neo4j client (shared via DI). Does NOT extend `C4GraphWriter` — separate writer for streaming shape.
- **Size target:** ≤150 lines
- **Cypher:**
  ```
  MERGE (n {type: $type, canonical_name: $canonical})
    ON CREATE SET n.name = $name, n.created_by = $run_id,
                  n.confidence = $confidence, n.evidence = $evidence
    ON MATCH SET n.aliases = coalesce(n.aliases, []) + [$name],
                 n.confidence = CASE WHEN $confidence > n.confidence THEN $confidence ELSE n.confidence END,
                 n.evidence = n.evidence + $evidence
  SET n.enrichment_run_id = $run_id
  ```
- **Canonical key:** reuse `normalize_logical_name()` from `context_manager.py:281`. Lowercased, suffixes (`-api`, `-sdk`, `-client`) stripped, whitespace collapsed.
- **Display vs key:** `canonical_name` is dedup key; `name` is first-seen display; `aliases` is audit trail.

### Module: EnrichmentJSONPersister
- **Responsibility:** Append-only per-emit log + final consolidated JSON snapshot
- **Interface:** `append(event)`, `finalize(run_summary)`, `rollback(enrichment_run_id)`
- **Dependencies:** filesystem
- **Size target:** ≤80 lines
- **Files written:**
  - `sources/data/c4_enrichments/{task_id}.jsonl` — one JSON line per emit (crash-safe)
  - `sources/data/c4_enrichments/{task_id}.json` — final consolidated snapshot on natural/partial completion
  - Deterministic `sources/data/c4_extractions/{task_id}.json` is **untouched**
- **Rollback:** delete both files if `enrichment_failed`.

### Module: GraphMerger
- **Responsibility:** Confidence-aware merge rules + conflict detection (calls `EnrichmentGraphWriter` per emit)
- **Interface:** `apply_emit(node_or_edge, deterministic_index) → DecisionMode`, `finalize(run_id)`, `rollback(run_id)`
- **Dependencies:** `EnrichmentGraphWriter`, `EnrichmentJSONPersister`, `decision_models.DecisionMode`, `decision_models.ReviewStatus`
- **Size target:** ≤150 lines
- **Merge rules:**
  - LLM found dep deterministic missed → new node, `DecisionMode.LLM_ADJUDICATED`
  - Both found same dep (canonical match) → MERGE evidence, max confidence, `DecisionMode.LLM_ADJUDICATED`
  - Conflict (LLM contradicts deterministic dep_type/category) → `ReviewStatus.NEEDS_REVIEW`, enqueue review item

### Module: LLMEnrichmentWorker
- **Responsibility:** Async job orchestrator — phases 2a–2c, pre-flight gating, timeout
- **Interface:** `enqueue(task_id, repo_path, evidence: EvidenceCorpus)`, `run()`
- **Dependencies:** `WarmContextBuilder`, `LLMAgentLoop`, `GraphMerger`, `EnrichmentWSEvents`
- **Size target:** ≤150 lines
- **Pre-flight gates (in order):**
  1. `ENRICHMENT_ENABLED=true`? else skip.
  2. `MINIMAX_API_KEY` present? else WS `enrichment_skipped {reason: 'no_api_key'}`.
  3. `await _semaphore.acquire()` (max 2 concurrent).
  4. `can_run()` rate check (rolling 5h, 600 req budget)? else WS `enrichment_skipped {reason: 'rate_limit_5h'}`.
  5. Run inside `asyncio.wait_for(..., timeout=300)`.
- **Stop-reason matrix:**

| Stop reason | Outcome | WS event |
|---|---|---|
| `natural_stop` (LLM done) | Keep all, finalize JSON | `enrichment_complete {partial: false}` |
| `budget_exceeded` (tokens/tool_calls) | Keep partials, finalize JSON | `enrichment_complete {partial: true, reason: 'budget'}` |
| `timeout` (wall-clock) | Keep partials, finalize JSON | `enrichment_complete {partial: true, reason: 'timeout'}` |
| `rate_limit_midrun` (429) | Keep partials, finalize JSON | `enrichment_complete {partial: true, reason: 'rate_limit'}` |
| `neo4j_error` | Rollback `enrichment_run_id` (Neo4j + JSON) | `enrichment_failed {reason: 'persistence'}` |
| `worker_exception` | Rollback | `enrichment_failed {reason: 'internal'}` |

- **Failure non-fatal:** deterministic results already in Neo4j + `{task_id}.json`. UI shows them unchanged.

### Module: EnrichmentWSEvents
- **Responsibility:** Emit enrichment events through the existing WebSocket router (no new endpoint)
- **Interface:** `emit(task_id, event_name, payload)`
- **Dependencies:** existing `websocket.router` connection manager
- **Size target:** ≤80 lines
- **Events emitted (added to existing WS event types):**

| Event | Payload |
|-------|---------|
| `enrichment_started` | `{task_id, run_id, timestamp}` |
| `enrichment_skipped` | `{task_id, reason}` |
| `node_added` | `{type, name, canonical_name, props, decision_mode}` |
| `edge_added` | `{from, to, relationship, props}` |
| `enrichment_complete` | `{nodes_added, edges_added, duration_s, partial: bool, reason?}` |
| `enrichment_failed` | `{reason}` |

Frontend already subscribed to the WS for `extraction_progress`; just adds handlers for new event types. No new endpoint, no new subscription protocol.

---

## emit_node Schema Validation

`props` validated against allowed fields before Neo4j write. Invalid fields logged + skipped. Required: non-empty `evidence`.

```python
ALLOWED_NODE_PROPS = {
    "confidence": float,        # 0.0–1.0
    "detection_source": str,
    "decision_mode": DecisionMode,
    "review_status": ReviewStatus,
    "evidence": list,           # REQUIRED, non-empty
    "dep_type": str,            # "database" | "messaging" | "payment" | ...
    "description": str,
}
```

Upsert: `MERGE (n {type: $type, canonical_name: $canonical})` — see `EnrichmentGraphWriter` Cypher above.

---

## Token & Request Budget (default)

| Component | Tokens / Reqs |
|-----------|---------------|
| System prompt | ~1K |
| File tree | ~2K |
| Evidence corpus | ~5K |
| Top-10 pre-grepped signal files | ~10K |
| Warm context total | ~18K |
| 15 tool calls × ~2K per response | ~30K |
| **Per-run token total** | **~50K** |
| **Per-run request total** | **≤16 (1 initial + 15 tool turns)** |
| **Global 5h request budget** | **600 (leaves 400 for other LLM features)** |
| **Max concurrent enrichments** | **2** |

---

## Configuration (env vars)

| Var | Default | Purpose |
|---|---|---|
| `ENRICHMENT_ENABLED` | `true` | Ops kill switch |
| `MINIMAX_API_KEY` | — | Required (skip if absent) |
| `MINIMAX_BASE_URL` | `https://api.minimax.io/anthropic` | API endpoint |
| `ENRICHMENT_MODEL` | `MiniMax-M2.7-highspeed` | LLM model |
| `ENRICHMENT_MAX_TOOL_CALLS` | `15` | Per-run tool cap |
| `ENRICHMENT_MAX_TOKENS` | `50000` | Per-run token cap |
| `ENRICHMENT_TIMEOUT_S` | `300` | Wall-clock cap |
| `ENRICHMENT_TOP_K` | `10` | Pre-grep file count |
| `ENRICHMENT_MAX_CONCURRENT` | `2` | Process-global semaphore |
| `ENRICHMENT_REQ_BUDGET_5H` | `600` | Rolling-window request cap |

---

## Out of Scope (v1)

- Container/Component level enrichment (same pattern, v2)
- Parallel LLM workers per repo (single worker per extraction)
- LLM-directed re-extraction (LLM cannot trigger a full re-run)
- Multi-process durable queue (in-process asyncio only; uvicorn restart kills in-flight)
- Disk-persisted rate counter (in-memory only — provider 429 is source of truth)

---

## Testing

| Test | Type | Validates |
|------|------|-----------|
| `test_warm_context_builder.py` | Unit | Top-K file selection, grep output format, fallback to largest files |
| `test_evidence_corpus.py` | Unit | Pydantic schema accepts/rejects expected shapes |
| `test_extraction_tool_registry.py` | Unit | Path sandbox, error returns, evidence-required reject |
| `test_llm_agent_loop.py` | Unit (mock LLM) | Budget enforcement (15 calls + 50K tokens), turn-1 tool-forcing |
| `test_enrichment_graph_writer.py` | Unit | Canonical dedup, alias accumulation, rollback by run_id |
| `test_enrichment_json_persister.py` | Unit | JSONL append, final snapshot, rollback delete |
| `test_graph_merger.py` | Unit | Merge rules: upsert, conflict flagging |
| `test_enrichment_ws_events.py` | Integration | Event stream over existing WebSocket |
| `test_llm_enrichment_worker.py` | Integration | Pre-flight gates, stop-reason matrix, deterministic preservation |

---

## Edge Cases

- **No `MINIMAX_API_KEY`** → WS `enrichment_skipped {reason: 'no_api_key'}`, deterministic unaffected.
- **`ENRICHMENT_ENABLED=false`** → worker exits immediately, no WS event.
- **Rate budget exhausted** → `enrichment_skipped {reason: 'rate_limit_5h'}`.
- **MiniMax 429 mid-loop** → keep partials, `enrichment_complete {partial: true, reason: 'rate_limit'}`.
- **LLM emits malformed JSON in tool call** → Anthropic SDK rejects; loop continues with `is_error=true` tool_result.
- **LLM emits node without evidence** → tool rejects, loop continues, LLM expected to retry with evidence.
- **LLM hallucinates path** → `read_file` returns `not_found` error to LLM.
- **Path escape attempt** (`../../etc/passwd`) → tool returns generic `invalid_path`, no filesystem leak.
- **Neo4j write fails mid-loop** → `enrichment_failed`, rollback Neo4j + JSON by `enrichment_run_id`.
- **Wall-clock timeout** → `asyncio.wait_for` cancels; treated same as `budget_exceeded` (keep partials).
- **Repo has no known signal files** → `WarmContextBuilder` falls back to top-10 largest text files at repo root.
- **Uvicorn restart kills in-flight worker** → no durable queue; WS connection drops; user sees deterministic results only. Acceptable v1.
- **Rerun of same task_id** → never happens at API level (each POST gets new UUID). `clear_extraction(task_id)` wipes all (deterministic + enrichment) — by design.
- **DELETE of task** → `active_enrichments[task_id].cancel()`, Neo4j `clear_extraction`, JSON files removed.
- **All extraction refactors:** every module that touches this pipeline must be updated — not just the primary one (learned from cleanup.py incident).
