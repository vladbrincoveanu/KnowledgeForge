"""Lightweight token budget tracker for LLM calls."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMCallBudget:
    """Track remaining token budget for LLM calls."""

    remaining_tokens: int

    def consume(self, estimated_tokens: int) -> bool:
        """
        Attempt to spend from the budget.

        Returns True if allowed; False if budget exhausted.
        """
        if estimated_tokens <= 0:
            return True
        if self.remaining_tokens <= 0:
            return False
        if estimated_tokens > self.remaining_tokens:
            return False
        self.remaining_tokens -= estimated_tokens
        return True
