import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from .tool_registry import ExtractionToolRegistry


class StopReason(Enum):
    natural_stop = "natural_stop"
    budget_exceeded = "budget_exceeded"
    rate_limit_midrun = "rate_limit_midrun"
    timeout = "timeout"


@dataclass
class Budget:
    max_tool_calls: int = 20
    max_tokens: int = 100_000


@dataclass
class LoopResult:
    stop_reason: StopReason
    tool_calls_used: int
    tokens_in: int
    tokens_out: int
    last_response: Any = None

    @property
    def tokens_used(self) -> int:
        return self.tokens_in + self.tokens_out

    @property
    def tokens_used(self) -> int:
        return self.tokens_in + self.tokens_out


class RateLimitMidrunError(Exception):
    pass


class LLMAgentLoop:
    def __init__(self, client, tool_registry: ExtractionToolRegistry,
                 system_prompt: str):
        self.client = client
        self.registry = tool_registry
        self.system = system_prompt

    async def run(self, warm_payload: str, budget: Budget) -> LoopResult:
        tools = self.registry.get_tools()
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": warm_payload}
        ]
tool_calls_used = 0
        tokens_in = 0
        tokens_out = 0
        turn = 0

        while True:
            kwargs: dict[str, Any] = {}
            if turn == 0:
                kwargs["tool_choice"] = {"type": "any"}

            try:
                resp = await self.client.messages_create(
                    messages=messages, tools=tools, system=self.system, **kwargs
                )
            except RateLimitMidrunError:
                return LoopResult(stop_reason=StopReason.rate_limit_midrun,
                                  tool_calls_used=tool_calls_used,
                                  tokens_in=tokens_in,
                                  tokens_out=tokens_out)

            tokens_in += getattr(resp.usage, "input_tokens", 0)
            tokens_out += getattr(resp.usage, "output_tokens", 0)

            tool_uses = [b for b in (resp.content or [])
                         if getattr(b, "type", None) == "tool_use"]

            messages.append({"role": "assistant",
                             "content": [self._block_to_dict(b)
                                         for b in resp.content or []]})

            if resp.stop_reason != "tool_use" or not tool_uses:
                return LoopResult(stop_reason=StopReason.natural_stop,
                                  tool_calls_used=tool_calls_used,
                                  tokens_in=tokens_in,
                                  tokens_out=tokens_out,
                                  last_response=resp)

            tool_results = []
            for tu in tool_uses:
                tool_calls_used += 1
                result = self.registry.dispatch(tu.name, tu.input or {})
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu.id,
                    "content": result["content"], "is_error": result["is_error"],
                })

            messages.append({"role": "user", "content": tool_results})

            if (tool_calls_used >= budget.max_tool_calls
                    or (tokens_in + tokens_out) >= budget.max_tokens):
                return LoopResult(stop_reason=StopReason.budget_exceeded,
                                  tool_calls_used=tool_calls_used,
                                  tokens_in=tokens_in,
                                  tokens_out=tokens_out)
            turn += 1

    def _block_to_dict(self, b: Any) -> dict[str, Any]:
        t = getattr(b, "type", None)
        if t == "tool_use":
            return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
        if t == "text":
            return {"type": "text", "text": b.text}
        return {"type": str(t)}