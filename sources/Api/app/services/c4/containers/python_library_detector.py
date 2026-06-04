"""Python Library Detector - detects Python packages that are not applications."""

import logging
from pathlib import Path
from typing import Any, Optional

from .base_detector import BaseContainerDetector
from . import utils

logger = logging.getLogger(__name__)


EXCLUDED_DIRS = {
    '__pycache__', '.git', '.github', '.gitlab', 'node_modules',
    'venv', 'env', '.env', 'dist', 'build', 'target', 'out',
    '.idea', '.vscode', 'logs', 'temp', 'tmp', '.pytest_cache',
    'test', 'tests', '__tests__', 'docs', 'documentation',
    '.next', '.nuxt', '.cache', 'coverage', '.coverage',
    '.tox', '.nox', '.eggs', '.egg-info',
}


class PythonLibraryDetector(BaseContainerDetector):
    """Detect Python packages/libraries that are not applications.

    A Python library has:
    - __init__.py (pure Python package indicator)
    - pyproject.toml or setup.py or setup.cfg (packaging metadata)
    - NO __main__.py (which would make it an application)

    This detector finds packages like dagster libraries, SDKs, etc.
    """

    def __init__(self, repo_path: Path, llm_manager=None):
        """Initialize Python library detector.

        Args:
            repo_path: Path to repository root
            llm_manager: Optional LLM manager for descriptions
        """
        super().__init__(repo_path)
        self.llm_manager = llm_manager

    def can_detect(self) -> bool:
        """Check if Python library detection is possible."""
        return True

    # Framework manifests mirrored from StructureDetector for collection checks
    _FRAMEWORK_MANIFESTS = {
        'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
        'package.json', 'pyproject.toml', 'pom.xml', 'build.gradle',
        'build.gradle.kts', 'go.mod', 'Cargo.toml', 'requirements.txt',
        'Chart.yaml', 'kustomization.yaml',
    }
    _COLLECTION_THRESHOLD = 3

    def detect(self) -> list[dict[str, Any]]:
        """Detect Python libraries in the repository.

        Returns:
            List of container dictionaries for Python libraries
        """
        libraries = []
        seen_paths = set()

        for init_file in self.repo_path.rglob("__init__.py"):
            dir_path = init_file.parent

            if dir_path == self.repo_path:
                continue

            rel_path = dir_path.relative_to(self.repo_path)
            if str(rel_path) in seen_paths:
                continue

            if self._is_collection_member(dir_path):
                continue

            if self._is_python_library(dir_path):
                container = self._create_library_container(dir_path)
                if container:
                    libraries.append(container)
                    seen_paths.add(str(rel_path))

        return libraries

    def _is_collection_member(self, directory: Path) -> bool:
        """Return True if directory is part of a collection tree (walk upward)."""
        if directory.parent == self.repo_path:
            return False
        current = directory
        while True:
            parent = current.parent
            if parent == self.repo_path:
                break
            sibling_count = 0
            try:
                for child in parent.iterdir():
                    if not child.is_dir() or child == current:
                        continue
                    if any((child / m).exists() for m in self._FRAMEWORK_MANIFESTS):
                        sibling_count += 1
                        if sibling_count >= self._COLLECTION_THRESHOLD:
                            return True
            except OSError:
                pass
            current = parent
        return False

    def _is_python_library(self, directory: Path) -> bool:
        """Check if directory is a Python library (not application).

        A directory is a Python library if:
        1. Has __init__.py (package indicator)
        2. Has pyproject.toml OR setup.py OR setup.cfg (packaging)
        3. Does NOT have __main__.py (which would make it an application)
        """
        if not directory.is_dir():
            return False

        init_file = directory / "__init__.py"
        if not init_file.exists():
            return False

        has_packaging = (
            (directory / "pyproject.toml").exists()
            or (directory / "setup.py").exists()
            or (directory / "setup.cfg").exists()
        )

        if not has_packaging:
            return False

        main_file = directory / "__main__.py"
        if main_file.exists():
            return False

        if self._is_excluded_directory(directory):
            return False

        return True

    def _is_excluded_directory(self, directory: Path) -> bool:
        """Check if directory should be excluded (tests, docs, etc.)."""
        dir_parts = set(directory.parts)
        return bool(dir_parts & EXCLUDED_DIRS)

    def _create_library_container(self, project_dir: Path) -> Optional[dict[str, Any]]:
        """Create container dictionary for a Python library.

        Args:
            project_dir: Path to the library directory

        Returns:
            Container dictionary or None
        """
        project_dir = Path(project_dir).resolve()

        rel_path = project_dir.relative_to(self.repo_path)
        rel_path_str = str(rel_path) if rel_path != Path(".") else "."

        container_name = project_dir.name

        if container_name.startswith(".") or container_name.lower() in EXCLUDED_DIRS:
            return None

        container_type = "Python Library"
        protocol = "internal"

        runtime_environment = None
        deployment = None
        dockerfile_path = rel_path / "Dockerfile" if (project_dir / "Dockerfile").exists() else None

        if dockerfile_path:
            runtime_environment = "Container"
            deployment = "Docker"

        owner, team = utils.detect_service_owner(self.repo_path, project_dir)

        container = {
            "c4_level": 2,
            "type": "container",
            "name": container_name,
            "container_type": container_type,
            "technology": "Python",
            "protocol": protocol,
            "path": rel_path_str,
            "runtime_environment": runtime_environment,
            "deployment": deployment,
            "description": utils.extract_container_description(project_dir, self.llm_manager),

            "repository_url": utils.get_repository_url(self.repo_path, project_dir),
            "runtime_info": utils.extract_runtime_version(project_dir),
            "dependencies_internal": [],
            "health_endpoint": None,
            "endpoint": None,
            "dockerfile": str(dockerfile_path) if dockerfile_path else None,
            "terraform": False,
            "helm": False,
            "kubernetes": False,
            "owner": owner,
            "team": team,
            "owner_team": team or owner,
        }

        if not container.get("description"):
            container["description"] = f"Python library {container_name}"

        container["relationships"] = []

        return container
