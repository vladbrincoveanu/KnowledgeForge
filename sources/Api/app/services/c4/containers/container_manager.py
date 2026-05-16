"""Container manager for Level 2 C4 Model extraction."""

import logging
import re
from pathlib import Path
from typing import Any, Optional, Tuple

import yaml

from . import utils
from app.services.c4.context.decision_models import C4ElementType
from .c4_types import C4ContainerType, classify_c4_container_type
from .llm_enrichment import enrich_containers

from .structure_detector import StructureDetector
from .compose_detector import ComposeDetector
from .helm_detector import HelmDetector
from .terraform_detector import TerraformDetector
from .kubernetes_detector import KubernetesDetector
from .python_library_detector import PythonLibraryDetector
from .relationship_extractor import ConfigRelationshipExtractor

logger = logging.getLogger(__name__)


def _deduplicate_relationships(rels: list[dict]) -> list[dict]:
    """Remove duplicate relationships by (to, type, protocol) key."""
    seen: set[tuple] = set()
    unique: list[dict] = []
    for r in rels:
        key = (r.get("to"), r.get("type"), r.get("protocol"))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


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
            KubernetesDetector(self.repo_path),
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

        # Run Kubernetes detection (raw manifests and Kustomize)
        kubernetes_detector = self.detectors[4]
        if kubernetes_detector.can_detect():
            kubernetes_containers = kubernetes_detector.detect()
            for container in kubernetes_containers:
                self._merge_kubernetes_container(container)

        # Run Python library detection (finds packages without __main__.py)
        python_library_detector = PythonLibraryDetector(self.repo_path, self.llm_manager)
        if python_library_detector.can_detect():
            library_containers = python_library_detector.detect()
            for container in library_containers:
                self._register_or_merge_container(container, source="python_library")

        # Map internal dependencies
        self._map_internal_dependencies()
        self._match_topic_producers_consumers()

        # Drop root-level structure placeholders when real compose/helm services exist.
        # The structure detector registers the repo root (path=".") as a container when
        # it finds a docker-compose.yml there, but the compose detector then registers
        # the actual services. Keep the root placeholder only if it's the sole container.
        self._drop_redundant_root_containers()

        logger.info(f"Container detection complete. Found {len(self.containers)} containers.")
        return self.containers

    def enrich_containers_with_llm(self) -> dict[str, Any]:
        """Run LLM enrichment as a second pass after rule-based detection.

        Must be called after detect_all_containers().  Updates self.containers
        in-place and returns enrichment stats.

        Returns:
            Stats dict from enrich_containers(): enriched, discarded,
            inferred_relationships, skipped, error.
        """
        if not self.containers:
            return {"enriched": 0, "discarded": 0, "inferred_relationships": 0,
                    "skipped": True, "error": None}

        # Build current relationships so the LLM can see existing signals
        current_rels = self.build_container_relationships()
        stats = enrich_containers(self.containers, current_rels, self.llm_manager)
        logger.info("LLM enrichment stats: %s", stats)
        return stats
    
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

    def _merge_kubernetes_container(self, k8s_container: dict[str, Any]) -> None:
        """Merge Kubernetes container info with an existing container.

        - Preserves the existing container's name, path, and structure-derived fields.
        - Appends K8s relationships to the existing relationships list.
        - Fills in missing or generic fields (container_type, technology, protocol)
          from K8s data only when the existing values are empty or generic placeholders.
        """
        existing_key, existing = self._find_existing_container(k8s_container)
        if not existing:
            self.containers[k8s_container.get('name')] = k8s_container
            return

        # Append K8s-extracted relationships rather than replacing, then deduplicate.
        k8s_rels = k8s_container.get("relationships") or []
        if k8s_rels:
            existing.setdefault("relationships", []).extend(k8s_rels)
            existing["relationships"] = _deduplicate_relationships(existing["relationships"])

        # Overwrite generic placeholder values with K8s-derived specifics.
        _generic_type = {"Service", "Unknown", None}
        _generic_tech = {"Unknown", None}
        if existing.get("container_type") in _generic_type:
            incoming_type = k8s_container.get("container_type")
            if incoming_type and incoming_type not in _generic_type:
                existing["container_type"] = incoming_type
        if existing.get("technology") in _generic_tech:
            incoming_tech = k8s_container.get("technology")
            if incoming_tech and incoming_tech not in _generic_tech:
                existing["technology"] = incoming_tech
        if not existing.get("protocol") and k8s_container.get("protocol"):
            existing["protocol"] = k8s_container["protocol"]

        # Copy K8s-only metadata fields not present on the existing container.
        for key in ("runtime_environment", "deployment", "kubernetes_kind",
                    "kubernetes_namespace", "health_endpoint"):
            if not existing.get(key) and k8s_container.get(key):
                existing[key] = k8s_container[key]

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

        # Don't use path-based matching for files that define multiple containers
        # (docker-compose, helm values) — every service in the file shares the same path.
        _multi_container_files = ("docker-compose", "values.yaml", "kustomize")
        use_path_match = incoming_path and not any(
            p in str(incoming_path) for p in _multi_container_files
        )

        for key, existing in self.containers.items():
            if use_path_match and existing.get("path") == incoming_path:
                return key, existing
            existing_slugs = self._get_container_slugs(existing)
            if incoming_slugs & existing_slugs:
                return key, existing

        # Suffix containment fallback: handles K8s metadata.name being a shortened
        # form of the repo directory name (universal K8s convention — teams strip org
        # prefixes). Only compare name slugs; path slugs overlap for unrelated reasons.
        incoming_name = container.get("name")
        if incoming_name:
            incoming_name_slug = self._slugify(incoming_name)
            for key, existing in self.containers.items():
                existing_name = existing.get("name")
                if not existing_name:
                    continue
                existing_name_slug = self._slugify(existing_name)
                longer, shorter = (
                    (incoming_name_slug, existing_name_slug)
                    if len(incoming_name_slug) >= len(existing_name_slug)
                    else (existing_name_slug, incoming_name_slug)
                )
                if not longer.endswith(shorter):
                    continue
                # Require the shorter slug to be substantial to avoid false matches
                # (e.g. "api" matching "my-org-api-gateway").
                segments = shorter.split("-")
                if len(segments) >= 3 or len(shorter) >= 10:
                    return key, existing

        return None, None

    # Paths that define multiple containers — excluded from identity slugs
    _MULTI_CONTAINER_PATHS = ("docker-compose", "values.yaml", "kustomization.yaml", "kustomize")

    def _get_container_slugs(self, container: dict[str, Any]) -> set[str]:
        """Build identity slugs from container name, path, and parent directory."""
        slugs: set[str] = set()
        name = container.get("name")
        path = container.get("path")
        generic_parents = {"projects", "services", "apps", "packages", "components", "bases"}

        if name:
            slugs.add(self._slugify(name))

        # Skip path-derived slugs for files that define multiple containers —
        # every service in the file shares the same path, causing false merges.
        if path and not any(p in str(path) for p in self._MULTI_CONTAINER_PATHS):
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
        """Discover internal dependencies from compose, k8s manifests, and config files.

        Phase 1: structured config files (appsettings.json, application.yml, .env, …)
                 processed via ConfigRelationshipExtractor → stored as rich relationships.
        Phase 2: unstructured YAML files (docker-compose, generic manifests) use
                 extract_internal_service_refs() as a fallback → stored as
                 dependencies_internal.
        """
        # Phase 1: structured config files per container directory
        # Skip containers that already have config-extracted relationships
        # (e.g., from StructureDetector) to avoid duplicates.
        for container_name, container in self.containers.items():
            if container.get("relationships"):
                continue
            container_path = container.get("path")
            if not container_path or container_path in {".", ""}:
                continue
            project_dir = self.repo_path / container_path
            if not project_dir.is_dir():
                continue
            try:
                rels = ConfigRelationshipExtractor(container_name).extract_from_directory(project_dir)
                if rels:
                    container.setdefault("relationships", []).extend(rels)
            except Exception as e:
                logger.debug("ConfigRelationshipExtractor failed for %s: %s", container_name, e)

        # Phase 2: fallback for unstructured YAML files
        unstructured_files: list[Path] = []
        unstructured_files.extend(self.repo_path.rglob("docker-compose*.yml"))
        unstructured_files.extend(self.repo_path.rglob("docker-compose*.yaml"))
        unstructured_files.extend(self.repo_path.rglob("*.yml"))
        unstructured_files.extend(self.repo_path.rglob("*.yaml"))

        for file_path in unstructured_files:
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

    def _match_topic_producers_consumers(self) -> None:
        """Create explicit cross-container relationships for shared messaging topics/queues.

        Scans all container relationships for those with metadata.topic or metadata.queue,
        groups publishers (type="publishes-to") and subscribers (type="subscribes-to") by
        topic name, then creates a direct publisher → subscriber relationship that
        references the broker as intermediary.
        """
        from collections import defaultdict

        # topic_name → {"publishers": [container_name], "subscribers": [container_name], "broker": str|None}
        topics: dict[str, dict] = defaultdict(lambda: {"publishers": [], "subscribers": [], "broker": None})

        for container_name, container in self.containers.items():
            for rel in container.get("relationships", []):
                metadata = rel.get("metadata") or {}
                topic_name = metadata.get("topic") or metadata.get("queue")
                if not topic_name:
                    continue

                rel_type = rel.get("type", "")
                broker = rel.get("to") or None

                if rel_type == "publishes-to":
                    topics[topic_name]["publishers"].append(container_name)
                    if broker and not topics[topic_name]["broker"]:
                        topics[topic_name]["broker"] = broker
                elif rel_type == "subscribes-to":
                    topics[topic_name]["subscribers"].append(container_name)
                    if broker and not topics[topic_name]["broker"]:
                        topics[topic_name]["broker"] = broker

        for topic_name, info in topics.items():
            publishers = info["publishers"]
            subscribers = info["subscribers"]
            broker = info["broker"]

            if not publishers or not subscribers:
                continue

            for publisher in publishers:
                if publisher not in self.containers:
                    continue
                for subscriber in subscribers:
                    if subscriber not in self.containers or subscriber == publisher:
                        continue

                    via = broker or topic_name
                    rel = {
                        "from": publisher,
                        "to": subscriber,
                        "type": "async",
                        "protocol": "messaging",
                        "source": "topic-match",
                        "description": f"{publisher} sends to {subscriber} via {via}",
                        "metadata": {"topic": topic_name, "broker": broker},
                    }
                    self.containers[publisher].setdefault("relationships", []).append(rel)

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
        """Build C4 container relationships, preferring detector-extracted rich data.

        Phase 1: harvest 'relationships' lists embedded by each detector.
        Phase 2: legacy fallback via 'dependencies_internal' for containers
                 that have no detector-level relationships.
        """
        seen: set[tuple] = set()
        result: list[dict] = []

        # Phase 1: richer detector-extracted relationships
        for container_name, container in self.containers.items():
            for rel in container.get("relationships", []):
                resolved = self._resolve_relationship(rel, container_name)
                if not resolved:
                    continue
                key = (resolved["from"], resolved["to"], resolved.get("type", ""), resolved.get("protocol", ""))
                if key not in seen:
                    seen.add(key)
                    result.append(resolved)

        # Phase 2: legacy fallback for containers with no detector-level rels
        containers_with_rels = {r["from"] for r in result}
        for container_name, container in self.containers.items():
            if container_name in containers_with_rels:
                continue
            for dep_name in container.get("dependencies_internal", []):
                if dep_name not in self.containers:
                    continue
                key = (container_name, dep_name, "uses", "")
                if key not in seen:
                    seen.add(key)
                    result.append({
                        "from": container_name,
                        "to": dep_name,
                        "type": "uses",
                        "protocol": container.get("protocol", "HTTP"),
                        "source": "internal-dependencies",
                    })

        return result

    def _resolve_relationship(self, rel: dict, source_container: str) -> Optional[dict]:
        """Validate and resolve relationship endpoints. Returns None to discard."""
        # Always use the registered container name as 'from' — the rel may carry
        # a pre-merge name (e.g., K8s metadata.name) that differs from the canonical key.
        from_name = source_container
        to_raw = rel.get("to", "")

        if not from_name or not to_raw or from_name == to_raw:
            return None

        # Resolve 'to': known name → direct, else slug-match
        if to_raw in self.containers:
            to_name = to_raw
        else:
            to_name = self._resolve_container_by_token(to_raw)
            if not to_name:
                # Unresolved helm values or volume refs: discard
                if rel.get("_unresolved") or rel.get("type") == "shares-volume":
                    return None
                to_name = to_raw  # keep for external/unknown targets (best-effort)

        clean = {k: v for k, v in rel.items() if k != "_unresolved"}
        clean["from"] = from_name
        clean["to"] = to_name
        return clean
    
    def _drop_redundant_root_containers(self) -> None:
        """Remove repo-root structure containers when explicit services exist.

        The structure detector registers the repo root (path=".") as a fallback
        container whenever it finds a framework manifest there (e.g. docker-compose.yml).
        Once the compose/helm detectors have registered the real services, this root
        node is just noise. Drop it unless it is the only container detected.
        """
        if len(self.containers) <= 1:
            return  # nothing to drop — keep the lone container

        # Collect keys of root-level structure containers (path == ".")
        to_drop = [
            key for key, c in self.containers.items()
            if c.get("path") in {".", ""} and not c.get("deployment")
        ]

        # Only drop them when there are other non-root containers
        real_services = [k for k in self.containers if k not in to_drop]
        if real_services:
            for key in to_drop:
                logger.debug("Dropping redundant root container %r (superseded by compose/helm services)", key)
                del self.containers[key]

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

    def _enrich_containers_with_c4_metadata(self, containers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Add C4 element type label and c4_container_type to each container.

        Adds:
        - c4_element_type = "Container"  (C4 canonical label for L2)
        - c4_container_type             (book-canonical ContainerType)
        """
        for name, container in containers.items():
            container["c4_element_type"] = C4ElementType.CONTAINER.value
            container["c4_container_type"] = classify_c4_container_type(container).value
        return containers

    def _enrich_relationships_with_protocol(self, relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ensure every relationship carries a technology/protocol field.

        Adds 'technology' (alias for protocol) to each relationship dict,
        defaulting to the container's own protocol when available.
        """
        for rel in relationships:
            rel.setdefault("technology", rel.get("protocol", ""))
        return relationships
