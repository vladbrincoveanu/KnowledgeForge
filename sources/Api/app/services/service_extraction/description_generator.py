"""Generate short service descriptions using optional LLM support."""

import logging
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)


DESCRIPTION_PROMPT = """You are an engineering assistant.
Summarize the purpose of this service in 1-2 concise sentences (business-level).
Avoid implementation details; focus on the business capability.

Service: {service_name}
Path: {service_path}
Language: {language}

Key files (truncated):
{file_snippets}

Respond with only the description sentence(s).
"""


class ServiceDescriptionGenerator:
    """Generate descriptions from code/docs with optional LLM assistance."""

    def __init__(self, llm_manager: Optional[Any], max_tokens: int = 150):
        self.llm = llm_manager
        self.max_tokens = max_tokens

    def generate_description(
        self,
        service_name: str,
        service_path: Path,
        language: Optional[str] = None,
    ) -> Optional[str]:
        """Return a short description or None if not enough signal."""
        key_files = self._collect_key_files(service_path)
        snippets = self._read_snippets(key_files)

        if not snippets:
            return None

        file_snippets = "\n\n".join(
            f"--- {path} ---\n{content}" for path, content in snippets.items()
        )

        prompt = DESCRIPTION_PROMPT.format(
            service_name=service_name,
            service_path=str(service_path),
            language=language or "unknown",
            file_snippets=file_snippets,
        )

        # Prefer LLM if available
        if self.llm:
            try:
                response = self.llm.generate_text(
                    prompt,
                    max_tokens=self.max_tokens,
                    temperature=0.3,
                )
                if response:
                    return response.strip().replace("\n", " ")
            except Exception as e:
                logger.debug(f"LLM description generation failed: {e}")

        # Fallback: synthesize from first snippet header/content
        for path, content in snippets.items():
            first_line = content.strip().splitlines()[0] if content.strip() else ""
            if first_line:
                return f"{service_name} service: {first_line[:200]}"

        return None

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
        return files[:3]  # limit to keep prompts small

    def _read_snippets(self, files: list[Path]) -> dict[str, str]:
        """Read up to ~400 characters per file to keep prompt compact."""
        snippets: dict[str, str] = {}
        for file_path in files:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                snippets[str(file_path.name)] = text[:800]
            except Exception:
                continue
        return snippets
