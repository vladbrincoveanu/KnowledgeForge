import os
import time
import asyncio
from typing import Optional

from anthropic import Anthropic

MINIMAX_API_URL = "https://api.minimax.io/anthropic"


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