"""Domain extractor that infers business domains from imports and namespaces."""

import ast
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Optional

from app.utils.fs_utils import limited_rglob

logger = logging.getLogger(__name__)


# Comprehensive keyword mapping to normalize domain labels
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    # AI/ML domains (high priority for ML repos)
    "ai": [
        "ai", "ml", "machine", "learning", "llm", "nlp", "language", "model",
        "neural", "deep", "tensor", "transformer", "embedding", "vector",
        "inference", "training", "prediction", "classification", "extraction",
        "ner", "tokenize", "parse", "langchain", "openai", "anthropic",
        "huggingface", "pytorch", "tensorflow", "scikit", "spacy", "gpt",
        "bert", "llama", "ollama", "chunk", "rag", "retrieval", "semantic",
    ],
    # Core infrastructure
    "core": ["core", "base", "common", "shared", "utils", "lib", "sdk", "platform"],
    "infrastructure": ["infra", "devops", "deploy", "ci", "cd", "kubernetes", "k8s", "docker", "terraform"],
    "database": ["database", "db", "postgres", "mysql", "mongo", "redis", "cache", "storage"],
    "messaging": ["queue", "kafka", "rabbitmq", "pubsub", "event", "stream", "message"],
    # Business domains
    "checkout": ["checkout", "cart", "basket", "purchase", "order"],
    "payments": ["payment", "billing", "invoice", "transaction", "stripe", "paypal"],
    "identity": ["auth", "user", "account", "identity", "login", "oauth", "sso", "jwt", "session"],
    "admin": ["admin", "backoffice", "management", "cms", "dashboard", "portal"],
    "marketing": ["marketing", "campaign", "promotion", "discount", "coupon", "ads", "seo"],
    "catalog": ["catalog", "product", "inventory", "sku", "listing", "item"],
    "shipping": ["shipping", "delivery", "logistics", "fulfillment", "tracking", "carrier"],
    "notifications": ["notification", "email", "sms", "push", "alert", "webhook"],
    "analytics": ["analytics", "metrics", "reporting", "stats", "telemetry", "observability", "monitoring"],
    "search": ["search", "elastic", "solr", "index", "query", "filter"],
    # Development domains
    "api": ["api", "gateway", "rest", "graphql", "grpc", "endpoint"],
    "frontend": ["frontend", "web", "ui", "react", "vue", "angular", "client"],
    "mobile": ["mobile", "ios", "android", "app", "native"],
    "testing": ["test", "e2e", "integration", "fixture", "mock", "spec", "cypress", "playwright"],
    "security": ["security", "crypto", "encrypt", "audit", "compliance", "vulnerability"],
    "docs": ["docs", "documentation", "readme", "wiki", "guide"],
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
        for py_file in limited_rglob(service_path, "*.py"):
            if self._should_skip(py_file):
                continue
            candidates.extend(self._extract_python_import_roots(py_file))

        # Collect README keywords from service and repo root
        for readme_text in self._read_readme_texts(service_path):
            candidates.extend(self._tokenize_text(readme_text))

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
        except (OSError, json.JSONDecodeError, ValueError) as e:
            try:
                from app.utils.config import get_config as _get_config
                config_debug = getattr(_get_config(), "debug", False)
            except (OSError, json.JSONDecodeError, ValueError):
                config_debug = False
            if config_debug:
                logger.debug(f"Failed to parse package.json at {pkg_file}: {e}")
            return None

    def extract_domain_from_text(self, text: str) -> Optional[str]:
        """Extract domain from README or description text."""
        tokens = self._tokenize_text(text)
        return self._score_candidates(tokens)

    def _tokenize_text(self, text: str) -> list[str]:
        """Split text into lowercase tokens for scoring."""
        return [token.lower() for token in re.split(r"[^A-Za-z0-9]+", text) if token]

    def _read_readme_texts(self, service_path: Path) -> list[str]:
        """Collect README text from service path and repo root."""
        readme_names = ["README.md", "README.rst", "readme.md", "readme.rst"]
        texts: list[str] = []

        for base in {service_path, self.repo_root}:
            for name in readme_names:
                candidate = base / name
                if candidate.exists():
                    try:
                        texts.append(candidate.read_text(encoding="utf-8", errors="ignore")[:4000])
                    except Exception:
                        continue

        return texts

    def _score_candidates(self, candidates: list[str]) -> Optional[str]:
        """Map candidate keywords to a domain using weighted frequency score."""
        if not candidates:
            return None

        scores: Counter[str] = Counter()
        for candidate in candidates:
            candidate_lower = candidate.lower()
            for domain, keywords in DOMAIN_KEYWORDS.items():
                # Exact match with domain name
                if candidate_lower == domain:
                    scores[domain] += 5
                # Exact match with any keyword
                elif candidate_lower in keywords:
                    scores[domain] += 3
                # Partial match (keyword contained in candidate or vice versa)
                elif any(k in candidate_lower for k in keywords):
                    scores[domain] += 2
                elif any(candidate_lower in k for k in keywords if len(candidate_lower) >= 3):
                    scores[domain] += 1

        if not scores:
            return None

        # Return the domain with the highest score
        domain, score = scores.most_common(1)[0]
        try:
            from app.utils.config import get_config as _get_config
            config_debug = getattr(_get_config(), "debug", False)
        except Exception:
            config_debug = False
        if config_debug:
            logger.debug(f"Domain scoring: top={domain} (score={score}), all={dict(scores.most_common(5))}")
        return domain

    def _should_skip(self, file_path: Path) -> bool:
        """Skip vendor/cache directories."""
        skip_parts = {"node_modules", "__pycache__", ".git", ".venv", "venv"}
        return any(part in skip_parts for part in file_path.parts)
