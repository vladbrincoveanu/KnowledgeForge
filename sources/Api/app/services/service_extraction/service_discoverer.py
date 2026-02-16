"""Service discovery using multi-signal detection."""

import json
import logging
from pathlib import Path
from typing import Optional

from app.utils.fs_utils import limited_rglob
from app.domain.models.services import Service, ServiceStatus, ServiceTier
from app.services.service_extraction.service_extractor import ServiceExtractor
from app.services.service_extraction.source_extractors import (
    extract_from_docker_compose,
    extract_from_kubernetes,
    extract_from_api_routes,
    extract_from_service_configs,
    extract_from_microservice_patterns,
    extract_from_top_level_directories,
)

logger = logging.getLogger(__name__)


class ServiceDiscoverer(ServiceExtractor):
    """Discover services using multiple signals across the repository."""

    def __init__(self, repo_root: Path):
        super().__init__(repo_root, llm_manager=None)

    # ------------------------------------------------------------------
    # Wrapper methods delegating to module-level source_extractors funcs
    # ------------------------------------------------------------------

    def _extract_from_docker_compose(self) -> None:
        found = extract_from_docker_compose(self.repo_root, self.services, self.errors, self.warnings)
        self.services.extend(found)

    def _extract_from_kubernetes(self) -> None:
        found = extract_from_kubernetes(self.repo_root, self.services, self.errors, self.warnings)
        self.services.extend(found)

    def _extract_from_api_routes(self) -> None:
        found = extract_from_api_routes(self.repo_root, self.services, self.errors, self.warnings)
        self.services.extend(found)

    def _extract_from_service_configs(self) -> None:
        found = extract_from_service_configs(self.repo_root, self.services, self.errors, self.warnings)
        self.services.extend(found)

    def _extract_from_microservice_patterns(self) -> None:
        found = extract_from_microservice_patterns(self.repo_root, self.services, self.errors, self.warnings)
        self.services.extend(found)

    def _extract_from_top_level_directories(self) -> None:
        found = extract_from_top_level_directories(self.repo_root, self.services, self.errors, self.warnings)
        self.services.extend(found)

    def discover_services(self) -> list[Service]:
        """Return service candidates without enrichment."""
        self.services = []
        self.errors = []
        self.warnings = []

        logger.info("Starting multi-signal service discovery")

        try:
            self._extract_from_docker_compose()
        except Exception as exc:
            logger.error("docker-compose discovery failed: %s", exc, exc_info=True)
            self.errors.append(f"docker-compose discovery failed: {exc}")

        try:
            self._extract_from_kubernetes()
        except Exception as exc:
            logger.error("kubernetes discovery failed: %s", exc, exc_info=True)
            self.errors.append(f"kubernetes discovery failed: {exc}")

        try:
            self._extract_from_api_routes()
        except Exception as exc:
            logger.error("api routes discovery failed: %s", exc, exc_info=True)
            self.errors.append(f"api routes discovery failed: {exc}")

        try:
            self._extract_from_service_configs()
        except Exception as exc:
            logger.error("service configs discovery failed: %s", exc, exc_info=True)
            self.errors.append(f"service configs discovery failed: {exc}")

        try:
            self._extract_from_microservice_patterns()
        except Exception as exc:
            logger.error("microservice pattern discovery failed: %s", exc, exc_info=True)
            self.errors.append(f"microservice pattern discovery failed: {exc}")

        try:
            self._extract_from_top_level_directories()
        except Exception as exc:
            logger.error("top-level directory discovery failed: %s", exc, exc_info=True)
            self.errors.append(f"top-level directory discovery failed: {exc}")

        try:
            self._extract_from_package_manifests()
        except Exception as exc:
            logger.error("manifest discovery failed: %s", exc, exc_info=True)
            self.errors.append(f"manifest discovery failed: {exc}")

        logger.info("Service discovery completed: %s services", len(self.services))
        return self.services

    def _extract_from_package_manifests(self) -> None:
        """Detect services by scanning for package/build manifests."""
        manifest_patterns = [
            "**/package.json",
            "**/pyproject.toml",
            "**/requirements.txt",
            "**/Pipfile",
            "**/go.mod",
            "**/Cargo.toml",
            "**/Dockerfile",
            "**/*.csproj",
            "**/*.sln",
        ]

        skip_parts = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "dist",
            "build",
        }

        manifest_files: list[Path] = []
        for pattern in manifest_patterns:
            manifest_files.extend(limited_rglob(self.repo_root, pattern))

        for manifest_file in manifest_files[:300]:
            if any(part in skip_parts for part in manifest_file.parts):
                continue

            service_dir = manifest_file.parent
            service_name = service_dir.name if service_dir != self.repo_root else self.repo_root.name

            if any(s.name == service_name for s in self.services):
                continue

            rel_path = str(service_dir.relative_to(self.repo_root))
            language, framework = self._infer_language_framework(manifest_file)

            display_name = service_name.replace("-", " ").replace("_", " ").title()
            if manifest_file.name == "package.json":
                display_name = self._display_name_from_package(manifest_file) or display_name

            service = Service(
                id=f"svc-{service_name}",
                name=service_name,
                display_name=display_name,
                domain=None,
                owner=None,
                status=ServiceStatus.UNKNOWN,
                tier=ServiceTier.UNKNOWN,
                data_class=None,
                language=language,
                framework=framework,
                file_path=rel_path,
                source="package_manifest",
            )
            self.services.append(service)

    def _infer_language_framework(self, manifest_file: Path) -> tuple[Optional[str], Optional[str]]:
        """Infer language/framework from manifest type."""
        name = manifest_file.name
        if name == "package.json":
            return "JavaScript", None
        if name in {"requirements.txt", "pyproject.toml", "Pipfile"}:
            return "Python", None
        if name == "go.mod":
            return "Go", None
        if name == "Cargo.toml":
            return "Rust", None
        if name == "Dockerfile":
            return None, None
        if manifest_file.suffix == ".csproj":
            return "C#", "ASP.NET Core"
        if manifest_file.suffix == ".sln":
            return "C#", None
        return None, None

    def _display_name_from_package(self, manifest_file: Path) -> Optional[str]:
        """Use package.json name for display name if available."""
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return None
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            return None
        clean = name.split("/")[-1]
        return clean.replace("-", " ").replace("_", " ").title()
