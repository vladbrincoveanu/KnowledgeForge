"""Structure-based container detector."""

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from .base_detector import BaseContainerDetector
from . import utils

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
            'test', 'tests', '__tests__', 'docs', 'documentation',
            '.next', '.nuxt', '.cache', 'coverage', '.coverage',
        }
    
    def can_detect(self) -> bool:
        """Check if structure detection is possible."""
        # Structure detection always runs as fallback
        return True
    
    def detect(self) -> list[dict[str, Any]]:
        """Detect containers from project structure."""
        containers = []
        registered_paths = set()
        
        # Recursively search for framework manifests
        for manifest_file in self.repo_path.rglob("*"):
            if not manifest_file.is_file():
                continue
            
            # Check if this is a framework manifest
            if manifest_file.name not in self.framework_manifests:
                continue
            
            # Get the directory containing this manifest
            service_dir = manifest_file.parent

            # Normalize Helm chart/kustomize layouts (chart folder -> parent service)
            if manifest_file.name == 'Chart.yaml' and service_dir.name in {'chart', 'charts'}:
                service_dir = service_dir.parent
            if manifest_file.name == 'kustomization.yaml' and service_dir.name in {'kustomize', 'kustomization'}:
                service_dir = service_dir.parent
            
            # Skip if in excluded directory
            if any(excluded in service_dir.parts for excluded in self.excluded_dirs):
                continue
            
            # Skip if already registered
            rel_path = service_dir.relative_to(self.repo_path)
            if str(rel_path) in registered_paths:
                continue
            
            # Check if this directory looks like a deployable service
            if self._is_deployable_service(service_dir):
                container = self._create_container(service_dir)
                if container:  # Only add if not None
                    containers.append(container)
                    registered_paths.add(str(rel_path))
        
        # Fallback: If no containers found, check if root is a service
        if not containers:
            if self._is_deployable_service(self.repo_path):
                container = self._create_container(self.repo_path)
                if container:  # Only add if not None
                    containers.append(container)
        
        return containers
    
    def _is_deployable_service(self, directory: Path) -> bool:
        """Check if directory contains a deployable service.
        
        Checks for framework manifest files that indicate a deployable unit.
        """
        # Check for any framework manifest
        for manifest in self.framework_manifests:
            manifest_path = directory / manifest
            if manifest_path.exists():
                return True
        
        # Also check for chart subdirectory (Helm)
        if (directory / "chart" / "Chart.yaml").exists():
            return True

        # Check for kustomize subdirectory
        if (directory / "kustomize" / "kustomization.yaml").exists():
            return True
        
        return False
    
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
        if (project_dir / "chart" / "Chart.yaml").exists():
            runtime_environment = "Kubernetes"
            deployment = "Helm"
        elif (project_dir / "kustomize" / "kustomization.yaml").exists():
            runtime_environment = "Kubernetes"
            deployment = "Kustomize"
        elif self._directory_has_k8s_manifest(project_dir):
            runtime_environment = "Kubernetes"
            deployment = "Manifest"
        elif self._path_matches_gitops(rel_path_str):
            runtime_environment = "Kubernetes"
            deployment = "GitOps"
        
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
        }

        if not container.get("description") and runtime_environment:
            deployment_label = deployment or "Kubernetes"
            container["description"] = (
                f"Kubernetes workload deployed via {deployment_label}."
            )
        
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
