"""LLM configuration and stats endpoints."""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.endpoint.v1.schemas.llm import ModelName, TestPromptRequest
from app.services.c4.enrichment.llm_client import EnrichmentLLMClient, get_rate_counter

router = APIRouter(tags=["llm_config"])

DEFAULT_MODEL = "MiniMax-M3"


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


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/test-prompt")
async def test_prompt(req: TestPromptRequest, request: Request):
    """Stream a real LLM test prompt back to the client as SSE.

    Emits ``meta`` (with ttft_ms) -> N ``chunk`` (delta text) -> ``done``
    (total_ms, tokens_in, tokens_out, tps). On error emits ``error`` frame
    with a code from spec §5.5. Disconnect is detected via
    ``request.is_disconnected()``; the generator exits cleanly when the
    client disconnects (the underlying ``asyncio.to_thread`` SDK call
    continues but its result is discarded -- acceptable for short test
    prompts per spec §5.7).
    """
    client = EnrichmentLLMClient.from_env()
    if client is None:
        raise HTTPException(status_code=401, detail="MINIMAX_API_KEY not set")
    if req.model:
        client.model = req.model

    start_ms = time.monotonic() * 1000
    first_chunk_ms: Optional[float] = None
    last_chunk_ms: Optional[float] = None
    chunks: list[str] = []

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
                    if ev.get("type") == "chunk":
                        now_ms = time.monotonic() * 1000
                        if first_chunk_ms is None:
                            first_chunk_ms = now_ms
                            ttft = int(now_ms - start_ms)
                            yield _sse_event({
                                "type": "meta",
                                "model": client.model,
                                "ttft_ms": ttft,
                                "ts": datetime.now(timezone.utc).isoformat(),
                            })
                        last_chunk_ms = now_ms
                        chunks.append(ev["delta"])
                        yield _sse_event(ev)
                if not chunks:
                    yield _sse_event({
                        "type": "error",
                        "code": "empty_response",
                        "message": "No chunks received",
                    })
                    return
                tokens_out = sum(len(d) // 4 for d in chunks)
                if (
                    first_chunk_ms is not None
                    and last_chunk_ms is not None
                    and last_chunk_ms > first_chunk_ms
                ):
                    gen_s = (last_chunk_ms - first_chunk_ms) / 1000
                    tps = round(tokens_out / max(gen_s, 0.05), 2)
                else:
                    tps = 0.0
                total_ms = int((last_chunk_ms or start_ms) - start_ms)
                yield _sse_event({
                    "type": "done",
                    "total_ms": total_ms,
                    "tokens_in": len(req.prompt) // 4,
                    "tokens_out": tokens_out,
                    "tps": tps,
                })
        except asyncio.TimeoutError:
            yield _sse_event({
                "type": "error",
                "code": "provider_timeout",
                "message": "Provider timed out (>15s)",
            })
        except Exception as e:
            yield _sse_event({
                "type": "error",
                "code": "provider_unavailable",
                "message": str(e),
            })

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )