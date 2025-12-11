"""Domain extractor that infers business domains from imports and namespaces."""

import ast
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Simple keyword mapping to normalize domain labels
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "core": ["core", "base", "common", "shared", "utils"],
    "checkout": ["checkout", "cart", "basket", "purchase"],
    "payments": ["payment", "billing", "invoice", "transaction"],
    "identity": ["auth", "user", "account", "identity", "login"],
    "admin": ["admin", "backoffice", "management", "cms"],
    "marketing": ["marketing", "campaign", "promotion", "discount", "coupon"],
    "catalog": ["catalog", "product", "inventory", "sku"],
    "shipping": ["shipping", "delivery", "logistics", "fulfillment"],
    "notifications": ["notification", "email", "sms", "message"],
    "analytics": ["analytics", "metrics", "reporting", "stats"],
    "testing": ["test", "e2e", "integration", "fixture"],
}


class DomainExtractor:
    """Extract business domain heuristically from code and package metadata."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root).resolve()

    def extract_domain(self, service_path: Optional[Path], service_name: str) -> Optional[str]:
        """
        Infer domain from imports, namespaces, and package metadata.
        
        Args:
            service_path: Path to the service directory
            service_name: Name of the service
        
        Returns:
            Domain label (e.g., "marketing", "payments") or None if unknown.
        """
        candidates: list[str] = []

        if not service_path or not service_path.exists():
            return None

        # Prefer directory name as a hint
        for part in service_path.parts[-2:]:
            candidates.append(part.lower())

        # Service name as a fallback
        candidates.append(service_name.lower())

        # Collect import namespaces from Python files
        for py_file in service_path.rglob("*.py"):
            if self._should_skip(py_file):
                continue
            candidates.extend(self._extract_python_import_roots(py_file))

        # Collect package.json namespace if present (JS/TS services)
        pkg_file = service_path / "package.json"
        if pkg_file.exists():
            domain_from_pkg = self._extract_domain_from_package(pkg_file)
            if domain_from_pkg:
                candidates.append(domain_from_pkg)

        # Score candidates against known keywords
        domain = self._score_candidates(candidates)
        return domain

    def _extract_python_import_roots(self, file_path: Path) -> list[str]:
        """Return the top-level module/namespace names imported in a Python file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except Exception:
            return []

        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    imports.append(root.lower())
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    imports.append(root.lower())
        return imports

    def _extract_domain_from_package(self, pkg_file: Path) -> Optional[str]:
        """Extract domain hint from package.json name (e.g., '@org/checkout-service')."""
        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            name = data.get("name")
            if not isinstance(name, str):
                return None
            # Strip scope and suffixes
            clean = name.split("/")[-1]
            clean = re.sub(r"[-_]?service$", "", clean)
            clean = clean.replace("-", "_")
            return clean.lower()
        except Exception as e:
            logger.debug(f"Failed to parse package.json at {pkg_file}: {e}")
            return None

    def _score_candidates(self, candidates: list[str]) -> Optional[str]:
        """Map candidate keywords to a domain using a simple frequency score."""
        if not candidates:
            return None

        scores: Counter[str] = Counter()
        for candidate in candidates:
            for domain, keywords in DOMAIN_KEYWORDS.items():
                if candidate == domain:
                    scores[domain] += 2  # exact match gets higher weight
                elif any(candidate.startswith(k) or k in candidate for k in keywords):
                    scores[domain] += 1

        if not scores:
            return None

        # Return the domain with the highest score
        domain, _ = scores.most_common(1)[0]
        return domain

    def _should_skip(self, file_path: Path) -> bool:
        """Skip vendor/cache directories."""
        skip_parts = {"node_modules", "__pycache__", ".git", ".venv", "venv"}
        return any(part in skip_parts for part in file_path.parts)
