"""LLM-based note enrichment for services."""

import logging
import re
from pathlib import Path
from typing import Any, Optional

from app.domain.models.services import Service
from app.services.service_extraction.llm_budget import LLMCallBudget

logger = logging.getLogger(__name__)


SMART_LLM_PROMPT = """You are a software architecture assistant.
Summarize the service in 1-2 concise sentences.
Focus on business purpose, avoid implementation details.

Service: {service_name}
Path: {service_path}
Language: {language}

Recent commit messages:
{commit_messages}

Key files (truncated):
{file_snippets}

Respond with only the 1-2 sentence summary.
"""


class SmartLLMEnricher:
    """Generate concise service notes from code and git context."""

    def __init__(self, llm_manager: Any, max_tokens: int = 200, budget: Optional[LLMCallBudget] = None):
        self.llm = llm_manager
        self.max_tokens = max_tokens
        self.budget = budget

    def generate_notes(self, service: Service, service_path: Path) -> Optional[str]:
        """Return 1-2 sentence notes or None if unavailable."""
        if not self.llm:
            return None

        snippets = self._read_snippets(self._collect_key_files(service_path))
        file_snippets = "\n\n".join(
            f"--- {path} ---\n{content}" for path, content in snippets.items()
        ) if snippets else "- none"

        commit_messages = "- none"
        if service.status_evidence and isinstance(service.status_evidence, dict):
            recent = service.status_evidence.get("recent_commit_messages", [])
            if recent:
                commit_messages = "\n".join(f"- {msg}" for msg in recent[:10])

        prompt = SMART_LLM_PROMPT.format(
            service_name=service.name,
            service_path=str(service_path),
            language=service.language or "unknown",
            commit_messages=commit_messages,
            file_snippets=file_snippets,
        )

        estimated_tokens = self._estimate_tokens(prompt, self.max_tokens)
        if self.budget and not self.budget.consume(estimated_tokens):
            logger.info("LLM budget exhausted; skipping notes for %s", service.name)
            return None

        try:
            response = self.llm.generate_text(
                prompt,
                max_tokens=self.max_tokens,
                temperature=0.2,
            )
        except Exception as exc:
            logger.warning("LLM notes generation failed for %s: %s", service.name, exc)
            return None

        if not response:
            return None

        return self._normalize_notes(response)

    def _estimate_tokens(self, prompt: str, max_tokens: int) -> int:
        """Rough heuristic: characters/4 + max tokens."""
        return int(len(prompt) / 4) + max_tokens

    def _collect_key_files(self, service_path: Path) -> list[Path]:
        """Prioritize README/docs and entrypoints."""
        candidates = [
            "README.md",
            "README.rst",
            "readme.md",
            "readme.rst",
            "__init__.py",
            "main.py",
            "app.py",
            "index.py",
            "index.js",
            "index.ts",
        ]

        files: list[Path] = []
        for name in candidates:
            candidate = service_path / name
            if candidate.exists():
                files.append(candidate)
        return files[:3]

    def _read_snippets(self, files: list[Path]) -> dict[str, str]:
        """Read up to ~800 characters per file to keep prompt compact."""
        snippets: dict[str, str] = {}
        for file_path in files:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                snippets[str(file_path.name)] = text[:800]
            except Exception:
                continue
        return snippets

    def _normalize_notes(self, text: str) -> Optional[str]:
        """Keep at most two sentences and normalize whitespace."""
        cleaned = re.sub(r"\s+", " ", text.strip())
        if not cleaned:
            return None

        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        if not sentences:
            return None

        note = " ".join(sentences[:2])
        if note and note[-1] not in ".!?":
            note = f"{note}."
        return note[:400]
