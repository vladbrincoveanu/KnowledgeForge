"""Kubernetes manifest container detector (raw YAML and Kustomize)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .base_detector import BaseContainerDetector
from .relationship_extractor import EnvVarRelationshipExtractor
from .utils import PORT_PROTOCOL_MAP

logger = logging.getLogger(__name__)

_EXCLUDED_DIRS = {
    "__pycache__", ".git", ".github", ".gitlab", "node_modules",
    "venv", "env", ".env", "dist", "build", "target", "out",
    ".idea", ".vscode", "logs", "temp", "tmp", ".pytest_cache",
    "test", "tests", "__tests__", "docs", "documentation",
    ".next", ".nuxt", ".cache", "coverage", ".coverage",
}

# image keyword → (technology label, container_type)
_IMAGE_TYPE_MAP = [
    ("postgres",        ("PostgreSQL",      "Database")),
    ("mysql",           ("MySQL",           "Database")),
    ("mariadb",         ("MariaDB",         "Database")),
    ("mongodb",         ("MongoDB",         "Database")),
    ("mongo",           ("MongoDB",         "Database")),
    ("redis",           ("Redis",           "Cache")),
    ("elasticsearch",   ("Elasticsearch",   "Search Engine")),
    ("opensearch",      ("OpenSearch",      "Search Engine")),
    ("kafka",           ("Kafka",           "Message Broker")),
    ("rabbitmq",        ("RabbitMQ",        "Message Broker")),
    ("nats",            ("NATS",            "Message Broker")),
    ("activemq",        ("ActiveMQ",        "Message Broker")),
    ("zookeeper",       ("ZooKeeper",       "Coordination Service")),
    ("mssql",           ("SQL Server",      "Database")),
    ("sqlserver",       ("SQL Server",      "Database")),
    ("nginx",           ("Nginx",           "Web Server")),
    ("envoy",           ("Envoy",           "Proxy")),
    ("jaeger",          ("Jaeger",          "Tracing")),
    ("prometheus",      ("Prometheus",      "Monitoring")),
    ("grafana",         ("Grafana",         "Monitoring Dashboard")),
]

_KIND_TYPE_OVERRIDES = {
    "Job":      "Batch Job",
    "CronJob":  "Scheduled Job",
    "DaemonSet": "System Agent",
}


class KubernetesDetector(BaseContainerDetector):
    """Detect C4 containers from Kubernetes manifests (raw YAML and Kustomize)."""

    WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}

    def __init__(self, repo_path: Path):
        super().__init__(repo_path)
        self._kustomize_files: set[Path] = set()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def can_detect(self) -> bool:
        """True if repo has a kustomization.yaml/yml or any K8s workload YAML."""
        if (
            list(self.repo_path.rglob("kustomization.yaml"))
            or list(self.repo_path.rglob("kustomization.yml"))
        ):
            return True

        for yaml_file in list(self.repo_path.rglob("*.yaml")) + list(self.repo_path.rglob("*.yml")):
            if self._quick_check_k8s_workload(yaml_file):
                return True

        return False

    def detect(self) -> list[dict[str, Any]]:
        """Detect containers from Kubernetes manifests."""
        containers: list[dict] = []
        seen: set[tuple] = set()  # (kind, name, namespace) dedup key

        self._kustomize_files = self._collect_kustomize_files()

        for yaml_file in self._collect_yaml_files():
            for doc in self._parse_yaml_docs(yaml_file):
                if not self._is_k8s_workload(doc):
                    continue

                meta = doc.get("metadata") or {}
                key = (
                    doc.get("kind", ""),
                    meta.get("name") or "",
                    meta.get("namespace") or "default",
                )
                if key in seen:
                    continue
                seen.add(key)

                container = self._extract_container_from_workload(doc, yaml_file)
                if container is not None:
                    containers.append(container)

        return containers

    # ------------------------------------------------------------------
    # Directory / file discovery
    # ------------------------------------------------------------------

    def _find_manifest_directories(self) -> list[Path]:
        """Return directories containing K8s manifests, skipping Helm chart dirs."""
        manifest_dirs: set[Path] = set()
        for yaml_file in list(self.repo_path.rglob("*.yaml")) + list(self.repo_path.rglob("*.yml")):
            if self._is_excluded(yaml_file) or self._is_in_helm_dir(yaml_file):
                continue
            manifest_dirs.add(yaml_file.parent)
        return list(manifest_dirs)

    def _collect_yaml_files(self) -> list[Path]:
        """Collect all YAML files that are not inside Helm chart directories."""
        files: list[Path] = []
        for yaml_file in list(self.repo_path.rglob("*.yaml")) + list(self.repo_path.rglob("*.yml")):
            if self._is_excluded(yaml_file) or self._is_in_helm_dir(yaml_file):
                continue
            files.append(yaml_file)
        return files

    def _collect_kustomize_files(self) -> set[Path]:
        """Return resolved paths of all YAML files referenced by kustomization.yaml files."""
        referenced: set[Path] = set()

        kust_files = list(self.repo_path.rglob("kustomization.yaml")) + list(
            self.repo_path.rglob("kustomization.yml")
        )
        for kust_file in kust_files:
            try:
                data = (
                    yaml.safe_load(kust_file.read_text(encoding="utf-8", errors="ignore")) or {}
                )
                for resource in data.get("resources") or []:
                    resource_path = kust_file.parent / str(resource)
                    if resource_path.is_file():
                        referenced.add(resource_path.resolve())
                    elif resource_path.is_dir():
                        for f in list(resource_path.rglob("*.yaml")) + list(resource_path.rglob("*.yml")):
                            referenced.add(f.resolve())
            except Exception as e:
                logger.debug("Error reading kustomization file %s: %s", kust_file, e)

        return referenced

    # ------------------------------------------------------------------
    # YAML parsing
    # ------------------------------------------------------------------

    def _parse_yaml_docs(self, file_path: Path) -> list[dict]:
        """Parse a YAML file and return all documents (multi-doc support)."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            return [d for d in yaml.safe_load_all(content) if isinstance(d, dict)]
        except Exception as e:
            logger.debug("Failed to parse YAML %s: %s", file_path, e)
            return []

    def _is_k8s_workload(self, doc: dict) -> bool:
        """True when doc has apiVersion and a supported workload kind."""
        return bool(doc.get("apiVersion")) and doc.get("kind") in self.WORKLOAD_KINDS

    # ------------------------------------------------------------------
    # Container extraction
    # ------------------------------------------------------------------

    def _extract_container_from_workload(self, doc: dict, file_path: Path) -> dict | None:
        """Build a C4 container dict from a K8s workload manifest."""
        meta = doc.get("metadata") or {}
        name = meta.get("name") or ""
        if not name:
            return None

        kind = doc.get("kind", "")
        namespace = meta.get("namespace") or "default"
        spec = doc.get("spec") or {}

        # Navigate to spec.template.spec for each kind
        if kind == "CronJob":
            template_spec = (
                spec.get("jobTemplate", {})
                .get("spec", {})
                .get("template", {})
                .get("spec", {})
            ) or {}
        else:
            template_spec = spec.get("template", {}).get("spec", {}) or {}

        # Only spec.template.spec.containers[], never initContainers[]
        containers = template_spec.get("containers") or []
        if not containers:
            return None

        first = containers[0] if isinstance(containers[0], dict) else {}
        image = first.get("image") or ""

        technology = self._extract_technology_from_image(image)
        container_type = self._infer_container_type_from_kind_and_image(kind, image)
        protocol = self._extract_protocol_from_ports(containers)
        health_endpoint = self._extract_health_endpoint(containers)
        relationships = self._extract_relationships(name, containers)

        deployment = (
            "Kustomize" if file_path.resolve() in self._kustomize_files else "Manifest"
        )

        return {
            "c4_level": 2,
            "type": "container",
            "name": name,
            "container_type": container_type,
            "technology": technology,
            "protocol": protocol,
            "path": str(file_path.parent.relative_to(self.repo_path)),
            "runtime_environment": "Kubernetes",
            "deployment": deployment,
            "description": f"Kubernetes {kind} workload.",
            "repository_url": "",
            "runtime_info": "",
            "dependencies_internal": [],
            "health_endpoint": health_endpoint,
            "relationships": relationships,
            "kubernetes_kind": kind,
            "kubernetes_namespace": namespace,
        }

    def _infer_container_type_from_kind_and_image(self, kind: str, image: str) -> str:
        """Infer C4 container type from workload kind and image name."""
        if kind in _KIND_TYPE_OVERRIDES:
            return _KIND_TYPE_OVERRIDES[kind]

        image_lower = (image or "").lower()
        image_base = image_lower.split("/")[-1].split(":")[0]

        for keyword, (_, container_type) in _IMAGE_TYPE_MAP:
            if keyword in image_base or keyword in image_lower:
                return container_type

        return "Service"

    # ------------------------------------------------------------------
    # Field extraction helpers
    # ------------------------------------------------------------------

    def _extract_technology_from_image(self, image: str) -> str:
        """Derive a technology label from the container image name."""
        if not image:
            return "Unknown"

        image_lower = image.lower()
        image_base = image_lower.split("/")[-1].split(":")[0]

        for keyword, (technology, _) in _IMAGE_TYPE_MAP:
            if keyword in image_base or keyword in image_lower:
                return technology

        return image_base.replace("-", " ").replace("_", " ").title() if image_base else "Unknown"

    def _extract_protocol_from_ports(self, containers: list) -> str:
        """Infer protocol from containerPort values using PORT_PROTOCOL_MAP."""
        for container in containers:
            if not isinstance(container, dict):
                continue
            for port_spec in container.get("ports") or []:
                if not isinstance(port_spec, dict):
                    continue
                port = str(port_spec.get("containerPort") or "")
                if port in PORT_PROTOCOL_MAP:
                    return PORT_PROTOCOL_MAP[port]
        return "HTTP"

    def _extract_health_endpoint(self, containers: list) -> str:
        """Extract health path from livenessProbe or readinessProbe httpGet."""
        for container in containers:
            if not isinstance(container, dict):
                continue
            for probe_key in ("readinessProbe", "livenessProbe"):
                probe = container.get(probe_key)
                if isinstance(probe, dict):
                    http_get = probe.get("httpGet")
                    if isinstance(http_get, dict):
                        path = http_get.get("path") or ""
                        if path:
                            return path
        return ""

    def _extract_relationships(self, name: str, containers: list) -> list[dict]:
        """Extract relationships from env vars across all pod containers."""
        extractor = EnvVarRelationshipExtractor(name, source_label="env")
        relationships: list[dict] = []
        for container in containers:
            if not isinstance(container, dict):
                continue
            env_vars = container.get("env") or []
            relationships.extend(extractor.extract(env_vars))
        return relationships

    # ------------------------------------------------------------------
    # Exclusion helpers
    # ------------------------------------------------------------------

    def _is_excluded(self, path: Path) -> bool:
        """True when any path component under repo_root is in the exclusion list."""
        try:
            rel_parts = path.relative_to(self.repo_path).parts
        except ValueError:
            return True
        return any(part in _EXCLUDED_DIRS for part in rel_parts)

    def _is_in_helm_dir(self, path: Path) -> bool:
        """True when any ancestor directory contains a Chart.yaml."""
        current = path.parent
        while current != self.repo_path and current != current.parent:
            if (current / "Chart.yaml").exists():
                return True
            current = current.parent
        return False

    def _quick_check_k8s_workload(self, yaml_file: Path) -> bool:
        """Fast text scan to check for apiVersion + a workload kind before full parse."""
        try:
            text = yaml_file.read_text(encoding="utf-8", errors="ignore")
            if "apiVersion" not in text:
                return False
            return any(f"kind: {k}" in text for k in self.WORKLOAD_KINDS)
        except Exception:
            return False
