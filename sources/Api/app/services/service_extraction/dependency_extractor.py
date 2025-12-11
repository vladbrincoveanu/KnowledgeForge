"""Dependency extractor that identifies direct service dependencies from imports."""

import ast
import logging
import re
from pathlib import Path
from typing import Optional

from app.domain.models.services import Service

logger = logging.getLogger(__name__)


class DependencyExtractor:
    """Extract direct dependencies between services by scanning imports."""

    def __init__(self, repo_root: Path, services: list[Service]):
        self.repo_root = Path(repo_root).resolve()
        self.services = services
        self.service_prefixes = self._build_service_prefixes()
        self.service_map = {svc.id: svc for svc in services}

    def extract_dependencies(self, service: Service) -> list[str]:
        """
        Scan a service directory for imports that reference other services.
        
        Returns:
            List of service IDs this service directly depends on.
        """
        service_path = self._get_service_path(service)
        if not service_path or not service_path.exists():
            return []

        dependencies: set[str] = set()

        for file_path in service_path.rglob("*"):
            if not file_path.is_file():
                continue
            if self._should_skip(file_path):
                continue

            suffix = file_path.suffix.lower()
            if suffix == ".py":
                imports = self._parse_python_imports(file_path)
            elif suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
                imports = self._parse_js_imports(file_path)
            else:
                continue

            for import_path in imports:
                target_service = self._map_import_to_service(import_path, service.id)
                if target_service:
                    dependencies.add(target_service)

        return sorted(dependencies)

    def _get_service_path(self, service: Service) -> Optional[Path]:
        """Resolve the directory that contains the service code."""
        if service.file_path:
            candidate = (self.repo_root / service.file_path).resolve()
            if candidate.exists():
                return candidate if candidate.is_dir() else candidate.parent

        candidate = (self.repo_root / service.name).resolve()
        if candidate.exists():
            return candidate if candidate.is_dir() else candidate.parent

        return None

    def _build_service_prefixes(self) -> dict[str, set[str]]:
        """Prepare normalized import prefixes for each service for quick matching."""
        prefixes: dict[str, set[str]] = {}

        for svc in self.services:
            svc_prefixes: set[str] = set()

            def _normalize(token: str) -> str:
                return token.replace("-", "_").lower()

            # Service name
            if svc.name:
                svc_prefixes.add(_normalize(svc.name))

            # Path-based prefixes
            if svc.file_path:
                path = Path(svc.file_path)
                parts = [_normalize(p) for p in path.parts if p]
                if parts:
                    svc_prefixes.add(".".join(parts))
                    svc_prefixes.add(parts[-1])
                    if len(parts) >= 2:
                        svc_prefixes.add(".".join(parts[:2]))

            prefixes[svc.id] = {p for p in svc_prefixes if p}

        return prefixes

    def _normalize_import(self, import_path: str) -> Optional[str]:
        """Normalize import path for comparison."""
        if not import_path:
            return None

        path = import_path.strip()
        if path.startswith("."):
            return None  # skip relative imports

        # Strip scopes like @org/package
        if path.startswith("@"):
            path = path.split("/", 1)[-1]

        path = path.replace("/", ".").replace("-", "_")
        return path.lower()

    def _map_import_to_service(self, import_path: str, current_service_id: str) -> Optional[str]:
        """Return the service ID that the import likely references."""
        normalized = self._normalize_import(import_path)
        if not normalized:
            return None

        best_match: tuple[int, str] | None = None  # (prefix_len, service_id)

        for service_id, prefixes in self.service_prefixes.items():
            if service_id == current_service_id:
                continue
            for prefix in prefixes:
                if normalized == prefix or normalized.startswith(prefix + "."):
                    match_len = len(prefix)
                    if not best_match or match_len > best_match[0]:
                        best_match = (match_len, service_id)

        return best_match[1] if best_match else None

    def _parse_python_imports(self, file_path: Path) -> list[str]:
        """Extract import paths from a Python file using the AST."""
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except Exception:
            return []

        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    def _parse_js_imports(self, file_path: Path) -> list[str]:
        """Extract import/require targets from JS/TS files."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return []

        imports: list[str] = []

        # ES module imports
        imports.extend(re.findall(r'import\s+(?:[^\'"]+?\s+from\s+)?[\'"]([^\'"]+)[\'"]', content))
        # require()
        imports.extend(re.findall(r'require\(\s*[\'"]([^\'"]+)[\'"]\s*\)', content))

        return imports

    def _should_skip(self, file_path: Path) -> bool:
        """Skip vendor/build directories."""
        skip_parts = {"node_modules", "__pycache__", ".git", ".venv", "venv", "dist", "build"}
        return any(part in skip_parts for part in file_path.parts)
