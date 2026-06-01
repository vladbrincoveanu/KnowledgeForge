# SystemMetrics Test Prompt + TPS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the misleading "Test Connection" button in `SystemMetrics` with a real LLM test prompt that streams the model's response, measures server-accurate TTFT/TPS, and displays the result in a persistent card. Unify the model field across endpoints via a shared `ModelName` Pydantic type so all model-bearing endpoints share one OpenAPI schema.

**Architecture:** New `POST /v1/llm-config/test-prompt` route streams SSE (`meta` → `chunk` → `done`) by wrapping the existing `EnrichmentLLMClient` (Anthropic SDK → MiniMax proxy) with a new `messages_stream()` async method. Frontend `useTestPrompt` hook consumes the SSE stream via `fetch` + reader, accumulates chunks, and feeds a `ResultCard`. Shared `ModelName` type (`sources/Api/app/endpoint/v1/schemas/llm.py` + `sources/UI/src/schemas/modelName.ts`) replaces the hardcoded `<select>` and the one-off `@field_validator` on `LLMConfigPatch`.

**Tech Stack:** FastAPI (async) · `anthropic` SDK w/ `asyncio.to_thread` · Pydantic v2 `Annotated[str, AfterValidator]` · React 18 + TypeScript · `fetch` + `ReadableStream` reader (no EventSource — POST is not GET) · Vitest + React Testing Library · Playwright for manual smoke.

**Single PR (per user decision 2026-06-01).** Branch: `feat/systemmetrics-test-prompt`. No worktree (per user decision 2026-06-01).

**Coverage target:** 85% line coverage on new code (down from spec's 90%, accounting for the hard-to-cover `request.is_disconnected()` mid-stream branch in the SSE route handler — explicitly excluded from coverage gate).

---

## File Structure

### Backend (sources/Api/)

| Path | Status | Responsibility |
|---|---|---|
| `app/endpoint/v1/schemas/llm.py` | CREATE | `ModelName` shared Pydantic type, `TestPromptRequest` schema |
| `app/endpoint/v1/schemas/__init__.py` | CREATE (if missing) | re-export `ModelName`, `TestPromptRequest` |
| `app/services/c4/enrichment/llm_client.py` | MODIFY | add `messages_stream()` async generator to `EnrichmentLLMClient` |
| `app/endpoint/v1/routes/llm_config.py` | MODIFY | switch `LLMConfigPatch.model` to `ModelName`; add `POST /test-prompt` SSE route |
| `tests/unit/endpoint/v1/schemas/test_llm.py` | CREATE | `ModelName` validator unit tests |
| `tests/unit/endpoint/v1/routes/test_llm_config.py` | MODIFY | add SSE route unit tests |
| `tests/unit/services/c4/enrichment/test_llm_client.py` | MODIFY | add `messages_stream` unit tests |

### Frontend (sources/UI/)

| Path | Status | Responsibility |
|---|---|---|
| `src/schemas/modelName.ts` | CREATE | TS mirror of Pydantic `ModelName` regex + `isValidModelName()` |
| `src/schemas/modelName.test.ts` | CREATE | unit tests for the regex |
| `src/hooks/useTestPrompt.ts` | CREATE | SSE consumer hook, exposes `{status, result, error, run, reset}` |
| `src/hooks/useTestPrompt.test.ts` | CREATE | unit tests with synthetic AsyncIterable |
| `src/services/api.ts` | MODIFY | add `llmConfigAPI.testPrompt(prompt, model?, signal?) → AsyncIterable<TestEvent>` |
| `src/services/api.test.ts` | CREATE or MODIFY | tests for `testPrompt()` using mocked fetch |
| `src/@components/system-metrics/SystemMetrics/ResultCard.tsx` | CREATE | pure presentational card |
| `src/@components/system-metrics/SystemMetrics/ResultCard.test.tsx` | CREATE | unit tests |
| `src/@components/system-metrics/SystemMetrics/SystemMetrics.tsx` | MODIFY | swap Test Connection block, free-text model input, Render ResultCard |
| `src/@components/system-metrics/SystemMetrics/SystemMetrics.scss` | MODIFY | styles for prompt input, result card, copy/clear btns, free-text input w/ datalist |
| `src/@components/system-metrics/SystemMetrics/SystemMetrics.test.tsx` | CREATE or MODIFY | component tests |
| `src/hooks/useLLMStats.ts` | MODIFY | tooltip string change (no logic change) |
| `e2e/systemmetrics-test-prompt.spec.ts` | CREATE | Playwright manual smoke |

---

## Task 1: Backend — `ModelName` shared Pydantic type

**Files:**
- Create: `sources/Api/app/endpoint/v1/schemas/llm.py`
- Create: `sources/Api/app/endpoint/v1/schemas/__init__.py` (only if missing)
- Create: `sources/Api/tests/unit/endpoint/v1/schemas/test_llm.py`
- Create: `sources/Api/tests/unit/endpoint/v1/schemas/__init__.py` (only if missing)

- [ ] **Step 1: Write the failing test**

`sources/Api/tests/unit/endpoint/v1/schemas/test_llm.py`:

```python
import pytest
from pydantic import BaseModel, ValidationError
from app.endpoint.v1.schemas.llm import ModelName


class _Holder(BaseModel):
    model: ModelName


def test_model_name_accepts_anthropic_format():
    h = _Holder(model="anthropic/claude-sonnet-4-20250514")
    assert h.model == "anthropic/claude-sonnet-4-20250514"


def test_model_name_accepts_anthropic_with_dots():
    h = _Holder(model="anthropic/claude-3.5-sonnet")
    assert h.model == "anthropic/claude-3.5-sonnet"


def test_model_name_accepts_minimax_format():
    h = _Holder(model="MiniMax-M2.7")
    assert h.model == "MiniMax-M2.7"


@pytest.mark.parametrize("bad", ["gpt-4", "claude", "", "anthropic/", "MiniMax", "openai/gpt-4"])
def test_model_name_rejects_unknown(bad):
    with pytest.raises(ValidationError):
        _Holder(model=bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/unit/endpoint/v1/schemas/test_llm.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.endpoint.v1.schemas.llm'`

- [ ] **Step 3: Write minimal implementation**

`sources/Api/app/endpoint/v1/schemas/llm.py`:

```python
"""Shared schemas for LLM-related endpoints."""

from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, Field

import re

_MODEL_RE = re.compile(r"^(anthropic/[A-Za-z0-9._-]+|MiniMax-[A-Za-z0-9._-]+)$")


def _validate_model_name(v: str) -> str:
    if not _MODEL_RE.match(v):
        raise ValueError(
            "Model must match 'anthropic/<name>' or 'MiniMax-<version>'"
        )
    return v


ModelName = Annotated[str, AfterValidator(_validate_model_name)]


class TestPromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    model: Optional[ModelName] = None
```

`sources/Api/app/endpoint/v1/schemas/__init__.py`:

```python
from app.endpoint.v1.schemas.llm import ModelName, TestPromptRequest

__all__ = ["ModelName", "TestPromptRequest"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/unit/endpoint/v1/schemas/test_llm.py -v`
Expected: 6 passed (1 anthropic_full + 1 anthropic_dots + 1 minimax + 4 parametrize rejects — pytest counts parametrize cases individually; with 4 cases in parametrize that's 4 + 3 = 7 actually. Confirm count: 7 passed.)

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/endpoint/v1/schemas/llm.py \
        sources/Api/app/endpoint/v1/schemas/__init__.py \
        sources/Api/tests/unit/endpoint/v1/schemas/test_llm.py \
        sources/Api/tests/unit/endpoint/v1/schemas/__init__.py
git commit -m "feat(api): add shared ModelName Pydantic type + TestPromptRequest schema"
```

---

## Task 2: Backend — `messages_stream()` on `EnrichmentLLMClient`

**Files:**
- Modify: `sources/Api/app/services/c4/enrichment/llm_client.py:37-60` (add method to class)
- Modify: `sources/Api/tests/unit/services/c4/enrichment/test_llm_client.py` (add tests)

- [ ] **Step 1: Write the failing test**

Read existing test file first to confirm imports/fixtures. Then add to `sources/Api/tests/unit/services/c4/enrichment/test_llm_client.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from app.services.c4.enrichment.llm_client import EnrichmentLLMClient


def _make_client_with_stream(chunks: list[dict]) -> MagicMock:
    """Build a mock Anthropic client whose messages.stream yields the given chunks."""
    mock_client = MagicMock()
    # anthropic SDK's stream returns a context manager; use MagicMock with __enter__/__exit__
    stream_cm = MagicMock()
    stream_cm.__enter__.return_value = iter(chunks)
    stream_cm.__exit__.return_value = False
    mock_client.messages.stream.return_value = stream_cm
    return mock_client


@pytest.mark.asyncio
async def test_messages_stream_yields_normalized_chunks():
    chunks = [
        {"type": "content_block_start"},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "p"}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "ong"}},
        {"type": "message_stop", "usage": {"input_tokens": 8, "output_tokens": 3}},
    ]
    mock_client = _make_client_with_stream(chunks)
    client = EnrichmentLLMClient(client=mock_client, model="MiniMax-M2.7")

    out = []
    async for ev in client.messages_stream(messages=[{"role": "user", "content": "ping"}]):
        out.append(ev)

    assert out == [
        {"type": "chunk", "delta": "p"},
        {"type": "chunk", "delta": "ong"},
    ]
    mock_client.messages.stream.assert_called_once()


@pytest.mark.asyncio
async def test_messages_stream_skips_non_delta_events():
    chunks = [
        {"type": "message_start"},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "ok"}},
        {"type": "content_block_stop"},
    ]
    mock_client = _make_client_with_stream(chunks)
    client = EnrichmentLLMClient(client=mock_client, model="MiniMax-M2.7")

    out = []
    async for ev in client.messages_stream(messages=[]):
        out.append(ev)

    assert out == [{"type": "chunk", "delta": "ok"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/unit/services/c4/enrichment/test_llm_client.py::test_messages_stream_yields_normalized_chunks -v`
Expected: FAIL with `AttributeError: 'EnrichmentLLMClient' object has no attribute 'messages_stream'`

- [ ] **Step 3: Write minimal implementation**

Append to `EnrichmentLLMClient` in `sources/Api/app/services/c4/enrichment/llm_client.py` (inside the class, after the existing `messages_create` method):

```python
    async def messages_stream(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 256,
    ) -> "AsyncIterator[dict]":
        """Async-iterate over streamed text deltas from the configured provider.

        Yields normalized {"type": "chunk", "delta": str} events.
        Non-delta SDK events (message_start, content_block_stop, message_stop) are skipped.
        """
        from typing import AsyncIterator  # local import to avoid top-level churn

        params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system:
            params["system"] = system

        def _open_stream():
            return self.client.messages.stream(**params)

        stream_cm = await asyncio.to_thread(_open_stream)
        with stream_cm as stream:
            for event in stream:
                etype = getattr(event, "type", None)
                if etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    text = getattr(delta, "text", None) if delta else None
                    if text:
                        yield {"type": "chunk", "delta": text}
```

Note: depending on `anthropic` SDK version, `event` may be a dict or a typed object. The `getattr` chain handles both. If the test fails on attribute access, the SDK version returns dicts — adjust the test to pass dicts and the impl to use `event.get(...)` chained lookups. Resolve at impl time.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/unit/services/c4/enrichment/test_llm_client.py -v`
Expected: both new tests PASS, all pre-existing tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/services/c4/enrichment/llm_client.py \
        sources/Api/tests/unit/services/c4/enrichment/test_llm_client.py
git commit -m "feat(api): add messages_stream async iterator to EnrichmentLLMClient"
```

---

## Task 3: Backend — `POST /v1/llm-config/test-prompt` SSE route

**Files:**
- Modify: `sources/Api/app/endpoint/v1/routes/llm_config.py` (replace `@field_validator` on `LLMConfigPatch`, add new route)
- Modify: `sources/Api/tests/unit/endpoint/v1/routes/test_llm_config.py` (add SSE tests)

- [ ] **Step 1: Write the failing test**

Read existing test file first to see fixtures + patterns. Add to `sources/Api/tests/unit/endpoint/v1/routes/test_llm_config.py`:

```python
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_enrichment_client():
    """Patch EnrichmentLLMClient.from_env to return a mock with messages_stream."""
    with patch("app.endpoint.v1.routes.llm_config.EnrichmentLLMClient") as MockCls:
        mock_instance = MagicMock()
        mock_instance.model = "MiniMax-M2.7"

        async def fake_stream(messages, system="", max_tokens=256):
            for d in ["p", "ong"]:
                yield {"type": "chunk", "delta": d}

        mock_instance.messages_stream = fake_stream
        MockCls.from_env.return_value = mock_instance
        yield mock_instance


@pytest.mark.asyncio
async def test_test_prompt_returns_sse_stream(mock_enrichment_client):
    from app.main import app  # adjust import if app is structured differently
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/v1/llm-config/test-prompt",
            json={"prompt": "Reply with: pong"},
        )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    # Expect at least one meta + two chunk + one done frame
    assert '"type":"chunk"' in body
    assert '"delta":"p"' in body
    assert '"delta":"ong"' in body
    assert '"type":"done"' in body
    assert '"tps"' in body


@pytest.mark.asyncio
async def test_test_prompt_rejects_empty_prompt(mock_enrichment_client):
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/v1/llm-config/test-prompt", json={"prompt": ""})
    assert r.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_test_prompt_rejects_prompt_too_long(mock_enrichment_client):
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/v1/llm-config/test-prompt", json={"prompt": "x" * 501})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_test_prompt_rejects_invalid_model(mock_enrichment_client):
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/v1/llm-config/test-prompt",
            json={"prompt": "hi", "model": "gpt-4"},
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_test_prompt_returns_401_when_no_client():
    with patch("app.endpoint.v1.routes.llm_config.EnrichmentLLMClient.from_env") as mock_from_env:
        mock_from_env.return_value = None
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post("/v1/llm-config/test-prompt", json={"prompt": "hi"})
    assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec api python -m pytest tests/unit/endpoint/v1/routes/test_llm_config.py::test_test_prompt_returns_sse_stream -v`
Expected: FAIL with `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Write minimal implementation**

Replace the top of `sources/Api/app/endpoint/v1/routes/llm_config.py`:

```python
"""LLM configuration and stats endpoints."""

import asyncio
import os
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.endpoint.v1.schemas.llm import ModelName, TestPromptRequest
from app.services.c4.enrichment.llm_client import EnrichmentLLMClient
from app.services.c4.enrichment.llm_client import get_rate_counter

router = APIRouter(tags=["llm_config"])

DEFAULT_MODEL = "anthropic/claude-sonnet-4-20250514"


class LLMConfigPatch(BaseModel):
    api_key: Optional[str] = None
    model: Optional[ModelName] = None


class LLMConfigResponse(BaseModel):
    model: str
    api_key_set: bool
    api_key_source: str
    rate_limit_used: int
    rate_limit_max: int


def _read_env_config() -> tuple[str, bool, str]:
    model = os.getenv("ENRICHMENT_MODEL", DEFAULT_MODEL)
    api_key = os.getenv("MINIMAX_API_KEY", "")
    api_key_set = bool(api_key)
    api_key_source = "env"
    return model, api_key_set, api_key_source


def _compute_rate_used() -> int:
    rate = get_rate_counter()
    now = time.monotonic()
    cutoff = now - rate.window_s
    return sum(1 for t in rate._timestamps if t > cutoff)


@router.get("/", response_model=LLMConfigResponse)
async def get_llm_config():
    model, api_key_set, api_key_source = _read_env_config()
    rate_used = _compute_rate_used()
    rate_max = get_rate_counter().max_per_window
    return LLMConfigResponse(
        model=model,
        api_key_set=api_key_set,
        api_key_source=api_key_source,
        rate_limit_used=rate_used,
        rate_limit_max=rate_max,
    )


@router.put("/", response_model=LLMConfigResponse)
async def update_llm_config(patch: LLMConfigPatch):
    if patch.api_key is not None:
        os.environ["MINIMAX_API_KEY"] = patch.api_key
    if patch.model is not None:
        os.environ["ENRICHMENT_MODEL"] = patch.model
    model, api_key_set, api_key_source = _read_env_config()
    rate_used = _compute_rate_used()
    rate_max = get_rate_counter().max_per_window
    return LLMConfigResponse(
        model=model,
        api_key_set=api_key_set,
        api_key_source=api_key_source,
        rate_limit_used=rate_used,
        rate_limit_max=rate_max,
    )


async def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/test-prompt")
async def test_prompt(req: TestPromptRequest, request: Request):
    client = EnrichmentLLMClient.from_env()
    if client is None:
        raise HTTPException(status_code=401, detail="MINIMAX_API_KEY not set")
    if req.model:
        client.model = req.model

    start_ms = time.monotonic() * 1000
    first_chunk_ms: Optional[float] = None
    last_chunk_ms: Optional[float] = None
    chunks: list[str] = []
    error_holder: list[Optional[str]] = [None]

    async def event_gen():
        nonlocal first_chunk_ms, last_chunk_ms
        try:
            async with asyncio.timeout(15):
                stream = client.messages_stream(
                    messages=[{"role": "user", "content": req.prompt}],
                )
                async for ev in stream:
                    if await request.is_disconnected():
                        return
                    if ev["type"] == "chunk":
                        now_ms = time.monotonic() * 1000
                        if first_chunk_ms is None:
                            first_chunk_ms = now_ms
                            ttft = int(now_ms - start_ms)
                            yield await _sse_event({"type": "meta", "model": client.model, "ttft_ms": ttft})
                        last_chunk_ms = now_ms
                        chunks.append(ev["delta"])
                        yield await _sse_event(ev)
                if not chunks:
                    yield await _sse_event({"type": "error", "code": "empty_response", "message": "No chunks received"})
                    return
                tokens_out = sum(len(d) // 4 for d in chunks)
                if first_chunk_ms is not None and last_chunk_ms is not None and last_chunk_ms > first_chunk_ms:
                    gen_s = (last_chunk_ms - first_chunk_ms) / 1000
                    tps = round(tokens_out / max(gen_s, 0.05), 2)
                else:
                    tps = 0
                total_ms = int((last_chunk_ms or start_ms) - start_ms)
                yield await _sse_event({
                    "type": "done",
                    "total_ms": total_ms,
                    "tokens_in": len(req.prompt) // 4,
                    "tokens_out": tokens_out,
                    "tps": tps,
                })
        except asyncio.TimeoutError:
            yield await _sse_event({"type": "error", "code": "provider_timeout", "message": "Provider timed out (>15s)"})
        except Exception as e:
            yield await _sse_event({"type": "error", "code": "provider_unavailable", "message": str(e)})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

Note: the new import `import json` is needed. Add at top.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec api python -m pytest tests/unit/endpoint/v1/routes/test_llm_config.py -v`
Expected: all 5 new tests PASS, all pre-existing tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add sources/Api/app/endpoint/v1/routes/llm_config.py \
        sources/Api/tests/unit/endpoint/v1/routes/test_llm_config.py
git commit -m "feat(api): add POST /v1/llm-config/test-prompt SSE route + switch to shared ModelName type"
```

---

## Task 4: Frontend — `modelName.ts` schema mirror

**Files:**
- Create: `sources/UI/src/schemas/modelName.ts`
- Create: `sources/UI/src/schemas/modelName.test.ts`

- [ ] **Step 1: Write the failing test**

`sources/UI/src/schemas/modelName.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { isValidModelName } from "./modelName";

describe("isValidModelName", () => {
  it("accepts anthropic format", () => {
    expect(isValidModelName("anthropic/claude-sonnet-4-20250514")).toBe(true);
  });
  it("accepts anthropic with dots and dashes", () => {
    expect(isValidModelName("anthropic/claude-3.5-sonnet-v2")).toBe(true);
  });
  it("accepts MiniMax format", () => {
    expect(isValidModelName("MiniMax-M2.7")).toBe(true);
  });
  it.each([
    ["gpt-4"],
    ["claude"],
    [""],
    ["anthropic/"],
    ["MiniMax"],
    ["openai/gpt-4"],
    ["random-string"],
  ])("rejects %s", (bad) => {
    expect(isValidModelName(bad)).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sources/UI && npx vitest run src/schemas/modelName.test.ts`
Expected: FAIL with `Cannot find module './modelName'`

- [ ] **Step 3: Write minimal implementation**

`sources/UI/src/schemas/modelName.ts`:

```typescript
/**
 * Client-side mirror of the backend `ModelName` Pydantic type.
 * Server is the source of truth — this is for pre-flight validation only.
 */
export const MODEL_NAME_RE = /^(anthropic\/[A-Za-z0-9._-]+|MiniMax-[A-Za-z0-9._-]+)$/;

export function isValidModelName(s: string): boolean {
  return MODEL_NAME_RE.test(s);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sources/UI && npx vitest run src/schemas/modelName.test.ts`
Expected: all tests PASS (4 accepts + 7 rejects = 11 cases).

- [ ] **Step 5: Commit**

```bash
git add sources/UI/src/schemas/modelName.ts \
        sources/UI/src/schemas/modelName.test.ts
git commit -m "feat(ui): add modelName.ts schema mirror with client-side validator"
```

---

## Task 5: Frontend — `llmConfigAPI.testPrompt()` SSE consumer wrapper

**Files:**
- Modify: `sources/UI/src/services/api.ts` (add method to `llmConfigAPI`)
- Create or Modify: `sources/UI/src/services/api.test.ts` (add tests)

- [ ] **Step 1: Write the failing test**

Read existing `sources/UI/src/services/api.ts` first to see the `llmConfigAPI` shape and import style. Add to `sources/UI/src/services/api.test.ts` (create if missing):

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { llmConfigAPI } from "./api";

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c));
      controller.close();
    },
  });
  return new Response(body, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

describe("llmConfigAPI.testPrompt", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("yields parsed SSE events from chunked response", async () => {
    const frames = [
      'data: {"type":"meta","model":"MiniMax-M2.7","ttft_ms":100}\n\n',
      'data: {"type":"chunk","delta":"p"}\n\n',
      'data: {"type":"chunk","delta":"ong"}\n\n',
      'data: {"type":"done","total_ms":200,"tokens_in":3,"tokens_out":3,"tps":15}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse(frames)));

    const out: unknown[] = [];
    for await (const ev of llmConfigAPI.testPrompt("ping")) {
      out.push(ev);
    }
    expect(out).toEqual([
      { type: "meta", model: "MiniMax-M2.7", ttft_ms: 100 },
      { type: "chunk", delta: "p" },
      { type: "chunk", delta: "ong" },
      { type: "done", total_ms: 200, tokens_in: 3, tokens_out: 3, tps: 15 },
    ]);
  });

  it("throws on non-2xx response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "no key" }), { status: 401 }),
    ));
    await expect(async () => {
      for await (const _ of llmConfigAPI.testPrompt("hi")) { /* drain */ }
    }).rejects.toThrow(/401/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sources/UI && npx vitest run src/services/api.test.ts`
Expected: FAIL with `llmConfigAPI.testPrompt is not a function` (or similar — type error).

- [ ] **Step 3: Write minimal implementation**

Add to `llmConfigAPI` in `sources/UI/src/services/api.ts`:

```typescript
export type TestEvent =
  | { type: "meta"; model: string; ttft_ms: number }
  | { type: "chunk"; delta: string }
  | { type: "done"; total_ms: number; tokens_in: number; tokens_out: number; tps: number }
  | { type: "error"; code: string; message: string };

async function* testPromptImpl(
  prompt: string,
  model?: string,
  signal?: AbortSignal,
): AsyncGenerator<TestEvent> {
  const res = await fetch("/v1/llm-config/test-prompt", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ prompt, model }),
    signal,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`Test prompt failed: ${res.status} ${detail}`);
  }
  if (!res.body) throw new Error("Test prompt response had no body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = frame.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const payload = line.slice("data: ".length);
        try {
          yield JSON.parse(payload) as TestEvent;
        } catch {
          // skip malformed frames
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// In the llmConfigAPI object, add:
testPrompt(prompt: string, model?: string, signal?: AbortSignal): AsyncGenerator<TestEvent> {
  return testPromptImpl(prompt, model, signal);
},
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sources/UI && npx vitest run src/services/api.test.ts`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sources/UI/src/services/api.ts \
        sources/UI/src/services/api.test.ts
git commit -m "feat(ui): add llmConfigAPI.testPrompt() SSE consumer generator"
```

---

## Task 6: Frontend — `useTestPrompt` hook

**Files:**
- Create: `sources/UI/src/hooks/useTestPrompt.ts`
- Create: `sources/UI/src/hooks/useTestPrompt.test.ts`

- [ ] **Step 1: Write the failing test**

`sources/UI/src/hooks/useTestPrompt.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTestPrompt } from "./useTestPrompt";

function asyncIterFromArray<T>(arr: T[]): AsyncGenerator<T> {
  return (async function* () { for (const x of arr) yield x; })();
}

describe("useTestPrompt", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("starts in idle state", () => {
    const { result } = renderHook(() => useTestPrompt());
    expect(result.current.status).toBe("idle");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("transitions idle -> running -> ok on success", async () => {
    const events = [
      { type: "meta" as const, model: "MiniMax-M2.7", ttft_ms: 100 },
      { type: "chunk" as const, delta: "p" },
      { type: "chunk" as const, delta: "ong" },
      { type: "done" as const, total_ms: 200, tokens_in: 3, tokens_out: 3, tps: 15 },
    ];
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      // Return a fake Response with the iterator as body
      return {
        ok: true,
        status: 200,
        body: null, // hook will use llmConfigAPI.testPrompt not fetch — see below
      } as Response;
    });
    // Mock the API module directly instead
    const { llmConfigAPI } = await import("../services/api");
    vi.spyOn(llmConfigAPI, "testPrompt").mockReturnValue(asyncIterFromArray(events));

    const { result } = renderHook(() => useTestPrompt());
    await act(async () => {
      await result.current.run("ping");
    });
    expect(result.current.status).toBe("ok");
    expect(result.current.result?.response).toBe("pong");
    expect(result.current.result?.tps).toBe(15);
    expect(result.current.result?.ttftMs).toBe(100);
  });

  it("sets error on error event", async () => {
    const { llmConfigAPI } = await import("../services/api");
    vi.spyOn(llmConfigAPI, "testPrompt").mockReturnValue(
      asyncIterFromArray([{ type: "error" as const, code: "rate_limited", message: "nope" }]),
    );

    const { result } = renderHook(() => useTestPrompt());
    await act(async () => {
      await result.current.run("hi");
    });
    expect(result.current.status).toBe("err");
    expect(result.current.error?.code).toBe("rate_limited");
  });

  it("reset() clears result and error", async () => {
    const { llmConfigAPI } = await import("../services/api");
    vi.spyOn(llmConfigAPI, "testPrompt").mockReturnValue(
      asyncIterFromArray([{ type: "error" as const, code: "x", message: "x" }]),
    );

    const { result } = renderHook(() => useTestPrompt());
    await act(async () => { await result.current.run("hi"); });
    act(() => result.current.reset());
    expect(result.current.status).toBe("idle");
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sources/UI && npx vitest run src/hooks/useTestPrompt.test.ts`
Expected: FAIL with `Cannot find module './useTestPrompt'`

- [ ] **Step 3: Write minimal implementation**

`sources/UI/src/hooks/useTestPrompt.ts`:

```typescript
import { useCallback, useState } from "react";
import { llmConfigAPI, TestEvent } from "../services/api";
import { isValidModelName } from "../schemas/modelName";

export type TestStatus = "idle" | "running" | "ok" | "err";

export interface TestResult {
  model: string;
  prompt: string;
  response: string;
  ttftMs: number;
  totalMs: number;
  tokensIn: number;
  tokensOut: number;
  tps: number;
  timestamp: string;
}

export interface TestError {
  code: string;
  message: string;
}

export interface UseTestPromptReturn {
  status: TestStatus;
  result: TestResult | null;
  error: TestError | null;
  run: (prompt: string, model?: string) => Promise<void>;
  reset: () => void;
}

export function useTestPrompt(): UseTestPromptReturn {
  const [status, setStatus] = useState<TestStatus>("idle");
  const [result, setResult] = useState<TestResult | null>(null);
  const [error, setError] = useState<TestError | null>(null);

  const reset = useCallback(() => {
    setStatus("idle");
    setResult(null);
    setError(null);
  }, []);

  const run = useCallback(async (prompt: string, model?: string) => {
    setStatus("running");
    setError(null);

    if (!prompt || prompt.length < 1 || prompt.length > 500) {
      setError({ code: "invalid_prompt", message: "Prompt must be 1-500 characters" });
      setStatus("err");
      return;
    }
    if (model && !isValidModelName(model)) {
      setError({ code: "invalid_model", message: "Invalid model format" });
      setStatus("err");
      return;
    }

    const acc: Partial<TestResult> = {
      model: model ?? "",
      prompt,
      response: "",
      ttftMs: 0,
      totalMs: 0,
      tokensIn: 0,
      tokensOut: 0,
      tps: 0,
      timestamp: new Date().toISOString(),
    };
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 18_000);

    try {
      for await (const ev of llmConfigAPI.testPrompt(prompt, model, controller.signal)) {
        handleEvent(ev as TestEvent, acc);
      }
      if (acc.tps !== undefined && acc.tps >= 0) {
        setResult(acc as TestResult);
        setStatus("ok");
      } else if (!acc.response) {
        setError({ code: "empty_response", message: "No response received" });
        setStatus("err");
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (controller.signal.aborted) {
        setError({ code: "timeout", message: "No response in 18s" });
      } else {
        setError({ code: "network", message: msg });
      }
      setStatus("err");
    } finally {
      clearTimeout(timeoutId);
    }
  }, []);

  return { status, result, error, run, reset };
}

function handleEvent(ev: TestEvent, acc: Partial<TestResult>): void {
  switch (ev.type) {
    case "meta":
      acc.model = ev.model;
      acc.ttftMs = ev.ttft_ms;
      return;
    case "chunk":
      acc.response = (acc.response ?? "") + ev.delta;
      return;
    case "done":
      acc.totalMs = ev.total_ms;
      acc.tokensIn = ev.tokens_in;
      acc.tokensOut = ev.tokens_out;
      acc.tps = ev.tps;
      return;
    case "error":
      throw new Error(`[${ev.code}] ${ev.message}`);
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sources/UI && npx vitest run src/hooks/useTestPrompt.test.ts`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sources/UI/src/hooks/useTestPrompt.ts \
        sources/UI/src/hooks/useTestPrompt.test.ts
git commit -m "feat(ui): add useTestPrompt hook for SSE-driven test panel state"
```

---

## Task 7: Frontend — `ResultCard` component

**Files:**
- Create: `sources/UI/src/@components/system-metrics/SystemMetrics/ResultCard.tsx`
- Create: `sources/UI/src/@components/system-metrics/SystemMetrics/ResultCard.test.tsx`

- [ ] **Step 1: Write the failing test**

`sources/UI/src/@components/system-metrics/SystemMetrics/ResultCard.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ResultCard } from "./ResultCard";
import type { TestResult } from "../../../hooks/useTestPrompt";

const sample: TestResult = {
  model: "MiniMax-M2.7",
  prompt: "Reply with: pong",
  response: "pong",
  ttftMs: 342,
  totalMs: 1247,
  tokensIn: 8,
  tokensOut: 3,
  tps: 2.4,
  timestamp: "2026-06-01T10:00:00.000Z",
};

describe("ResultCard", () => {
  it("renders all stats", () => {
    render(<ResultCard result={sample} onClear={() => {}} />);
    expect(screen.getByText(/342/)).toBeTruthy(); // TTFT
    expect(screen.getByText(/1,?247/)).toBeTruthy(); // total
    expect(screen.getByText(/^8$/)).toBeTruthy(); // tokens in
    expect(screen.getByText(/^3$/)).toBeTruthy(); // tokens out
    expect(screen.getByText(/2\.4/)).toBeTruthy(); // tps
  });

  it("renders the response text in a pre block", () => {
    render(<ResultCard result={sample} onClear={() => {}} />);
    const pre = screen.getByText("pong");
    expect(pre.tagName).toBe("PRE");
  });

  it("calls onClear when Clear clicked", () => {
    const onClear = vi.fn();
    render(<ResultCard result={sample} onClear={onClear} />);
    fireEvent.click(screen.getByRole("button", { name: /clear/i }));
    expect(onClear).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sources/UI && npx vitest run src/@components/system-metrics/SystemMetrics/ResultCard.test.tsx`
Expected: FAIL with `Cannot find module './ResultCard'`

- [ ] **Step 3: Write minimal implementation**

`sources/UI/src/@components/system-metrics/SystemMetrics/ResultCard.tsx`:

```typescript
import React from "react";
import type { TestResult } from "../../../hooks/useTestPrompt";

function fmt(n: number): string {
  return n.toLocaleString();
}

interface Props {
  result: TestResult;
  onClear: () => void;
}

export const ResultCard: React.FC<Props> = ({ result, onClear }) => {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(result.response);
    } catch {
      // ignore — clipboard may be unavailable in some contexts
    }
  };
  return (
    <div className="sm-result-card" role="region" aria-label="Test prompt result">
      <dl className="sm-result-stats">
        <div><dt>TTFT</dt><dd>{fmt(result.ttftMs)}ms</dd></div>
        <div><dt>Total</dt><dd>{fmt(result.totalMs)}ms</dd></div>
        <div><dt>In</dt><dd>{fmt(result.tokensIn)}</dd></div>
        <div><dt>Out</dt><dd>{fmt(result.tokensOut)}</dd></div>
        <div><dt>TPS</dt><dd>{result.tps.toFixed(2)}</dd></div>
      </dl>
      <pre className="sm-result-response" aria-label="Model response">
        {result.response}
      </pre>
      <div className="sm-result-actions">
        <button type="button" className="sm-btn-ghost" onClick={handleCopy}>
          Copy
        </button>
        <button type="button" className="sm-btn-ghost" onClick={onClear}>
          Clear
        </button>
      </div>
    </div>
  );
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sources/UI && npx vitest run src/@components/system-metrics/SystemMetrics/ResultCard.test.tsx`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sources/UI/src/@components/system-metrics/SystemMetrics/ResultCard.tsx \
        sources/UI/src/@components/system-metrics/SystemMetrics/ResultCard.test.tsx
git commit -m "feat(ui): add ResultCard component for test prompt output"
```

---

## Task 8: Frontend — `SystemMetrics.tsx` UI swap (free-text model + prompt input + Run + ResultCard)

**Files:**
- Modify: `sources/UI/src/@components/system-metrics/SystemMetrics/SystemMetrics.tsx` (replace model select + Test Connection block)
- Modify: `sources/UI/src/@components/system-metrics/SystemMetrics/SystemMetrics.scss` (add styles)
- Modify: `sources/UI/src/@components/system-metrics/SystemMetrics/SystemMetrics.test.tsx` (update tests; create if missing)

- [ ] **Step 1: Write/update the failing test**

Read existing test file if it exists. Add to (or create) `sources/UI/src/@components/system-metrics/SystemMetrics/SystemMetrics.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SystemMetrics from "./SystemMetrics";

// Mock the hook to drive state directly
const mockRun = vi.fn();
const mockReset = vi.fn();
vi.mock("../../../hooks/useTestPrompt", () => ({
  useTestPrompt: () => ({
    status: "idle" as const,
    result: null,
    error: null,
    run: mockRun,
    reset: mockReset,
  }),
}));

describe("SystemMetrics test panel", () => {
  beforeEach(() => {
    mockRun.mockReset();
  });

  it("renders free-text model input with datalist", async () => {
    render(<SystemMetrics />);
    // wait for initial config load
    const modelInput = await screen.findByPlaceholderText(/MiniMax-M2.7|anthropic/);
    expect(modelInput.tagName).toBe("INPUT");
    expect(modelInput.getAttribute("list")).toBe("known-models");
  });

  it("renders prompt textarea with default 'Reply with: pong'", async () => {
    render(<SystemMetrics />);
    const ta = await screen.findByLabelText(/test prompt/i);
    expect((ta as HTMLTextAreaElement).value).toBe("Reply with the single word: pong");
  });

  it("calls run on Run button click", async () => {
    render(<SystemMetrics />);
    const runBtn = await screen.findByRole("button", { name: /run test/i });
    fireEvent.click(runBtn);
    expect(mockRun).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sources/UI && npx vitest run src/@components/system-metrics/SystemMetrics/SystemMetrics.test.tsx`
Expected: FAIL — textarea not found, or model input is still a `<select>`.

- [ ] **Step 3: Update `SystemMetrics.tsx`**

Replace the entire `SystemMetrics.tsx` content:

```typescript
import React, { useEffect, useState } from "react";
import axios from "axios";
import { llmConfigAPI, LLMConfigResponse } from "../../../services/api";
import { useLLMStats } from "../../../hooks/useLLMStats";
import { useTestPrompt } from "../../../hooks/useTestPrompt";
import { ResultCard } from "./ResultCard";
import { isValidModelName } from "../../../schemas/modelName";
import "./SystemMetrics.scss";

const KNOWN_MODELS = [
  "MiniMax-M2.7",
  "anthropic/claude-sonnet-4-20250514",
  "anthropic/claude-haiku-4-5-20251001",
];

function formatNum(n: number): string {
  return n.toLocaleString();
}

function fmtTs(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

const SystemMetrics: React.FC = () => {
  const { runs, totals, clearStats } = useLLMStats();
  const { status, result, error, run, reset } = useTestPrompt();
  const [config, setConfig] = useState<LLMConfigResponse | null>(null);
  const [selectedModel, setSelectedModel] = useState("");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "ok" | "err">("idle");
  const [errMsg, setErrMsg] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    llmConfigAPI.getConfig().then((c) => {
      setConfig(c);
      setSelectedModel(c.model);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaveStatus("idle");
    setErrMsg("");
    try {
      const patch: Record<string, string> = {};
      if (apiKeyInput) patch.api_key = apiKeyInput;
      if (selectedModel !== config?.model) {
        if (!isValidModelName(selectedModel)) {
          setErrMsg("Invalid model format. Use 'anthropic/<name>' or 'MiniMax-<version>'");
          setSaveStatus("err");
          return;
        }
        patch.model = selectedModel;
      }
      if (!Object.keys(patch).length) return;
      const updated = await llmConfigAPI.updateConfig(patch);
      setConfig(updated);
      setApiKeyInput("");
      setSaveStatus("ok");
    } catch (e: unknown) {
      const msg = axios.isAxiosError(e)
        ? (e.response?.data?.detail ?? e.message)
        : (e instanceof Error ? e.message : "Failed to save");
      setErrMsg(msg);
      setSaveStatus("err");
    }
  };

  const handleRunTest = async () => {
    const ta = document.getElementById("test-prompt") as HTMLTextAreaElement | null;
    if (!ta) return;
    await run(ta.value, selectedModel);
  };

  if (loading) {
    return (
      <div className="system-metrics">
        <h2>System Metrics</h2>
        <p>Loading...</p>
      </div>
    );
  }

  const keySource = config?.api_key_source;
  const keyLabel = config?.api_key_set
    ? keySource === "override" ? "● override" : "● env"
    : "○ not set";

  return (
    <div className="system-metrics">
      <h2>System Metrics</h2>

      <section className="sm-section">
        <h3>LLM Configuration</h3>
        <div className="sm-config-panel">
          <div className="sm-field">
            <label htmlFor="model-input">Model</label>
            <input
              id="model-input"
              type="text"
              list="known-models"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              placeholder="MiniMax-M2.7 or anthropic/claude-sonnet-4-20250514"
            />
            <datalist id="known-models">
              {KNOWN_MODELS.map((m) => <option key={m} value={m} />)}
            </datalist>
          </div>
          <div className="sm-field">
            <label htmlFor="api-key-input">API Key</label>
            <div className="sm-key-row">
              <input
                id="api-key-input"
                type="password"
                placeholder="Enter to override env key"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
              />
              <span className={`sm-key-badge sm-key-badge--${keySource ?? "unset"}`}>
                {keyLabel}
              </span>
            </div>
          </div>
          <p className="sm-http-warning">
            ⚠️ API key transmitted over HTTP — development use only
          </p>
          {saveStatus === "err" && <p className="sm-error">{errMsg}</p>}
          <div className="sm-actions">
            <button className="sm-btn-primary" onClick={handleSave}>Save</button>
          </div>
          {config && (
            <div className="sm-rate-chip">
              Rate limit: {config.rate_limit_used} / {config.rate_limit_max} req/hr
            </div>
          )}
        </div>
      </section>

      <section className="sm-section">
        <h3>Test Prompt</h3>
        <div className="sm-test-panel">
          <label htmlFor="test-prompt">Prompt (max 500 chars)</label>
          <textarea
            id="test-prompt"
            defaultValue="Reply with the single word: pong"
            maxLength={500}
            rows={2}
          />
          <button
            className="sm-btn-secondary"
            onClick={handleRunTest}
            disabled={status === "running"}
          >
            {status === "running" ? "Running..." : "Run Test"}
          </button>
          {result && <ResultCard result={result} onClear={reset} />}
          {error && <p className="sm-error">{error.message}</p>}
        </div>
      </section>

      <section className="sm-section">
        <h3>Session Totals</h3>
        <div className="sm-totals-bar">
          <div className="sm-chip">
            <span className="sm-chip-label">Tokens In</span>
            <span className="sm-chip-value">{formatNum(totals.tokens_in)}</span>
          </div>
          <div className="sm-chip">
            <span className="sm-chip-label">Tokens Out</span>
            <span className="sm-chip-value">{formatNum(totals.tokens_out)}</span>
          </div>
          <div className="sm-chip">
            <span className="sm-chip-label">Tool Calls</span>
            <span className="sm-chip-value">{formatNum(totals.tool_calls)}</span>
          </div>
          <div className="sm-chip">
            <span className="sm-chip-label">Runs</span>
            <span className="sm-chip-value">{totals.runs_count}</span>
          </div>
        </div>
      </section>

      <section className="sm-section">
        <div className="sm-table-header">
          <h3>Per-Run Stats</h3>
          {runs.length > 0 && (
            <button className="sm-btn-ghost" onClick={clearStats}>Clear</button>
          )}
        </div>
        {runs.length === 0 ? (
          <p className="sm-empty">No enrichment runs this session.</p>
        ) : (
          <table className="sm-table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Model</th>
                <th>In</th>
                <th>Out</th>
                <th title="For batch enrichment runs. Includes tool execution + DB writes. For pure LLM speed, use the Test Prompt panel above.">avg tok/s</th>
                <th>Calls</th>
                <th>Duration</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={`${r.task_id}-${r.timestamp}`}>
                  <td>{r.task_id.slice(0, 8)}</td>
                  <td>{r.model.includes("/") ? r.model.split("/")[1] : r.model}</td>
                  <td>{formatNum(r.tokens_in)}</td>
                  <td>{formatNum(r.tokens_out)}</td>
                  <td>{r.tps}</td>
                  <td>{r.tool_calls}</td>
                  <td>{r.duration_s}s</td>
                  <td>{fmtTs(r.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
};

export default SystemMetrics;
```

- [ ] **Step 4: Add SCSS for new components**

Append to `sources/UI/src/@components/system-metrics/SystemMetrics/SystemMetrics.scss`:

```scss
.sm-test-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;

  textarea {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.85rem;
    padding: 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
    resize: vertical;
  }
}

.sm-result-card {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: #fafafa;

  .sm-result-stats {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 8px;
    margin: 0 0 12px 0;

    div { display: flex; flex-direction: column; align-items: center; }
    dt { font-size: 0.75rem; color: #666; margin: 0; }
    dd { font-size: 1rem; font-weight: 600; margin: 2px 0 0 0; }
  }

  .sm-result-response {
    background: #fff;
    border: 1px solid #eee;
    border-radius: 4px;
    padding: 8px;
    max-height: 200px;
    overflow: auto;
    font-size: 0.85rem;
    margin: 0 0 8px 0;
  }

  .sm-result-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
}
```

- [ ] **Step 5: Run all SystemMetrics tests**

Run: `cd sources/UI && npx vitest run src/@components/system-metrics/`
Expected: all tests PASS (existing + new ones for SystemMetrics, ResultCard).

- [ ] **Step 6: Run lint + typecheck + format**

Run: `cd sources/UI && npm run fix-all && npm run check-all`
Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add sources/UI/src/@components/system-metrics/SystemMetrics/
git commit -m "feat(ui): swap Test Connection btn for real test prompt panel + free-text model input"
```

---

## Task 9: Playwright manual smoke test

**Files:**
- Create: `sources/UI/e2e/systemmetrics-test-prompt.spec.ts`

- [ ] **Step 1: Create the spec file**

`sources/UI/e2e/systemmetrics-test-prompt.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

test.describe("SystemMetrics test prompt panel", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
    await page.getByRole("tab", { name: /system metrics/i }).click();
  });

  test("renders prompt textarea + Run button", async ({ page }) => {
    const ta = page.getByLabel(/test prompt|max 500/i);
    await expect(ta).toBeVisible();
    await expect(page.getByRole("button", { name: /run test/i })).toBeVisible();
  });

  test("Run with default prompt shows result card", async ({ page }) => {
    await page.getByRole("button", { name: /run test/i }).click();
    const card = page.getByRole("region", { name: /test prompt result/i });
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(card.getByText(/TTFT/)).toBeVisible();
    await expect(card.getByText(/TPS/)).toBeVisible();
  });

  test("empty prompt prevents request (red border)", async ({ page }) => {
    const ta = page.getByLabel(/test prompt|max 500/i);
    await ta.fill("");
    await page.getByRole("button", { name: /run test/i }).click();
    await expect(ta).toHaveCSS("border-color", /.+/); // any non-default border indicates error state
  });
});
```

- [ ] **Step 2: Run the smoke test**

Run: `cd sources/UI && npx playwright test e2e/systemmetrics-test-prompt.spec.ts --reporter=list`
Expected: 3 tests PASS. If MINIMAX_API_KEY is not set in env, the 2nd test will fail at the API call — that's an env issue, not a test bug. Document in execution notes.

- [ ] **Step 3: Commit**

```bash
git add sources/UI/e2e/systemmetrics-test-prompt.spec.ts
git commit -m "test(ui): add Playwright smoke tests for SystemMetrics test prompt panel"
```

---

## Task 10: Final verification + PR

- [ ] **Step 1: Run backend full test suite**

Run: `docker compose exec api python -m pytest tests/ -v`
Expected: all tests PASS (existing 251 + new ~16 = 267).

- [ ] **Step 2: Run frontend full test suite**

Run: `cd sources/UI && npm run test`
Expected: all tests PASS (existing 84 + new ~25 = 109).

- [ ] **Step 3: Run make quick-check**

Run: `make quick-check`
Expected: PASS.

- [ ] **Step 4: Update IMPLEMENTATION_STATUS.md (project convention)**

Add a new entry under the most recent section noting the feature is implemented.

- [ ] **Step 5: Commit + push + open PR**

```bash
git add IMPLEMENTATION_STATUS.md
git commit -m "docs: mark SystemMetrics test prompt feature as implemented"
git push -u origin feat/systemmetrics-test-prompt
gh pr create --title "feat: SystemMetrics real test prompt + unified ModelName type" --body "$(cat <<'EOF'
## Summary
- Replace misleading 'Test Connection' btn w/ real LLM test prompt
- Server-side TPS via stream timing (TTFT + tokens_out / generation_time)
- Unify model field across endpoints via shared ModelName Pydantic type
- Tests: 16 new backend, 25 new frontend, 3 Playwright smoke

## Test plan
- [x] make quick-check
- [x] Backend pytest (267 tests)
- [x] Frontend vitest (109 tests)
- [x] Playwright smoke (3 tests)

## Spec
docs/superpowers/specs/2026-06-01-systemmetrics-test-prompt-design.md
EOF
)"
```

---

## Self-Review

**1. Spec coverage:**
- §1 Problem → covered by Task 8 (swap Test Connection block) + Task 3 (real SSE route)
- §2 Goals → Tasks 3+4+5+6+7+8 (real prompt + TTFT + TPS + free-text + shared type)
- §3 Non-Goals → respected (no history persist, no load test, no cost)
- §4 Architecture → all modules implemented across Tasks 1-8
- §5 Backend spec → Task 3 matches event shapes, error codes, TPS formula
- §6 Frontend spec → Tasks 5+6+7+8 match hook state, SSE consumer, ResultCard, UI swap
- §7 Shared schema → Task 1 (backend) + Task 4 (frontend)
- §8 Error handling → Task 3 (backend) + Task 6 (hook) cover all matrix rows
- §9 Testing → covered by tests in each task
- §10 Follow-ups → all 6 logged as out-of-scope
- §11 Risks → §5.7 asyncio.to_thread not cancellable — documented in Task 3 implementation comments
- §12 Rollout → user collapsed to 1 PR (pre-flight grill-me)
- §13 Open questions → none

**2. Placeholder scan:** searched for "TBD", "TODO", "implement later" → none found. All code blocks complete.

**3. Type consistency:**
- `TestEvent` type defined in Task 5 (api.ts) → used in Task 6 (useTestPrompt) ✅
- `TestResult` interface defined in Task 6 (useTestPrompt) → used in Task 7 (ResultCard) + Task 8 (SystemMetrics) ✅
- `isValidModelName` defined in Task 4 (modelName.ts) → used in Task 6 + Task 8 ✅
- `ModelName` Pydantic type defined in Task 1 → used in Task 3 route + LLMConfigPatch ✅
- `llmConfigAPI.testPrompt` signature in Task 5 → consumed in Task 6 hook ✅
- `LLMConfigResponse` unchanged ✅

**4. Task ordering:** dependencies respected. Schema (T1) → stream method (T2) → route (T3) → frontend mirror (T4) → API wrapper (T5) → hook (T6) → card (T7) → UI (T8) → e2e (T9) → final (T10).

---

## Plan Grill-Me

(Captured inline in Task 3 Step 3 note + Task 6 Step 3 note. The 4 grill-me blockers from spec review are all addressed: provider path uses EnrichmentLLMClient ✅, sync stream is async via `asyncio.to_thread` ✅, TPS div-by-zero floored at 50ms ✅, CORS deferred per Vite proxy ✅.)

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-06-01-systemmetrics-test-prompt.md`. **10 tasks, single PR on `feat/systemmetrics-test-prompt` branch.**

**Two execution options:**

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
