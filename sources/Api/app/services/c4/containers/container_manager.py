"""Container manager for Level 2 C4 Model extraction."""

import logging
import re
from pathlib import Path
from typing import Any, Optional, Tuple

import yaml

from . import utils

from .structure_detector import StructureDetector
from .compose_detector import ComposeDetector
from .helm_detector import HelmDetector
from .terraform_detector import TerraformDetector

logger = logging.getLogger(__name__)


class ContainerManager:
    """Manages container detection and registration for C4 Level 2."""
    
    def __init__(self, repo_path: Path, llm_manager=None):
        """Initialize container manager.
        
        Args:
            repo_path: Path to repository root
            llm_manager: Optional LLM manager for descriptions
        """
        self.repo_path = Path(repo_path).resolve()
        self.llm_manager = llm_manager
        self.containers = {}  # name -> container dict
        
        # Detect GitOps paths first (needed for structure detector)
        self.gitops_paths = self._detect_gitops_paths()
        
        # Initialize detectors
        self.detectors = [
            StructureDetector(self.repo_path, llm_manager, self.gitops_paths),
            ComposeDetector(self.repo_path),
            HelmDetector(self.repo_path, llm_manager),
            TerraformDetector(self.repo_path),
        ]
    
    def detect_all_containers(self) -> dict[str, dict[str, Any]]:
        """Run all container detectors and merge results.
        
        Returns:
            Dictionary of container_name -> container_data
        """
        logger.info("Starting container detection...")
        
        # Run structure detection first (base containers)
        structure_detector = self.detectors[0]
        structure_containers = structure_detector.detect()
        for container in structure_containers:
            if container:
                self._register_or_merge_container(container, source="structure")
        
        # Run compose detection (may add new containers or enrich existing)
        compose_detector = self.detectors[1]
        if compose_detector.can_detect():
            compose_containers = compose_detector.detect()
            for container in compose_containers:
                self._register_or_merge_container(container, source="compose")
        
        # Run Helm detection (merge with existing containers)
        helm_detector = self.detectors[2]
        if helm_detector.can_detect():
            helm_containers = helm_detector.detect()
            for container in helm_containers:
                self._merge_helm_container(container)

        # Run Terraform detection (passive containers)
        terraform_detector = self.detectors[3]
        if terraform_detector.can_detect():
            terraform_containers = terraform_detector.detect()
            for container in terraform_containers:
                self._register_or_merge_container(container, source="terraform")
        
        # Map internal dependencies
        self._map_internal_dependencies()
        
        logger.info(f"Container detection complete. Found {len(self.containers)} containers.")
        return self.containers
    
    def _register_or_merge_container(self, container: dict[str, Any], source: str) -> None:
        """Register a new container or merge if an identity match exists."""
        name = container.get('name')
        if not name:
            return

        existing_key, existing = self._find_existing_container(container)
        if not existing:
            self.containers[name] = container
            return

        self._merge_container_data(existing, container)
        if source == "helm":
            self._apply_helm_overrides(existing, container)
    
    def _merge_helm_container(self, helm_container: dict[str, Any]) -> None:
        """Merge Helm container info with existing containers."""
        existing_key, existing = self._find_existing_container(helm_container)
        if not existing:
            self.containers[helm_container.get('name')] = helm_container
            return

        self._merge_container_data(existing, helm_container)
        self._apply_helm_overrides(existing, helm_container)

    def _merge_container_data(self, existing: dict[str, Any], incoming: dict[str, Any]) -> None:
        """Merge incoming container data into existing without overwriting truthy values."""
        for key, value in incoming.items():
            if value and not existing.get(key):
                existing[key] = value

    def _apply_helm_overrides(self, existing: dict[str, Any], helm_container: dict[str, Any]) -> None:
        """Apply Helm-specific fields to an existing container."""
        rel_service_path = helm_container.get('path')
        if existing.get("container_type") in {"Service", "Unknown", None}:
            existing["container_type"] = "Helm Deployed Service"
        if existing.get("technology") in {"Unknown", None}:
            existing["technology"] = "Kubernetes"
        if not existing.get("protocol"):
            existing["protocol"] = "HTTP"
        if existing.get("path") in {".", ""}:
            existing["path"] = rel_service_path
        existing["runtime_environment"] = "Kubernetes"
        existing["deployment"] = "Helm"
        if not existing.get("description"):
            existing["description"] = helm_container.get("description", "")
        if not existing.get("description"):
            existing["description"] = "Kubernetes workload deployed via Helm."

    def _find_existing_container(self, container: dict[str, Any]) -> Tuple[Optional[str], Optional[dict[str, Any]]]:
        """Find an existing container by identity-based matching."""
        incoming_slugs = self._get_container_slugs(container)
        incoming_path = container.get("path")

        for key, existing in self.containers.items():
            if incoming_path and existing.get("path") == incoming_path:
                return key, existing
            existing_slugs = self._get_container_slugs(existing)
            if incoming_slugs & existing_slugs:
                return key, existing

        return None, None

    def _get_container_slugs(self, container: dict[str, Any]) -> set[str]:
        """Build identity slugs from container name, path, and parent directory."""
        slugs: set[str] = set()
        name = container.get("name")
        path = container.get("path")
        generic_parents = {"projects", "services", "apps", "packages", "components", "bases"}

        if name:
            slugs.add(self._slugify(name))

        if path:
            slugs.add(self._slugify(path))
            path_obj = Path(path)
            slugs.add(self._slugify(path_obj.name))
            if path_obj.parent and str(path_obj.parent) not in {".", ""}:
                parent_name = path_obj.parent.name
                if parent_name and parent_name.lower() not in generic_parents:
                    slugs.add(self._slugify(parent_name))

        return {s for s in slugs if s}

    def _slugify(self, value: str) -> str:
        """Normalize names/paths to a slug for identity matching."""
        normalized = value.strip().lower()
        normalized = normalized.replace("/", "-").replace("\\", "-")
        normalized = re.sub(r"[\s_]+", "-", normalized)
        normalized = re.sub(r"[^a-z0-9-]", "", normalized)
        normalized = re.sub(r"-+", "-", normalized)
        return normalized.strip("-")
    
    def _map_internal_dependencies(self) -> None:
        """Map dependencies between containers based on Helm charts and env references."""
        for container in self.containers.values():
            chart_path = self.repo_path / container['path'] / 'Chart.yaml'
            if chart_path.exists():
                try:
                    with open(chart_path, 'r') as f:
                        chart_data = yaml.safe_load(f)
                        if 'dependencies' in chart_data:
                            for dep in chart_data['dependencies']:
                                dep_name = dep['name']
                                if dep_name in self.containers and dep_name != container['name']:
                                    container.setdefault('dependencies_internal', []).append(dep_name)
                except Exception as e:
                    logger.warning(f"Could not parse {chart_path}: {e}")

        self._discover_runtime_dependencies()

    def _discover_runtime_dependencies(self) -> None:
        """Discover internal dependencies from compose, k8s manifests, and env files."""
        files = []
        files.extend(self.repo_path.rglob("docker-compose*.yml"))
        files.extend(self.repo_path.rglob("docker-compose*.yaml"))
        files.extend(self.repo_path.rglob("*.env"))
        files.extend(self.repo_path.rglob(".env*"))
        files.extend(self.repo_path.rglob("*.yml"))
        files.extend(self.repo_path.rglob("*.yaml"))

        for file_path in files:
            if not file_path.is_file():
                continue

            container_name = self._resolve_container_for_path(file_path)
            if not container_name:
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            refs = utils.extract_internal_service_refs(content)
            for token in refs:
                target_name = self._resolve_container_by_token(token)
                if not target_name or target_name == container_name:
                    continue
                self.containers[container_name].setdefault("dependencies_internal", []).append(target_name)

        for container in self.containers.values():
            deps = container.get("dependencies_internal")
            if deps:
                container["dependencies_internal"] = sorted(set(deps))

    def _resolve_container_by_token(self, token: str) -> Optional[str]:
        """Resolve a token to a known container name by slug matching."""
        token_slug = self._slugify(token)
        if not token_slug:
            return None

        for name, container in self.containers.items():
            if token_slug in self._get_container_slugs(container):
                return name
        return None

    def _resolve_container_for_path(self, file_path: Path) -> Optional[str]:
        """Find the owning container for a file based on its path."""
        try:
            rel_path = file_path.relative_to(self.repo_path)
        except Exception:
            return None

        rel_path_str = str(rel_path)
        for name, container in self.containers.items():
            container_path = container.get("path")
            if not container_path or container_path in {".", ""}:
                continue
            if rel_path_str.startswith(container_path):
                return name

        root_container = next(
            (c['name'] for c in self.containers.values() if c.get('path') in {'.', ''}),
            None
        )
        return root_container
    
    def build_container_relationships(self) -> list[dict[str, Any]]:
        """Build relationships between containers for C4 diagram.
        
        Returns:
            List of relationship dictionaries
        """
        relationships = []
        
        for container_name, container in self.containers.items():
            deps = container.get('dependencies_internal', [])
            for dep_name in deps:
                if dep_name in self.containers:
                    relationships.append({
                        "from": container_name,
                        "to": dep_name,
                        "type": "uses",
                        "protocol": container.get('protocol', 'HTTP'),
                    })
        
        return relationships
    
    def _detect_gitops_paths(self) -> set[str]:
        """Detect GitOps/ArgoCD application paths that imply Kubernetes deployment."""
        gitops_paths: set[str] = set()

        # Only scan YAML in likely GitOps folders to keep it cheap
        candidate_dirs = [
            self.repo_path / "gitops",
            self.repo_path / "argo",
            self.repo_path / "argocd",
        ]

        for base_dir in candidate_dirs:
            if not base_dir.exists():
                continue

            for yaml_file in base_dir.rglob("*.y*ml"):
                try:
                    with open(yaml_file, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(20000)

                    if "argoproj.io" not in content and "Application" not in content:
                        continue

                    docs = list(yaml.safe_load_all(content))
                    for doc in docs:
                        if not isinstance(doc, dict):
                            continue

                        kind = str(doc.get("kind", ""))
                        if kind not in {"Application", "ApplicationSet"}:
                            continue

                        # Application spec
                        spec = doc.get("spec", {})
                        self._collect_gitops_paths_from_spec(spec, gitops_paths)

                        # ApplicationSet template spec
                        template = spec.get("template", {}) if isinstance(spec, dict) else {}
                        template_spec = template.get("spec", {}) if isinstance(template, dict) else {}
                        self._collect_gitops_paths_from_spec(template_spec, gitops_paths)
                except Exception:
                    continue

        return {p.strip("/ ") for p in gitops_paths if p}
    
    def _collect_gitops_paths_from_spec(self, spec: dict, gitops_paths: set[str]):
        """Collect source paths from ArgoCD Application specs."""
        if not isinstance(spec, dict):
            return

        source = spec.get("source")
        if isinstance(source, dict):
            path = source.get("path")
            if isinstance(path, str):
                gitops_paths.add(path)

        sources = spec.get("sources")
        if isinstance(sources, list):
            for src in sources:
                if isinstance(src, dict):
                    path = src.get("path")
                    if isinstance(path, str):
                        gitops_paths.add(path)
    
    def detect_cluster_metadata(self) -> dict[str, Any]:
        """Detect cluster metadata from GitOps configurations."""
        metadata = {}
        
        gitops_files = []
        for gitops_dir in ["gitops", "argo", "argocd"]:
            gitops_path = self.repo_path / gitops_dir
            if gitops_path.exists():
                gitops_files.extend([str(f.relative_to(self.repo_path)) for f in gitops_path.rglob("*.y*ml")])
        
        if gitops_files:
            metadata["gitops_files_count"] = len(gitops_files)
            metadata["gitops_directories"] = list(set([str(Path(f).parent) for f in gitops_files]))
        
        return metadata
