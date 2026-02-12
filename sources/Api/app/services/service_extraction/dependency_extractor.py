"""Dependency extractor that identifies direct service dependencies from imports."""

import ast
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

import yaml

from app.utils.fs_utils import limited_rglob
from app.domain.models.services import Service

logger = logging.getLogger(__name__)


class DependencyExtractor:
    """Extract direct dependencies between services by scanning imports."""

    def __init__(self, repo_root: Path, services: list[Service]):
        self.repo_root = Path(repo_root).resolve()
        self.services = services
        self.service_prefixes = self._build_service_prefixes()
        self.service_map = {svc.id: svc for svc in services}
        self.service_name_map = self._build_service_name_map()
        self.compose_dependency_map = self._scan_compose_dependencies()
        self.k8s_dependency_map = self._scan_k8s_dependencies()

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

        # Limit file search to prevent hangs on large directories
        # Use glob with patterns instead of rglob("*") to limit depth
        file_patterns = ["**/*.py", "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.mjs", "**/*.cjs"]
        all_files = []
        for pattern in file_patterns:
            try:
                files = list(service_path.glob(pattern))[:100]  # Limit per pattern
                all_files.extend(files)
            except Exception as e:
                logger.warning(f"Error searching files with pattern {pattern} in {service_path}: {e}")
        
        # Remove duplicates and limit total
        seen = set()
        for file_path in all_files[:500]:  # Overall limit
            if file_path in seen:
                continue
            seen.add(file_path)
            
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

        service_keys = self._get_service_keys(service)
        for key in service_keys:
            dependencies.update(self.compose_dependency_map.get(key, set()))
            dependencies.update(self.k8s_dependency_map.get(key, set()))

        dependencies.update(self._scan_env_dependencies(service_path))

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

    def _build_service_name_map(self) -> dict[str, str]:
        """Map normalized service tokens to service IDs."""
        name_map: dict[str, str] = {}
        for svc in self.services:
            for key in self._get_service_keys(svc):
                if key:
                    name_map[key] = svc.id
        return name_map

    def _normalize_token(self, token: str) -> str:
        return token.replace("-", "_").lower()

    def _get_service_keys(self, service: Service) -> set[str]:
        """Return normalized tokens that can identify this service."""
        keys: set[str] = set()
        if service.name:
            keys.add(self._normalize_token(service.name))
        if service.docker_compose_service:
            keys.add(self._normalize_token(service.docker_compose_service))
        if service.file_path:
            path = Path(service.file_path)
            if path.parts:
                keys.add(self._normalize_token(path.parts[-1]))
        return {key for key in keys if key}

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

    def _map_token_to_service_id(self, token: str, current_service_id: Optional[str] = None) -> Optional[str]:
        normalized = self._normalize_token(token)
        service_id = self.service_name_map.get(normalized)
        if not service_id or service_id == current_service_id:
            return None
        return service_id

    def _extract_dependency_tokens(self, value: str) -> set[str]:
        """Extract candidate dependency tokens from a string value."""
        tokens = set(
            self._normalize_token(token)
            for token in re.split(r"[^A-Za-z0-9_-]+", value)
            if token
        )
        skip = {"http", "https", "tcp", "udp", "localhost", "local", "svc", "service"}
        return {token for token in tokens if token and token not in skip}

    def _collect_env_values(self, env: object) -> list[str]:
        values: list[str] = []
        if isinstance(env, dict):
            values.extend(str(value) for value in env.values() if value is not None)
        elif isinstance(env, list):
            for item in env:
                if isinstance(item, str):
                    if "=" in item:
                        values.append(item.split("=", 1)[1])
                    else:
                        values.append(item)
        return values

    def _scan_compose_dependencies(self) -> dict[str, set[str]]:
        """Extract dependencies from docker-compose files."""
        dependency_map: dict[str, set[str]] = defaultdict(set)

        compose_files = (
            list(limited_rglob(self.repo_root, "docker-compose*.yml"))
            + list(limited_rglob(self.repo_root, "docker-compose*.yaml"))
            + list(limited_rglob(self.repo_root, "compose.yml"))
            + list(limited_rglob(self.repo_root, "compose.yaml"))
        )

        for compose_file in compose_files[:80]:
            try:
                content = compose_file.read_text(encoding="utf-8")
                compose_data = yaml.safe_load(content)
            except (OSError, yaml.YAMLError):
                continue

            if not compose_data or "services" not in compose_data:
                continue

            services = compose_data.get("services", {})
            if not isinstance(services, dict):
                continue

            for service_name, service_config in services.items():
                source_key = self._normalize_token(service_name)
                if not isinstance(service_config, dict):
                    continue

                depends_on = service_config.get("depends_on", [])
                if isinstance(depends_on, dict):
                    depends_on = depends_on.keys()
                if isinstance(depends_on, list):
                    for dep in depends_on:
                        dep_id = self._map_token_to_service_id(str(dep))
                        if dep_id:
                            dependency_map[source_key].add(dep_id)

                links = service_config.get("links", [])
                if isinstance(links, list):
                    for link in links:
                        dep_id = self._map_token_to_service_id(str(link))
                        if dep_id:
                            dependency_map[source_key].add(dep_id)

                for value in self._collect_env_values(service_config.get("environment", {})):
                    for token in self._extract_dependency_tokens(value):
                        dep_id = self._map_token_to_service_id(token)
                        if dep_id:
                            dependency_map[source_key].add(dep_id)

        return dependency_map

    def _scan_k8s_dependencies(self) -> dict[str, set[str]]:
        """Extract dependencies from Kubernetes manifests."""
        dependency_map: dict[str, set[str]] = defaultdict(set)
        k8s_patterns = [
            "**/k8s/**/*.yaml",
            "**/k8s/**/*.yml",
            "**/kubernetes/**/*.yaml",
            "**/kubernetes/**/*.yml",
            "**/manifests/**/*.yaml",
            "**/manifests/**/*.yml",
            "*.yaml",
            "*.yml",
        ]

        k8s_files: list[Path] = []
        for pattern in k8s_patterns:
            k8s_files.extend(list(self.repo_root.glob(pattern))[:50])

        seen = set()
        k8s_files = [f for f in k8s_files if f not in seen and not seen.add(f)]
        k8s_files = k8s_files[:200]

        for k8s_file in k8s_files:
            if "docker-compose" in k8s_file.name.lower() or "compose" in k8s_file.name.lower():
                continue
            try:
                content = k8s_file.read_text(encoding="utf-8")
                documents = list(yaml.safe_load_all(content))
            except (OSError, yaml.YAMLError):
                continue

            for doc in documents:
                if not isinstance(doc, dict):
                    continue
                kind = str(doc.get("kind", "")).lower()
                if kind not in {"deployment", "statefulset", "daemonset", "job", "cronjob"}:
                    continue
                metadata = doc.get("metadata", {})
                service_name = metadata.get("name")
                if not service_name:
                    continue
                source_key = self._normalize_token(service_name)

                pod_spec = self._extract_pod_spec(kind, doc)
                containers = pod_spec.get("containers", []) if isinstance(pod_spec, dict) else []
                for container in containers:
                    for env in container.get("env", []) or []:
                        if not isinstance(env, dict):
                            continue
                        env_name = env.get("name") or ""
                        env_value = env.get("value")
                        if env_value:
                            for token in self._extract_dependency_tokens(str(env_value)):
                                dep_id = self._map_token_to_service_id(token)
                                if dep_id:
                                    dependency_map[source_key].add(dep_id)
                        if env_name.endswith("_SERVICE_HOST") or env_name.endswith("_SERVICE_URL"):
                            prefix = env_name.replace("_SERVICE_HOST", "").replace("_SERVICE_URL", "")
                            dep_id = self._map_token_to_service_id(prefix)
                            if dep_id:
                                dependency_map[source_key].add(dep_id)

        return dependency_map

    def _extract_pod_spec(self, kind: str, doc: dict) -> dict:
        """Extract pod spec from common workload kinds."""
        spec = doc.get("spec", {})
        if kind == "cronjob":
            return (
                spec.get("jobTemplate", {})
                .get("spec", {})
                .get("template", {})
                .get("spec", {})
            )
        return spec.get("template", {}).get("spec", {})

    def _scan_env_dependencies(self, service_path: Path) -> set[str]:
        """Scan local environment files for service references."""
        dependency_ids: set[str] = set()
        env_files = [
            service_path / ".env",
            service_path / ".env.local",
            service_path / ".env.production",
            service_path / "config.env",
        ]

        for env_file in env_files:
            if not env_file.exists() or not env_file.is_file():
                continue
            try:
                content = env_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                value = stripped.split("=", 1)[1]
                for token in self._extract_dependency_tokens(value):
                    dep_id = self._map_token_to_service_id(token)
                    if dep_id:
                        dependency_ids.add(dep_id)

        return dependency_ids

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
