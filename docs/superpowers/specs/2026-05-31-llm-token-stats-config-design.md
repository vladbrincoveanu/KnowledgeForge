---
title: LLM Token Stats + Config Panel
date: 2026-05-31
status: approved
---

# LLM Token Stats + Config Panel

Surface MiniMax/Claude token usage in the System Metrics tab. Allow runtime override of API key and model via a config panel. Store per-run stats in sessionStorage.

---

## Problem

- `agent_loop.py` tracks `tokens_in + tokens_out` combined — no breakdown
- `enrichment_complete` WS event drops all token data before reaching the frontend
- `SystemMetrics.tsx` is a stub ("Coming soon...")
- Model is hardcoded in `llm_client.py`; no way to change without restart
- No visibility into rate limiter utilization

---

## Scope

Backend: 4 files modified, 1 new route file.
Frontend: 3 files modified, 1 new hook.

---

## Backend Changes

### Module: LoopResult (agent_loop.py)
- **Responsibility:** Carry separate input/output token counts out of the agent loop
- **Interface:** `LoopResult.tokens_in: int`, `LoopResult.tokens_out: int` (replaces `tokens_used`)
- **Dependencies:** Anthropic SDK `resp.usage.input_tokens` / `resp.usage.output_tokens`
- **Size target:** <10 lines changed

Split `tokens_used` into `tokens_in` and `tokens_out`. Accumulate separately per turn:
```python
tokens_in  += getattr(resp.usage, "input_tokens",  0)
tokens_out += getattr(resp.usage, "output_tokens", 0)
```

### Module: EnrichmentLLMClient (llm_client.py)
- **Responsibility:** Wrap Anthropic client with MiniMax proxy; expose configurable model
- **Interface:** `from_env() -> Optional[EnrichmentLLMClient]`; `self.model: str`
- **Dependencies:** `MINIMAX_API_KEY`, `ENRICHMENT_MODEL` env vars
- **Size target:** <5 lines changed

`from_env()` reads `ENRICHMENT_MODEL` (default: `"anthropic/claude-sonnet-4-20250514"`), stores as `self.model`. `messages_create()` uses `self.model` instead of hardcoded string.

### Module: RateCounter (llm_client.py)
- **Responsibility:** Track hourly request rate; expose current utilization
- **Interface:** `current_count() -> int` (computed inline in route, not a method)
- **Dependencies:** none
- **Size target:** 0 lines — logic inlined in route handler

`current_count()` is **not a method** on `RateCounter`. The route handler computes it inline:
```python
now = time.monotonic()
cutoff = now - rate_counter.window_s
current = sum(1 for t in rate_counter._timestamps if t > cutoff)
```

### Module: LLMEnrichmentWorker (worker.py)
- **Responsibility:** Run agent loop; emit token stats in completion event
- **Interface:** WS event `enrichment_complete` gains `{tokens_in, tokens_out, tool_calls_used, model, duration_s}`
- **Dependencies:** `LoopResult`, `EnrichmentLLMClient`, `time.monotonic()`
- **Size target:** <10 lines changed

Track `start = time.monotonic()` before agent loop call. After loop:
```python
ws.emit("enrichment_complete", {
    "partial": partial,
    "reason": partial_reason,
    "nodes_added": nodes_added,
    "tokens_in": result.tokens_in,
    "tokens_out": result.tokens_out,
    "tool_calls_used": result.tool_calls_used,
    "model": client.model,
    "duration_s": round(time.monotonic() - start, 2),
})
```

### Module: LLMConfigRouter (routes/llm_config.py — new)
- **Responsibility:** Expose LLM config read/write over HTTP; surface rate limiter state
- **Interface:** `GET /api/v1/config/llm`, `PUT /api/v1/config/llm`
- **Dependencies:** `get_rate_counter()`, `os.environ`
- **Size target:** <80 lines (incl. validation)

**Request validation (PUT body):**
```python
class LLMConfigPatch(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None

    @field_validator("model")
    @classmethod
    def model_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith("anthropic/"):
            raise ValueError("model must be 'anthropic/<version>'")
        return v
```

**GET response:**
```json
{
  "model": "anthropic/claude-sonnet-4-20250514",
  "api_key_set": true,
  "api_key_source": "override",
  "rate_limit_used": 12,
  "rate_limit_max": 100
}
```

`api_key_source` values: `"env"` (from .env bootstrap) | `"override"` (set via PUT). UI badge distinguishes them.

**PUT body:**
```json
{ "api_key": "sk-...", "model": "anthropic/claude-haiku-4-5-20251001" }
```
Both fields optional. Mutates `os.environ["MINIMAX_API_KEY"]` and/or `os.environ["ENRICHMENT_MODEL"]` in-process. Validation fails (400) if model format is invalid. Ephemeral — lost on container restart. Returns same shape as GET.

**Per-run isolation note:** Mutating env does NOT affect in-flight runs — each `LLMEnrichmentWorker.run()` creates a fresh `EnrichmentLLMClient` via `from_env()`. New runs after PUT pick up the new config.

Registered in `main.py`:
```python
app.include_router(llm_config.router, prefix="/api/v1/config")
```

---

## Frontend Changes

### Module: EnrichmentWSEvents type extension (useEnrichmentWS.ts)
- **Responsibility:** Type-safe WS event for enrichment_complete with token fields
- **Interface:** `enrichment_complete.data` gains `tokens_in, tokens_out, tool_calls_used, model, duration_s`
- **Dependencies:** none
- **Size target:** <5 lines changed

### Module: useLLMStats (hooks/useLLMStats.ts — new)
- **Responsibility:** Accumulate per-run token stats in sessionStorage; expose totals
- **Interface:** `{ runs: LLMRun[], totals: LLMTotals, clearStats: () => void }`
- **Dependencies:** `wsService`, sessionStorage key `kf_llm_stats`
- **Size target:** <80 lines

```typescript
type LLMRun = {
  task_id: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  tool_calls: number;
  duration_s: number;
  tps: number;          // (tokens_in + tokens_out) / duration_s
  timestamp: string;    // ISO
};

type LLMTotals = {
  tokens_in: number;
  tokens_out: number;
  tool_calls: number;
  runs_count: number;
};
```

On `enrichment_complete` WS event: append run to `sessionStorage['kf_llm_stats']` (JSON array). Hydrate from sessionStorage on mount.

`tps` = `(tokens_in + tokens_out) / duration_s`. Label in UI: **"avg tok/s"** with tooltip: `"Total tokens ÷ run duration (includes tool execution time)"`.

### Module: api.ts additions
- **Responsibility:** HTTP calls for LLM config CRUD
- **Interface:** `getLLMConfig(): Promise<LLMConfigResponse>`, `updateLLMConfig(patch): Promise<LLMConfigResponse>`
- **Dependencies:** existing `api.ts` base URL pattern
- **Size target:** <20 lines added

### Module: SystemMetrics (SystemMetrics.tsx — rebuild)
- **Responsibility:** Display LLM config controls + token stats
- **Interface:** standalone page component; no props
- **Dependencies:** `useLLMStats`, `getLLMConfig`, `updateLLMConfig`
- **Size target:** <200 lines

Three sections:

**1. Config Panel**
- Model dropdown: `anthropic/claude-sonnet-4-20250514` | `anthropic/claude-haiku-4-5-20251001`
- API key: password `<input>`, placeholder "Enter to override env key". Shows `● set` badge if `api_key_set: true` from GET, with color coded by `api_key_source`: `● env` (gray) vs `● override` (blue).
- ⚠️ Warning text below input: `"API key transmitted over HTTP — development use only"`
- Save button → `PUT /api/v1/config/llm`. Success toast; error inline.
- Rate limiter chip: `12 / 100 req/hr` (live from GET on mount).

**2. Session Totals Bar**
Four chips: `Tokens In`, `Tokens Out`, `Tool Calls`, `Runs`. Derived from `useLLMStats` totals.

**3. Per-Run Table**
Columns: `Task` (8-char truncated ID) | `Model` | `In` | `Out` | `avg tok/s` | `Calls` | `Duration` | `Time`.
Clear button (`sessionStorage` wipe + state reset). Empty state: "No enrichment runs this session."

Plain CSS table via `SystemMetrics.scss`. No chart library.

---

## Data Flow

```
enrichment runs
  → agent_loop accumulates tokens_in / tokens_out per turn
  → worker tracks start time, emits enrichment_complete with full stats
  → WS → useEnrichmentWS → enrichment_complete event
  → useLLMStats appends to sessionStorage
  → SystemMetrics reads useLLMStats → renders table + totals
```

Config flow:
```
UI model picker / API key input → PUT /api/v1/config/llm
  → os.environ mutated in-process
  → next enrichment run picks up new MINIMAX_API_KEY / ENRICHMENT_MODEL
```

---

## Constraints

- `os.environ` mutation is safe: `from_env()` is called per-run (not cached at startup). New runs after PUT pick up new config; in-flight runs are unaffected.
- `os.environ` mutation is not atomic under concurrent enrichments — race window is narrow (client instantiation only) and acceptable for a dev tool. Not safe for multi-tenant production use.
- API key sent over HTTP in PUT body — ⚠️ warning shown in UI. Not for production deployments.
- sessionStorage is per-tab; stats don't cross tabs — acceptable for now.
- Config is ephemeral; `MINIMAX_API_KEY` in `.env` is still the persistent bootstrap. UI distinguishes `● env` vs `● override` so users know their override is session-only.
- PUT validation: invalid model format returns 400 before any mutation occurs.

---

## File Map

| File | Action | Squad |
|------|--------|-------|
| `sources/Api/app/services/c4/enrichment/agent_loop.py` | Modify | ours |
| `sources/Api/app/services/c4/enrichment/llm_client.py` | Modify | ours |
| `sources/Api/app/services/c4/enrichment/worker.py` | Modify | ours |
| `sources/Api/app/endpoint/v1/routes/llm_config.py` | Create | ours |
| `sources/Api/main.py` | Modify (1 line) | ours |
| `sources/UI/src/hooks/useEnrichmentWS.ts` | Modify | ours |
| `sources/UI/src/hooks/useLLMStats.ts` | Create | ours |
| `sources/UI/src/services/api.ts` | Modify | ours |
| `sources/UI/src/@components/system-metrics/SystemMetrics/SystemMetrics.tsx` | Rebuild | ours |
| `sources/UI/src/@components/system-metrics/SystemMetrics/SystemMetrics.scss` | Modify | ours |
