"""Container manager for Level 2 C4 Model extraction."""

import logging
from pathlib import Path
from typing import Any

import yaml

from .structure_detector import StructureDetector
from .compose_detector import ComposeDetector
from .helm_detector import HelmDetector

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
                self._register_container(container)
        
        # Run compose detection (may add new containers or enrich existing)
        compose_detector = self.detectors[1]
        if compose_detector.can_detect():
            compose_containers = compose_detector.detect()
            for container in compose_containers:
                self._register_or_merge_container(container)
        
        # Run Helm detection (merge with existing containers)
        helm_detector = self.detectors[2]
        if helm_detector.can_detect():
            helm_containers = helm_detector.detect()
            for container in helm_containers:
                self._merge_helm_container(container)
        
        # Map internal dependencies
        self._map_internal_dependencies()
        
        logger.info(f"Container detection complete. Found {len(self.containers)} containers.")
        return self.containers
    
    def _register_container(self, container: dict[str, Any]) -> None:
        """Register a new container."""
        name = container.get('name')
        if name and name not in self.containers:
            self.containers[name] = container
    
    def _register_or_merge_container(self, container: dict[str, Any]) -> None:
        """Register a new container or merge if exists."""
        name = container.get('name')
        if not name:
            return
        
        if name not in self.containers:
            self.containers[name] = container
        else:
            # Container exists, merge information
            existing = self.containers[name]
            # Don't overwrite existing fields with empty/None values
            for key, value in container.items():
                if value and not existing.get(key):
                    existing[key] = value
    
    def _merge_helm_container(self, helm_container: dict[str, Any]) -> None:
        """Merge Helm container info with existing containers."""
        chart_name = helm_container.get('name')
        rel_service_path = helm_container.get('path')
        
        # Try to find an existing container by path or name variants
        existing = None
        existing_key = None

        for key, container in self.containers.items():
            if container.get('path') == rel_service_path:
                existing = container
                existing_key = key
                break

        if not existing and chart_name:
            candidate_names = {
                chart_name,
                chart_name.replace('-', '_'),
                chart_name.replace('_', '-'),
            }
            for name in candidate_names:
                if name in self.containers:
                    existing = self.containers[name]
                    existing_key = name
                    break

        if not existing:
            # Register as new container
            self.containers[chart_name] = helm_container
        else:
            # Merge Helm info into existing container
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
    
    def _map_internal_dependencies(self) -> None:
        """Map dependencies between containers based on Helm charts."""
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
