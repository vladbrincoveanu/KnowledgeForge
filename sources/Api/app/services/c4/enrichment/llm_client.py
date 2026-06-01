import os
import time
import asyncio
from typing import AsyncIterator, Optional

from anthropic import Anthropic

MINIMAX_API_URL = "https://api.minimax.io/anthropic"


def _extract_delta_text(event) -> Optional[str]:
    """Extract the text payload from a content_block_delta event.

    Handles both dict-style events (older SDK, proxies, mocks) and typed
    object events (modern anthropic SDK), so callers don't have to care
    which shape the underlying transport returned.
    """
    if isinstance(event, dict):
        if event.get("type") != "content_block_delta":
            return None
        delta = event.get("delta")
    else:
        if getattr(event, "type", None) != "content_block_delta":
            return None
        delta = getattr(event, "delta", None)
    if delta is None:
        return None
    if isinstance(delta, dict):
        return delta.get("text") or None
    return getattr(delta, "text", None) or None


class RateCounter:
    def __init__(self, max_per_window: int = 100, window_s: int = 3600):
        self.max_per_window = max_per_window
        self.window_s = window_s
        self._timestamps: list[float] = []

    async def can_run(self, reserve: int = 1) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_s
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        return len(self._timestamps) + reserve <= self.max_per_window

    def record(self) -> None:
        self._timestamps.append(time.monotonic())


_rate_counter: Optional[RateCounter] = None


def get_rate_counter() -> RateCounter:
    global _rate_counter
    if _rate_counter is None:
        _rate_counter = RateCounter()
    return _rate_counter


class EnrichmentLLMClient:
    def __init__(self, client: Anthropic, model: str):
        self.client = client
        self.model = model

    @classmethod
    def from_env(cls) -> Optional["EnrichmentLLMClient"]:
        api_key = os.getenv("MINIMAX_API_KEY")
        if not api_key:
            return None
        model = os.getenv("ENRICHMENT_MODEL", "anthropic/claude-sonnet-4-20250514")
        return cls(Anthropic(base_url=MINIMAX_API_URL, api_key=api_key), model=model)

    async def messages_create(self, messages: list[dict], tools: list[dict],
                             system: str, **kwargs):
        return await asyncio.to_thread(
            self.client.messages.create,
            model=self.model,
            messages=messages,
            tools=tools,
            system=system,
            max_tokens=4096,
            **kwargs,
        )

    async def messages_stream(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 256,
    ) -> AsyncIterator[dict]:
        """Async-iterate over streamed text deltas from the configured provider.

        Yields normalized {"type": "chunk", "delta": str} events.
        Non-delta SDK events (message_start, content_block_stop, message_stop)
        are skipped. Empty or None text deltas are also skipped.
        """
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
                text = _extract_delta_text(event)
                if text:
                    yield {"type": "chunk", "delta": text}