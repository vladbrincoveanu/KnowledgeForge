"""LLM-based enrichment for service labels and notes."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from app.domain.models.services import Service, ServiceStatus, ServiceTier
from app.services.service_extraction.domain_extractor import DOMAIN_KEYWORDS
from app.services.service_extraction.llm_budget import LLMCallBudget

logger = logging.getLogger(__name__)


LLM_ENRICH_PROMPT = """You are a software architecture assistant.
Analyze the service and return JSON with exactly these fields:

{{
  "domain": "oneword",  // ONE WORD ONLY, no spaces, lowercase (e.g. "payments", "identity", "analytics")
  "owner": "team or person",  // team or maintainer name (e.g. "Platform Team", "Akshay Goel")
  "status": "Active-Dev | Maintenance-Only | Deprecated / Frozen",
  "tier": "Tier 1 | Tier 2 | Tier 3",
  "data_class": "Public | Internal | PII | Credit-Card | Secret | Unknown",
  "notes": "1-2 complete sentences describing what this service does at the business level. Must end with a period."
}}

CRITICAL RULES:
- domain: MUST be exactly ONE word, lowercase, no spaces or hyphens
- notes: MUST be 1-2 sentences, ending with a period. Describe the business purpose, not technical details.
- If unsure, make a best-effort guess based on README/commits and still return values.

Known domain hints: {domain_hints}

Service name: {service_name}
Path: {service_path}
Language: {language}
Existing domain: {existing_domain}
Existing owner: {existing_owner}
Existing status: {existing_status}
Existing tier: {existing_tier}
Existing data_class: {existing_data_class}
Existing description: {existing_description}

Recent commit messages (for activity context):
{commit_messages}

Key files (truncated):
{file_snippets}

Return ONLY valid JSON, no markdown, no explanations.
"""


class ServiceLLMEnricher:
    """Use LLM to enrich service labels and notes."""

    def __init__(self, llm_manager: Any, max_tokens: int = 200, budget: Optional[LLMCallBudget] = None):
        self.llm = llm_manager
        self.max_tokens = max_tokens
        self.budget = budget

    def enrich_service(
        self,
        service: Service,
        service_path: Path,
        repo_root: Optional[Path] = None,
    ) -> dict[str, Optional[str]]:
        """Return LLM-derived labels/notes or empty dict on failure."""
        if not self.llm:
            return {}

        snippets = self._read_snippets(self._collect_key_files(service_path, repo_root))
        file_snippets = "\n\n".join(
            f"--- {path} ---\n{content}" for path, content in snippets.items()
        ) if snippets else "- none"

        # Extract commit messages from status_evidence if available
        commit_messages = "- none"
        if service.status_evidence and isinstance(service.status_evidence, dict):
            recent_messages = service.status_evidence.get('recent_commit_messages', [])
            if recent_messages:
                commit_messages = "\n".join(f"- {msg}" for msg in recent_messages[:10])

        domain_hints = ", ".join(sorted(DOMAIN_KEYWORDS.keys()))

        prompt = LLM_ENRICH_PROMPT.format(
            domain_hints=domain_hints,
            service_name=service.name,
            service_path=str(service_path),
            language=service.language or "unknown",
            existing_domain=service.domain or "unknown",
            existing_owner=service.owner or "unknown",
            existing_status=service.status.value if isinstance(service.status, ServiceStatus) else str(service.status),
            existing_tier=service.tier.value if isinstance(service.tier, ServiceTier) else str(service.tier),
            existing_data_class=service.data_class or "unknown",
            existing_description=service.description or "unknown",
            commit_messages=commit_messages,
            file_snippets=file_snippets,
        )

        estimated_tokens = self._estimate_tokens(prompt, self.max_tokens)
        if self.budget and not self.budget.consume(estimated_tokens):
            logger.debug("LLM budget exhausted; skipping enrichment for %s", service.name)
            return {}

        try:
            llm_url = getattr(self.llm, "base_url", None) or getattr(self.llm, "lmstudio_url", "unknown")
            logger.info(
                "Requesting LLM enrichment for service '%s' via %s (model: %s)",
                service.name,
                llm_url,
                getattr(self.llm, "default_model", "unknown"),
            )
            logger.debug(f"LLM prompt preview (first 500 chars): {prompt[:500]}")
            response = self.llm.generate_text(
                prompt,
                max_tokens=self.max_tokens,
                temperature=0.2,
            )
            logger.info(f"LLM response received for service '{service.name}': {response[:200] if response else 'None'}")
        except Exception as exc:
            logger.error(f"LLM label enrichment failed for {service.name}: {exc}", exc_info=True)
            return {}

        if not response:
            return {}

        parsed = self._parse_json(response)
        if not isinstance(parsed, dict):
            logger.warning(
                "LLM enrichment response not JSON for service '%s': %s",
                service.name,
                response[:300].replace("\n", " "),
            )
            return {}

        result = {
            "domain": self._normalize_domain(parsed.get("domain")),
            "owner": self._normalize_owner(parsed.get("owner")),
            "status": self._normalize_status(parsed.get("status")),
            "tier": self._normalize_tier(parsed.get("tier")),
            "data_class": self._normalize_label(parsed.get("data_class")),
            "notes": self._normalize_notes(parsed.get("notes")),
        }
        
        logger.info(
            "LLM enrichment parsed result for service: domain=%s, owner=%s, status=%s, tier=%s, data_class=%s, notes=%s",
            result.get("domain"),
            result.get("owner"),
            result.get("status"),
            result.get("tier"),
            result.get("data_class"),
            result.get("notes")[:100] if result.get("notes") else None,
        )
        return result

    def _estimate_tokens(self, prompt: str, max_tokens: int) -> int:
        """Rough heuristic: characters/4 + max tokens."""
        return int(len(prompt) / 4) + max_tokens

    def _collect_key_files(self, service_path: Path, repo_root: Optional[Path] = None) -> list[Path]:
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

        if repo_root and repo_root != service_path:
            for name in candidates:
                candidate = repo_root / name
                if candidate.exists() and candidate not in files:
                    files.append(candidate)

        return files[:4]

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

    def _parse_json(self, text: str) -> Optional[dict[str, Any]]:
        """Extract JSON object from response."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    def _normalize_label(self, value: Any) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            lowered = cleaned.lower()
            if lowered in {"unknown", "unclassified", "none", "n/a", "null"}:
                return None
            return cleaned
        return None

    def _normalize_owner(self, value: Any) -> Optional[str]:
        return self._normalize_label(value)

    def _normalize_status(self, value: Any) -> Optional[str]:
        cleaned = self._normalize_label(value)
        if not cleaned:
            return None
        lowered = cleaned.lower()
        if any(token in lowered for token in ["deprecat", "sunset", "retire", "frozen", "legacy", "eol"]):
            return ServiceStatus.DEPRECATED.value
        if any(token in lowered for token in ["maint", "bugfix", "support", "stabil", "patch"]):
            return ServiceStatus.MAINTENANCE_ONLY.value
        if any(token in lowered for token in ["active", "dev", "feature"]):
            return ServiceStatus.ACTIVE_DEV.value
        return cleaned

    def _normalize_tier(self, value: Any) -> Optional[str]:
        cleaned = self._normalize_label(value)
        if not cleaned:
            return None
        lowered = cleaned.lower()
        if any(token in lowered for token in ["tier 1", "tier1", "t1", "critical", "p0", "p1"]):
            return ServiceTier.TIER_1.value
        if any(token in lowered for token in ["tier 2", "tier2", "t2", "important", "p2", "medium"]):
            return ServiceTier.TIER_2.value
        if any(token in lowered for token in ["tier 3", "tier3", "t3", "minor", "p3", "low"]):
            return ServiceTier.TIER_3.value
        return cleaned

    def _normalize_domain(self, value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        lowered = cleaned.lower()
        if lowered in {"unknown", "unclassified", "none", "n/a", "null"}:
            return None
        first_token = re.split(r"[\s/]+", cleaned)[0].strip(" ,;:")
        return first_token or None

    def _normalize_notes(self, value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        cleaned = re.sub(r"\s+", " ", value.strip())
        if not cleaned or cleaned.lower() in {"unknown", "n/a", "null"}:
            return None
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        if not sentences:
            return None
        note = " ".join(sentences[:2])
        if note and note[-1] not in ".!?":
            note = f"{note}."
        return note[:400]
