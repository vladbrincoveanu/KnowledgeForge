"""Structure-based container detector."""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml

from .base_detector import BaseContainerDetector
from . import utils
from .relationship_extractor import ConfigRelationshipExtractor

logger = logging.getLogger(__name__)


class StructureDetector(BaseContainerDetector):
    """Detect containers from repository structure using recursive search.
    
    Recursively searches for framework manifests (Dockerfile, package.json, etc.)
    to identify deployable services. Works with any repository structure:
    - Monorepos (any directory structure)
    - Single service repos
    - Nested structures
    - Custom layouts
    """
    
    def __init__(self, repo_path: Path, llm_manager=None, gitops_paths: Optional[set[str]] = None):
        """Initialize structure detector.
        
        Args:
            repo_path: Path to repository root
            llm_manager: Optional LLM manager for descriptions
            gitops_paths: Set of GitOps-tracked paths
        """
        super().__init__(repo_path)
        self.llm_manager = llm_manager
        self.gitops_paths = gitops_paths or set()
        
        # Framework manifest files that indicate a deployable service
        self.framework_manifests = {
            'Dockerfile',
            'docker-compose.yml',
            'docker-compose.yaml',
            'package.json',
            'pyproject.toml',
            'pom.xml',
            'build.gradle',
            'build.gradle.kts',
            'go.mod',
            'Cargo.toml',
            'requirements.txt',
            'Chart.yaml',
            'kustomization.yaml',
        }
        
        # Excluded directories (not services)
        self.excluded_dirs = {
            '__pycache__', '.git', '.github', '.gitlab', 'node_modules',
            'venv', 'env', '.env', 'dist', 'build', 'target', 'out',
            '.idea', '.vscode', 'logs', 'temp', 'tmp', '.pytest_cache',
            'test', 'tests', '__tests__', 'integration_tests', 'docs', 'documentation',
            '.next', '.nuxt', '.cache', 'coverage', '.coverage',
            # Gradle build infrastructure — never a deployable service
            'buildSrc', 'gradle',
        }

        # How many sibling directories with manifests makes a parent a "collection"
        # (connector repos, plugin directories, etc.) whose children are not C4 containers.
        self._collection_threshold = 3
    
    def can_detect(self) -> bool:
        """Check if structure detection is possible."""
        return True

    def detect(self) -> list[dict[str, Any]]:
        """Detect containers using a depth-1-first / top-down strategy.

        Phase 1: classify each depth-1 directory as a deployable service or
        significant module and register it as a C4 container.  This catches
        top-level SDK/tool directories that have nested manifests rather than
        a manifest at their own root (e.g. airbyte-cdk/, airbyte-ci/).

        Phase 2: recurse into depth-1 grouping dirs (directories that act as
        collection parents for many service sub-directories, like apps/ or
        services/ in a monorepo) and surface their direct children as
        containers using the existing collection-member filter.

        Fallback: if no containers are found, treat the repo root as a single
        service.
        """
        containers: list[dict[str, Any]] = []
        registered_paths: set[str] = set()
        grouping_dirs: list[Path] = []

        # Phase 1: classify depth-1 directories
        try:
            depth1_dirs = sorted(
                d for d in self.repo_path.iterdir()
                if d.is_dir()
                and d.name not in self.excluded_dirs
                and not d.name.startswith('.')
            )
        except OSError:
            depth1_dirs = []

        for d1 in depth1_dirs:
            is_deployable = self._is_deployable_service(d1)
            has_deployable_children = self._has_deployable_children(d1)
            is_significant = self._is_significant_module(d1)
            is_grouping = self._is_grouping_dir(d1)

            # Register as a container only when the directory itself is deployable,
            # OR it has nested manifests but NO deployable immediate children
            # (multi-language SDK like airbyte-cdk whose python/ and java/ subdirs
            # are library packages, not standalone services).
            # Organizational folders like development/ or projects/ that contain
            # actual services as direct children must NOT be registered here — they
            # belong in Phase 2 recursion so the real services surface instead.
            if is_deployable or (is_significant and not has_deployable_children):
                container = self._create_container(d1)
                if container:
                    containers.append(container)
                    registered_paths.add(str(d1.relative_to(self.repo_path)))

            # Recurse in Phase 2 for classic grouping dirs OR folders whose
            # immediate children are deployable services.
            if is_grouping or has_deployable_children:
                grouping_dirs.append(d1)

        # Phase 2: recurse into grouping dirs that were not already registered
        # as Phase 1 containers (a dir can be both significant and a grouping
        # parent; if it is registered as a container we don't recurse inside it).
        grouping_dirs = [
            g for g in grouping_dirs
            if str(g.relative_to(self.repo_path)) not in registered_paths
        ]

        resolved_paths: set[str] = set()
        for grouping_dir in grouping_dirs:
            for root, dirs, files in os.walk(grouping_dir, topdown=True):
                root_path = Path(root)

                dirs[:] = [
                    d for d in dirs
                    if d not in self.excluded_dirs and not d.startswith('.')
                ]

                try:
                    root_rel = root_path.relative_to(self.repo_path)
                except ValueError:
                    root_rel = Path('.')
                dirs[:] = [d for d in dirs if str(root_rel / d) not in registered_paths]

                for file_name in files:
                    if file_name not in self.framework_manifests:
                        continue

                    manifest_file = root_path / file_name
                    service_dir = manifest_file.parent

                    if manifest_file.name == 'Chart.yaml' and service_dir.name in {'chart', 'charts'}:
                        service_dir = service_dir.parent
                    if manifest_file.name == 'kustomization.yaml' and service_dir.name in {'kustomize', 'kustomization'}:
                        service_dir = service_dir.parent

                    try:
                        resolved_service_dir = service_dir.resolve()
                        resolved_rel = str(resolved_service_dir.relative_to(self.repo_path))
                    except (OSError, RuntimeError, ValueError):
                        resolved_rel = str(service_dir)
                    if resolved_rel in resolved_paths:
                        continue
                    resolved_paths.add(resolved_rel)

                    try:
                        rel_path = service_dir.relative_to(self.repo_path)
                    except ValueError:
                        continue
                    if str(rel_path) in registered_paths:
                        continue

                    if self._is_collection_member(service_dir):
                        logger.debug("Skipping collection member: %s", rel_path)
                        continue

                    if self._is_deployable_service(service_dir):
                        container = self._create_container(service_dir)
                        if container:
                            containers.append(container)
                            registered_paths.add(str(rel_path))

        # Fallback: single-service repo
        if not containers:
            if self._is_deployable_service(self.repo_path):
                container = self._create_container(self.repo_path)
                if container:
                    containers.append(container)

        return containers

    def _is_significant_module(self, directory: Path) -> bool:
        """Return True if directory is a meaningful top-level module.

        A directory is significant if it contains at least one framework manifest
        nested within it.  Known build-infrastructure directories (buildSrc, gradle,
        etc.) are already excluded before this method is reached.
        """
        return self._has_nested_manifest(directory, max_depth=3)

    def _is_grouping_dir(self, directory: Path) -> bool:
        """Return True if directory is a collection parent for many service subdirs.

        A grouping dir has >= _collection_threshold direct child directories
        that each contain at least one framework manifest within depth 2.
        These are recursed into in Phase 2 to surface nested services.
        """
        count = 0
        try:
            for child in directory.iterdir():
                if (not child.is_dir()
                        or child.name in self.excluded_dirs
                        or child.name.startswith('.')):
                    continue
                if self._has_nested_manifest(child, max_depth=2):
                    count += 1
                    if count >= self._collection_threshold:
                        return True
        except OSError:
            pass
        return False

    def _has_deployable_children(self, directory: Path) -> bool:
        """Return True if any immediate child directory is a deployable service."""
        try:
            for child in directory.iterdir():
                if (child.is_dir()
                        and not child.name.startswith('.')
                        and child.name not in self.excluded_dirs
                        and self._is_deployable_service(child)):
                    return True
        except OSError:
            pass
        return False

    def _has_nested_manifest(self, directory: Path, max_depth: int = 3) -> bool:
        """Return True if any framework manifest exists within max_depth directory levels."""
        return self._search_nested(directory, self.framework_manifests, max_depth, check_name=True)

    def _search_nested(
        self,
        directory: Path,
        targets: set[str],
        max_depth: int,
        check_name: bool,
        _depth: int = 0,
    ) -> bool:
        """Recursively search for target files within max_depth directory levels."""
        if _depth > max_depth:
            return False
        try:
            for child in directory.iterdir():
                if child.is_file():
                    if (child.name if check_name else child.suffix) in targets:
                        return True
                elif (child.is_dir()
                      and child.name not in self.excluded_dirs
                      and not child.name.startswith('.')):
                    if self._search_nested(child, targets, max_depth, check_name, _depth + 1):
                        return True
        except OSError:
            pass
        return False

    def _is_collection_member(self, service_dir: Path) -> bool:
        """Return True when service_dir is part of a collection tree.

        Walks upward from service_dir to the repo root.  At each level,
        counts how many siblings (directories at the same level) carry at
        least one framework manifest directly inside them.  If any level
        reaches _collection_threshold, the directory is a collection member
        (connector, plugin, base-image tree, etc.) and should not be a
        standalone C4 container.

        Direct children of the repo root are always exempt.
        """
        if service_dir.parent == self.repo_path:
            return False  # depth-1 dirs are always real service candidates

        current = service_dir
        while True:
            parent = current.parent
            if parent == self.repo_path:
                break  # reached root — direct children exempt
            if parent.parent == self.repo_path:
                break  # parent is a depth-1 dir — don't conflate its siblings with a collection

            sibling_count = 0
            try:
                for child in parent.iterdir():
                    if not child.is_dir() or child == current:
                        continue
                    if any((child / m).exists() for m in self.framework_manifests):
                        sibling_count += 1
                        if sibling_count >= self._collection_threshold:
                            return True
            except OSError:
                pass

            current = parent

        return False

    def _is_infrastructure_only(self, project_dir: Path) -> bool:
        """Return True when the directory contains only IaC files with no application code.

        Infrastructure-only = has IaC signals (.tf / Chart.yaml / kustomization.yaml)
        AND no app framework manifests (Dockerfile, package.json, pom.xml, go.mod, …)
        AND no app source files (*.py, *.js, *.ts, *.java, *.go, *.cs, *.rs, *.rb).
        """
        _APP_EXTENSIONS = {'.py', '.js', '.ts', '.java', '.go', '.cs', '.rs', '.rb'}
        _APP_MANIFESTS = {
            'Dockerfile', 'package.json', 'pom.xml', 'go.mod',
            'requirements.txt', 'pyproject.toml', 'Cargo.toml',
            'build.gradle', 'build.gradle.kts',
        }

        has_iac = (
            bool(list(project_dir.glob('*.tf')))
            or (project_dir / 'Chart.yaml').exists()
            or (project_dir / 'chart' / 'Chart.yaml').exists()
            or (project_dir / 'kustomization.yaml').exists()
            or (project_dir / 'kustomize' / 'kustomization.yaml').exists()
        )
        if not has_iac:
            return False

        for manifest in _APP_MANIFESTS:
            if (project_dir / manifest).exists():
                return False

        if list(project_dir.glob('*.csproj')) or list(project_dir.glob('*.sln')):
            return False

        for f in project_dir.iterdir():
            if f.is_file() and f.suffix in _APP_EXTENSIONS:
                return False

        return True

    def _is_deployable_service(self, directory: Path) -> bool:
        """Check if directory contains a deployable service.
        
        Checks for framework manifest files that indicate a deployable unit.
        """
        return utils.is_deployable_service(directory)
    
    def _create_container(self, project_dir: Path) -> Optional[dict[str, Any]]:
        """Create container dictionary from project directory.
        
        Args:
            project_dir: Path to container directory (absolute or relative)
            
        Returns:
            Container dictionary or None if directory should be skipped
        """
        # Ensure absolute path
        project_dir = Path(project_dir).resolve()

        # Avoid registering repo root in multi-service repos
        if project_dir == self.repo_path:
            common_service_dirs = {'projects', 'services', 'apps', 'packages', 'components', 'bases'}
            if any((self.repo_path / d).exists() for d in common_service_dirs):
                return None
        
        # Get relative path from repo root (standardized)
        rel_path = project_dir.relative_to(self.repo_path)
        rel_path_str = str(rel_path) if rel_path != Path('.') else "."
        
        # Generate container name
        container_name = project_dir.name if project_dir != self.repo_path else self.repo_path.name
        
        # Filter out non-service directories
        if container_name.lower() in self.excluded_dirs or container_name.startswith('.'):
            return None
        
        container_type = utils.infer_container_type(project_dir)
        protocol = utils.infer_protocol(project_dir)

        runtime_environment = None
        deployment = None
        dockerfile_path = rel_path / "Dockerfile" if (project_dir / "Dockerfile").exists() else None
        has_terraform = bool(list(project_dir.glob("*.tf")))
        has_helm = (project_dir / "chart" / "Chart.yaml").exists() or (project_dir / "Chart.yaml").exists()
        has_kubernetes = self._directory_has_k8s_manifest(project_dir)
        if (project_dir / "chart" / "Chart.yaml").exists():
            runtime_environment = "Kubernetes"
            deployment = "Helm"
        elif (project_dir / "kustomize" / "kustomization.yaml").exists():
            runtime_environment = "Kubernetes"
            deployment = "Kustomize"
        elif has_kubernetes:
            runtime_environment = "Kubernetes"
            deployment = "Manifest"
        elif self._path_matches_gitops(rel_path_str):
            runtime_environment = "Kubernetes"
            deployment = "GitOps"

        owner, team = utils.detect_service_owner(self.repo_path, project_dir)
        
        container = {
            "c4_level": 2,
            "type": "container",
            "name": container_name,
            "container_type": container_type,
            "technology": utils.detect_technology_stack(project_dir),
            "protocol": protocol,
            "path": rel_path_str,  # Always relative to repo root
            "runtime_environment": runtime_environment,
            "deployment": deployment,
            "description": utils.extract_container_description(project_dir, self.llm_manager),
            
            # IT Landscape fields
            "repository_url": utils.get_repository_url(self.repo_path, project_dir),
            "runtime_info": utils.extract_runtime_version(project_dir),
            "dependencies_internal": [],  # Will be populated later
            "health_endpoint": utils.extract_health_endpoint(project_dir),
            "endpoint": utils.extract_service_endpoint(project_dir),
            "dockerfile": str(dockerfile_path) if dockerfile_path else None,
            "terraform": has_terraform,
            "helm": has_helm,
            "kubernetes": runtime_environment == "Kubernetes" or has_kubernetes,
            "owner": owner,
            "team": team,
            "owner_team": team or owner,
        }

        if not container.get("description") and runtime_environment:
            deployment_label = deployment or "Kubernetes"
            container["description"] = (
                f"Kubernetes workload deployed via {deployment_label}."
            )

        if self._is_infrastructure_only(project_dir):
            container["is_infrastructure_only"] = True

        container["relationships"] = ConfigRelationshipExtractor(container_name).extract_from_directory(project_dir)

        return container
    
    def _path_matches_gitops(self, rel_path: str) -> bool:
        """Check if a container path is referenced by GitOps application paths."""
        if not rel_path or not self.gitops_paths:
            return False

        rel_path = rel_path.strip("/ ")
        for gitops_path in self.gitops_paths:
            if rel_path == gitops_path:
                return True
            if rel_path.startswith(gitops_path + "/"):
                return True
            if gitops_path.startswith(rel_path + "/"):
                return True
        return False
    
    def _directory_has_k8s_manifest(self, directory: Path) -> bool:
        """Detect Kubernetes manifests by apiVersion/kind patterns."""
        k8s_kinds = {
            "deployment",
            "statefulset",
            "daemonset",
            "service",
            "ingress",
            "job",
            "cronjob",
        }

        for yaml_file in directory.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(5000)

                if "apiVersion:" not in content:
                    continue

                docs = list(yaml.safe_load_all(content))
                for doc in docs:
                    if isinstance(doc, dict):
                        kind = str(doc.get("kind", "")).lower()
                        if kind in k8s_kinds:
                            return True
            except Exception:
                continue

        return False
