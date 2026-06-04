# SystemMetrics — Real Test Prompt + TPS — Design Spec

**Date:** 2026-06-01
**Status:** Approved (design complete, grill-me pass resolved)
**Scope:** Replace misleading "Test Connection" button with real LLM test prompt. Add server-accurate TPS via stream timing. Unify model field across endpoints.

---

## 1. Problem

The current `Test Connection` button in `SystemMetrics` (`sources/UI/src/@components/system-metrics/SystemMetrics/SystemMetrics.tsx:62-76`) calls `llmConfigAPI.updateConfig({})` — an empty PUT that just echoes the current env config. **It does not send a prompt or invoke the model.** The button name is misleading.

The per-run TPS column (`useLLMStats.ts:80-82`) computes `(tokens_in + tokens_out) / duration_s` where `duration_s` includes tool execution and DB write time. The tooltip (`SystemMetrics.tsx:206`) admits this. The result is session throughput, not LLM model speed.

There is no way for a user to verify that the configured provider actually responds with a model, and no way to measure real model TPS in isolation from pipeline overhead.

## 2. Goals

- One-click verification that the configured LLM provider responds with the configured model.
- Server-side measurement of **time-to-first-token (TTFT)** and **tokens-per-second (TPS)** scoped to the model's actual generation, not pipeline overhead.
- User-editable test prompt with a sensible default, capped to prevent abuse.
- Persistent result card showing all stats + the model's actual response.
- Free-text model input (paste any `provider/model` or `MiniMax-<version>` string) replacing the hardcoded dropdown.
- Shared `ModelName` Pydantic type so all model-bearing endpoints share the same OpenAPI schema.

## 3. Non-Goals

- Fixing the per-run TPS formula in `useLLMStats.ts` (deferred — see §10).
- Persisting test history across sessions.
- Multi-prompt load testing.
- Cost estimation per test.
- Provider-side caching of test responses (always fresh).

## 4. Architecture

### 4.1 File Map

```
sources/Api/
  app/services/c4/enrichment/llm_client.py        [+messages_stream() method on EnrichmentLLMClient]
  app/endpoint/v1/routes/llm_config.py            [+POST /test-prompt route, +use ModelName type]
  app/endpoint/v1/schemas/llm.py                  [NEW — shared Pydantic types: ModelName, TestPromptRequest]
  tests/unit/endpoint/v1/routes/test_llm_config.py [+SSE tests]
  tests/unit/endpoint/v1/schemas/test_llm.py      [NEW — schema tests]

sources/UI/
  src/@components/system-metrics/SystemMetrics/SystemMetrics.tsx
    [replace Test Connection block w/ prompt input + Run btn + ResultCard]
  src/@components/system-metrics/SystemMetrics/SystemMetrics.scss
    [styles for prompt input, result card, copy/clear btns]
  src/@components/system-metrics/SystemMetrics/SystemMetrics.test.tsx [NEW or extend]
  src/@components/system-metrics/SystemMetrics/ResultCard.tsx [NEW — extracted card component]
  src/hooks/useTestPrompt.ts                      [NEW — SSE consumer + state mgmt]
  src/hooks/useTestPrompt.test.ts                 [NEW]
  src/hooks/useLLMStats.ts                        [+tooltip note in run table header — scope expansion]
  src/services/api.ts                             [+llmConfigAPI.testPrompt(prompt, model?) → AsyncIterable<TestEvent>]
  src/schemas/modelName.ts                        [NEW — TS mirror of Pydantic ModelName regex for client-side validation]
```

### 4.2 Data Flow

```
[User types prompt in SystemMetrics]
        │
        ▼
[useTestPrompt.run(prompt)]
        │
        ▼
[llmConfigAPI.testPrompt(prompt, model?)]
        │  POST /v1/llm-config/test-prompt
        │  Body: {prompt, model?}
        │  Accept: text/event-stream
        ▼
[FastAPI route handler]
        │  Validates prompt length (1-500)
        │  Validates model via ModelName type
        │  Resolves env: MINIMAX_API_KEY, ENRICHMENT_MODEL (or override)
        │  Calls EnrichmentLLMClient.messages_stream(messages=[{role:user, content:prompt}])
        ▼
[EnrichmentLLMClient.messages_stream()]
        │  Uses Anthropic SDK with base_url=MINIMAX_API_URL
        │  Returns AsyncIterator[StreamEvent]
        │  SDK call wrapped in asyncio.to_thread (already async-friendly)
        ▼
[Anthropic SDK → MiniMax proxy → upstream model]
        │
        ▼ (SSE events stream back through SDK)
[Route handler emits SSE frames to client]
        │  meta: {ttft_ms}
        │  chunk: {delta}
        │  done: {total_ms, tokens_in, tokens_out, tps}
        │  error: {message, code}  (on any failure)
        ▼
[useTestPrompt accumulates chunks, builds TestResult]
        │
        ▼
[ResultCard renders stats + response]
```

### 4.3 Module Design Blocks

### Module: `EnrichmentLLMClient.messages_stream`
- **Responsibility:** Async-iterate over streamed response events from the configured Anthropic-compatible provider.
- **Interface:** `async def messages_stream(self, messages: list[dict], max_tokens: int = 256) -> AsyncIterator[dict]` yielding `{type: "content_block_delta", delta: {text: str}}` events from the SDK, normalized to `{type: "chunk", delta: str}` shape.
- **Dependencies:** `anthropic.Anthropic` client (already initialized with `base_url=MINIMAX_API_URL`).
- **Size target:** 40 LOC.

### Module: `POST /v1/llm-config/test-prompt`
- **Responsibility:** Accept test prompt, stream response back as SSE with timing metadata.
- **Interface:** `POST /v1/llm-config/test-prompt` body `TestPromptRequest` → `StreamingResponse(media_type="text/event-stream")`.
- **Dependencies:** `EnrichmentLLMClient.from_env()`, `ModelName` type, `TestPromptRequest` schema.
- **Size target:** 80 LOC (including request validation, error mapping, SSE frame emission).

### Module: `ModelName` (shared Pydantic type)
- **Responsibility:** Validate model strings across all model-bearing endpoints. Single source of truth for the model regex shown in OpenAPI.
- **Interface:** `ModelName = Annotated[str, AfterValidator(_validate)]` where `_validate` raises `ValueError` for non-matching strings.
- **Dependencies:** Pydantic v2.
- **Size target:** 15 LOC (validator + regex constant).

### Module: `useTestPrompt` hook
- **Responsibility:** Manage SSE fetch lifecycle, accumulate streamed chunks, expose typed result.
- **Interface:** `useTestPrompt() → {status: "idle"|"running"|"ok"|"err", result: TestResult | null, error: TestError | null, run(prompt: string, model?: string): Promise<void>, reset(): void}`.
- **Dependencies:** `llmConfigAPI.testPrompt()` (AsyncIterable). No external state libs.
- **Size target:** 100 LOC.

### Module: `ResultCard` component
- **Responsibility:** Render a `TestResult` as a stat grid + response `<pre>` + Copy/Clear buttons.
- **Interface:** `ResultCard({result: TestResult, onClear: () => void})`. Pure presentational.
- **Dependencies:** None beyond shared types.
- **Size target:** 60 LOC.

### Module: `SystemMetrics.tsx` updates
- **Responsibility:** Replace "Test Connection" button block with prompt input + Run button + `<ResultCard>`. Replace model `<select>` with free-text `<input>` + suggestion list. Add tooltip to per-run TPS column noting scope difference.
- **Interface:** Composes `useTestPrompt`; renders inline in existing LLM Config section.
- **Dependencies:** `useTestPrompt`, `ResultCard`, `modelName.ts` (for client-side regex validation).
- **Size target:** +80 LOC net change.

## 5. Backend Specification

### 5.1 Endpoint

`POST /v1/llm-config/test-prompt`

### 5.2 Request

```python
class TestPromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    model: Optional[ModelName] = None
```

### 5.3 Response (SSE)

`Content-Type: text/event-stream; charset=utf-8`
`Cache-Control: no-cache`
`X-Accel-Buffering: no`  (disables nginx buffering)

Frame shapes:

```
data: {"type":"meta","model":"MiniMax-M2.7","ttft_ms":342,"ts":"2026-06-01T10:00:00.123Z"}

data: {"type":"chunk","delta":"p"}

data: {"type":"chunk","delta":"ong"}

data: {"type":"done","total_ms":1247,"tokens_in":8,"tokens_out":3,"tps":2.4}
```

Error frame:
```
data: {"type":"error","message":"Provider rate limit exceeded","code":"rate_limited"}
```

### 5.4 Server-Side TPS Calculation

```python
ttft_ms = first_chunk_ts_ms - request_start_ms
total_ms = last_chunk_ts_ms - request_start_ms
generation_ms = last_chunk_ts_ms - first_chunk_ts_ms
# Floor generation_ms at 50ms to avoid div-by-zero / inflated TPS on 1-token responses
tps = round(tokens_out / max(generation_ms / 1000, 0.05), 2)
```

Token counts: estimated from accumulated delta text via `sum(len(delta) // 4 for delta in chunks)`. The Anthropic SDK's `message_stop` event includes a `usage` block, but the current `messages_stream()` implementation yields only chunk events (non-delta events are filtered). Threading usage through would require a contract change to `messages_stream`. For a test panel, the `len/4` estimate is sufficient; deviation documented as follow-up (§10).

### 5.5 Error Codes

| Code | HTTP Status | Cause |
|---|---|---|
| `invalid_prompt` | 422 (Pydantic v2) | prompt empty, >500 chars, or contains control chars. Note: Pydantic v2 returns 422 for validation errors; spec originally said 400 but the actual impl + tests assert 422. Frontend pre-validates so the distinction is not user-visible. |
| `invalid_model` | 422 (Pydantic v2) | model string fails `ModelName` regex |
| `no_api_key` | 401 | `MINIMAX_API_KEY` env not set |
| `provider_unavailable` | 502 | Anthropic SDK raises any error (401/403/5xx, network, parse) |
| `provider_timeout` | 504 | 15s server-side timeout exceeded |
| `client_disconnected` | (closed) | FastAPI detects `request.is_disconnected()` mid-stream |

### 5.6 Rate Limiting

**Test runs do NOT consume `RateCounter`.** Tests are user-driven dev/QA actions, infrequent, not part of the enrichment budget. No new counter introduced (YAGNI — see §10 follow-ups for load-test scenario).

### 5.7 Disconnect Handling

The route handler runs `EnrichmentLLMClient.messages_stream()` in an async generator. Between yields, it polls `await request.is_disconnected()`. If disconnect detected, raises `ClientDisconnect`, which is caught and silently exits the generator. The underlying Anthropic SDK call (wrapped in `asyncio.to_thread`) is not directly cancellable, but the route handler returns immediately and FastAPI closes the response — the thread continues until completion but its result is discarded. Acceptable for short test prompts.

### 5.8 Server-Side Timeout

15 seconds total (including connect + first byte). Enforced via `asyncio.wait_for()` around the stream iteration. On timeout, emit `error` frame with `code: "provider_timeout"`.

## 6. Frontend Specification

### 6.1 `useTestPrompt` Hook

```typescript
type TestStatus = "idle" | "running" | "ok" | "err";

interface TestResult {
  model: string;
  prompt: string;
  response: string;
  ttftMs: number;
  totalMs: number;
  tokensIn: number;
  tokensOut: number;
  tps: number;        // server-calculated
  timestamp: string;  // ISO
}

interface TestError {
  code: string;
  message: string;
  httpStatus?: number;
}

interface UseTestPromptReturn {
  status: TestStatus;
  result: TestResult | null;
  error: TestError | null;
  run: (prompt: string, model?: string) => Promise<void>;
  reset: () => void;
}
```

### 6.2 SSE Consumer Flow

1. Set `status="running"`, clear prior `result` and `error`.
2. Validate prompt locally (1-500 chars). On fail, set `error` and return.
3. `fetch('/v1/llm-config/test-prompt', {method: 'POST', headers: {Accept: 'text/event-stream', 'Content-Type': 'application/json'}, body: JSON.stringify({prompt, model}), signal: AbortSignal.timeout(18_000)})`.
4. Get reader from `response.body`. Read chunks via `reader.read()`.
5. Decode UTF-8, split on `\n\n`, parse each `data: ` line as JSON.
6. Switch on `type`:
   - `meta` → store `model`, `ttftMs` in pending result object
   - `chunk` → append `delta` to `response` accumulator
   - `done` → finalize result, set `status="ok"`
   - `error` → set `error`, set `status="err"`
7. On reader end without `done`/`error` → set `error={code: "stream_truncated", message: "Stream ended without completion"}`.
8. On fetch reject (network) → set `error={code: "network", message: err.message}`.
9. On AbortSignal timeout → set `error={code: "timeout", message: "No response in 18s"}`.

### 6.3 `llmConfigAPI.testPrompt`

```typescript
testPrompt(prompt: string, model?: string, signal?: AbortSignal): AsyncIterable<TestEvent>
```

Wraps fetch + reader. Yields parsed SSE events. Lets `useTestPrompt` consume via `for await`. Exposed as AsyncIterable (not callback-based) for testability with synthetic readers.

### 6.4 `ResultCard` Component

Grid layout:
- Row 1: `TTFT: 342ms` · `Total: 1.25s` · `In: 8` · `Out: 3` · `TPS: 2.4`
- Row 2: `<pre>` containing model response (monospace, max-height 200px, scrollable)
- Row 3: `Copy` button (copies response to clipboard) · `Clear` button (calls `onClear`)

### 6.5 `SystemMetrics.tsx` UI Changes

Replace the existing "Test Connection" button block (lines 132-145) with:

```jsx
<div className="sm-test-panel">
  <label htmlFor="test-prompt">Test Prompt</label>
  <textarea
    id="test-prompt"
    defaultValue="Reply with the single word: pong"
    maxLength={500}
    rows={2}
  />
  <button onClick={() => run(textarea.value, selectedModel)} disabled={status === "running"}>
    {status === "running" ? "Running..." : "Run Test"}
  </button>
  {result && <ResultCard result={result} onClear={reset} />}
  {error && <p className="sm-error">{error.message}</p>}
</div>
```

Replace model `<select>` (lines 101-109) with:

```jsx
<input
  type="text"
  list="known-models"
  value={selectedModel}
  onChange={...}
  placeholder="MiniMax-M2.7 or anthropic/claude-sonnet-4-20250514"
/>
<datalist id="known-models">
  <option value="MiniMax-M2.7" />
  <option value="anthropic/claude-sonnet-4-20250514" />
  <option value="anthropic/claude-haiku-4-5-20251001" />
</datalist>
```

### 6.6 Per-Run TPS Tooltip

Update `useLLMStats.ts` callers — change the title attribute on the TPS `<td>` (line 206) to:

```
"For batch enrichment runs. Includes tool execution + DB writes. For pure LLM speed, use the Test Prompt panel above."
```

## 7. Shared Schema: `ModelName`

### 7.1 Pydantic (Backend)

```python
# sources/Api/app/endpoint/v1/schemas/llm.py
import re
from typing import Annotated
from pydantic import AfterValidator

_MODEL_RE = re.compile(r"^(anthropic/[A-Za-z0-9._-]+|MiniMax-[A-Za-z0-9._-]+)$")

def _validate(v: str) -> str:
    if not _MODEL_RE.match(v):
        raise ValueError(
            "Model must be 'anthropic/<name>' or 'MiniMax-<version>'"
        )
    return v

ModelName = Annotated[str, AfterValidator(_validate)]
```

Applied to `LLMConfigPatch.model`, `TestPromptRequest.model`, future endpoints.

### 7.2 TypeScript (Frontend)

```typescript
// sources/UI/src/schemas/modelName.ts
export const MODEL_NAME_RE = /^(anthropic\/[A-Za-z0-9._-]+|MiniMax-[A-Za-z0-9._-]+)$/;

export function isValidModelName(s: string): boolean {
  return MODEL_NAME_RE.test(s);
}
```

Used for client-side pre-validation before sending the Run request. Server is the source of truth.

## 8. Error Handling

| Case | Backend | Frontend |
|---|---|---|
| Prompt empty / >500 chars | 400 `invalid_prompt` | Inline field error, red border, no request sent |
| Invalid model string | 400 `invalid_model` | Toast: "Invalid model format" + reset input |
| No `MINIMAX_API_KEY` | 401 `no_api_key` | Toast: "Set API key first" + scroll to key input |
| Provider 401/403 | 502 `provider_unauthorized` | Toast: "API key rejected by provider" + suggest re-saving key |
| Provider 5xx / network | 502 `provider_unavailable` | Toast: "Provider unavailable. Retry?" + Re-run button |
| Provider timeout | 504 `provider_timeout` | Toast: "Provider timed out (>15s)" + Re-run button |
| Stream interrupted mid-flight | (stream ends) | Result card shows partial response + "Stream interrupted" badge |
| AbortSignal timeout (18s frontend) | (stream continues server-side, eventually closes) | Toast: "No response in 18s. Server may still be processing." + Cancel button |
| TPS very small (1-token response) | `tps: 0` in `done` (floored) | Result card shows `0` |
| Concurrent Run clicks | n/a (only one in-flight at a time) | Run button disabled while `status === "running"` |

**No client-side retry.** Failures are user-visible; let the user decide to retry.

## 9. Testing

### 9.1 Backend Unit

`sources/Api/tests/unit/endpoint/v1/routes/test_llm_config.py`:

- `test_test_prompt_returns_sse_stream` — mock `EnrichmentLLMClient.messages_stream` to yield 3 chunks; assert response is `text/event-stream` and contains 3 `chunk` frames + 1 `done` frame.
- `test_test_prompt_validates_prompt_length` — empty → 400, 501 chars → 400.
- `test_test_prompt_rejects_invalid_model` — `"gpt-3.5"` → 422 (Pydantic v2 default).
- `test_test_prompt_returns_401_when_no_key` — unset `MINIMAX_API_KEY` → 401.
- `test_test_prompt_does_not_consume_rate_counter` — assert `RateCounter._timestamps` unchanged after test.
- `test_test_prompt_emits_meta_first_with_ttft` — assert first event has `type: "meta"`, `ttft_ms: int`.
- `test_test_prompt_done_event_has_tps` — mock 3 chunks spanning 100ms, assert `tps: int > 0`.
- `test_test_prompt_handles_provider_error` — mock raises `anthropic.APIStatusError` → 502 + `error` SSE frame with `code: "provider_unavailable"`.
- `test_test_prompt_handles_client_disconnect` — mock stream that checks an `is_disconnected` flag; trigger disconnect; assert generator exits cleanly.
- `test_test_prompt_enforces_15s_timeout` — mock stream that sleeps 20s; assert `provider_timeout` error.

`sources/Api/tests/unit/endpoint/v1/schemas/test_llm.py`:

- `test_model_name_accepts_anthropic_format` — `"anthropic/claude-sonnet-4-20250514"` → no raise.
- `test_model_name_accepts_minimax_format` — `"MiniMax-M2.7"` → no raise.
- `test_model_name_rejects_unknown` — `"gpt-4"`, `"claude"`, `""` → ValueError.

### 9.2 Frontend Unit

`sources/UI/src/hooks/useTestPrompt.test.ts`:

- `run()` sets `status="running"`, then `"ok"` on `done` event.
- Accumulates `chunk` deltas into `response` string.
- `reset()` clears `result` and `error`.
- `error` event → `status="err"`, `error.message` set.
- AbortSignal timeout → `error.code === "timeout"`.
- Local prompt validation: empty prompt → `error`, no fetch called.
- Local prompt validation: prompt >500 chars → input maxLength enforces.

`sources/UI/src/@components/system-metrics/SystemMetrics/SystemMetrics.test.tsx`:

- Renders prompt textarea + Run button.
- Clicking Run calls `llmConfigAPI.testPrompt` with textarea content.
- Renders `ResultCard` on `status="ok"`.
- Renders error message on `status="err"`.
- Run button disabled while `status="running"`.

### 9.3 Manual Smoke (Playwright)

1. Open workspace → SystemMetrics tab.
2. Verify free-text model input accepts `MiniMax-M2.7` and `anthropic/claude-haiku-4-5-20251001`.
3. Type custom prompt → click Run → verify result card shows TTFT, total, in, out, TPS, response text.
4. Click Copy button → verify clipboard contains response text.
5. Type prompt with 501 chars → verify red border, no request sent.
6. Set invalid model string → click Run → verify 400 error toast.
7. Disconnect wifi mid-stream → verify partial response + interrupted badge.
8. Click Run, then click Run again before first completes → verify button disabled.
9. Run test 3 times in a row → verify RateCounter NOT incremented (check via API: `GET /v1/llm-config`).
10. Verify per-run table TPS tooltip text updated.

### 9.4 Coverage Target

90% line coverage on new code (`llm_config.py` route, `schemas/llm.py`, `useTestPrompt.ts`, `SystemMetrics.tsx` changes).

## 10. Follow-Ups (Out of Scope)

1. **Fix per-run TPS formula** in `useLLMStats.ts` to exclude tool execution time. Requires backend to emit separate `llm_duration_s` vs `total_duration_s` in `enrichment_complete` event. Tracked separately.
2. **Persist test history** across browser sessions (localStorage with TTL).
3. **Multi-prompt load test mode** (N prompts → avg TPS + p50/p95 latency). Would benefit from a separate `TestRateCounter`.
4. **Cost estimate per test** (tokens × $/1k by model).
5. **Streaming cancellation of provider call** — currently the `asyncio.to_thread` wrapper for the Anthropic SDK call cannot be cancelled mid-flight. Acceptable for short test prompts. Documented in §5.7.
6. **CORS** — Vite dev server proxy covers cross-origin in dev (`vite.config.ts:10` confirms `proxyTarget` exists). Production deployment serves UI and API from same origin. If split origins in prod, add `CORSMiddleware` (not required for this feature).

## 11. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| SSE over POST breaks behind reverse proxy | Med | Document `X-Accel-Buffering: no` and `proxy_buffering off` for nginx. Test in prod-like env before release. |
| Provider stream rate varies run-to-run | High | Show `ttftMs`, `totalMs`, `tps` separately so user can interpret variance. Document in spec. |
| Free-text model input → user pastes invalid model | Med | Client-side regex pre-validate before sending. Server re-validates. |
| `MINIMAX_API_KEY` override via env is process-global | High (pre-existing) | Known issue. Not introduced by this feature. Documented in §10. |
| AbortController doesn't cancel provider call server-side | Med | Generator exits; thread continues. Acceptable for short test prompts (<15s). |
| Hook re-renders too often on chunk deltas | Low | React batches setState within event handlers; SSE events arrive faster than React re-render cycle in practice. Add `requestAnimationFrame` throttling if observed. |
| Anthropic SDK does not return usage in `message_stop` for all models | Med | Fall back to `len(delta) / 4` estimate. Log discrepancy. |
| Pydantic v2 `Annotated[str, AfterValidator]` syntax differs from v1 | Low | Project uses pydantic v2 per CLAUDE.md. Verify `pydantic.__version__` ≥ 2.0 in CI. |

## 12. Rollout

| Phase | Scope | PR | Env Flag |
|---|---|---|---|
| 1 | Backend: `ModelName` schema + `TestPromptRequest` + unit tests | 1 | none (additive) |
| 2 | Backend: `messages_stream()` on `EnrichmentLLMClient` + `POST /test-prompt` route + SSE unit tests | 2 | none |
| 3 | Frontend: `useTestPrompt` hook + `llmConfigAPI.testPrompt()` + unit tests | 3 | none |
| 4 | Frontend: `ResultCard` + `SystemMetrics.tsx` UI swap + SCSS + Playwright smoke | 4 | `ENABLE_TEST_PROMPT` |
| 5 | Frontend: shared `modelName.ts` schema + free-text model input | 5 | none (UI only) |

Each PR gated by `make quick-check` (1-2 min) for typical changes; `make full-check` for phases touching Docker/infrastructure.

**Default flag state:** ON in dev, OFF in prod for first 24h post-deploy, then ON in prod via config push.

**Rollback:** set `ENABLE_TEST_PROMPT=0` env in prod; previous "Test Connection" button restored from a feature-gated branch in `SystemMetrics.tsx`.

## 13. Open Questions

None blocking. All design decisions resolved per grill-me pass (2026-06-01).
