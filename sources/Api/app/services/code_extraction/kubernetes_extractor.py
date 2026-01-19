"""Kubernetes and Helm manifest extractor."""

import logging
from pathlib import Path
from typing import Any

import yaml

from app.domain.models.code_entities import (
    CodeEntity,
    CodeEntityType,
    CodeLanguage,
    CodeRelationship,
    CodeRelationType,
    SourceType,
)
from app.services.code_extraction.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class KubernetesExtractor(BaseExtractor):
    """Extract entities and relationships from Kubernetes/Helm manifests."""

    KIND_ENTITY_MAP: dict[str, CodeEntityType] = {
        "Deployment": CodeEntityType.DEPLOYMENT,
        "StatefulSet": CodeEntityType.DEPLOYMENT,
        "DaemonSet": CodeEntityType.DEPLOYMENT,
        "Job": CodeEntityType.DEPLOYMENT,
        "CronJob": CodeEntityType.DEPLOYMENT,
        "Service": CodeEntityType.SERVICE,
        "Ingress": CodeEntityType.SERVICE,
        "Pod": CodeEntityType.POD,
        "ConfigMap": CodeEntityType.CONFIG_FILE,
        "Secret": CodeEntityType.SECRET,
        "PersistentVolume": CodeEntityType.VOLUME,
        "PersistentVolumeClaim": CodeEntityType.VOLUME,
        "Namespace": CodeEntityType.NAMESPACE,
    }

    HELM_FILES = {"chart.yaml", "values.yaml", "kustomization.yaml"}

    def can_handle(self, file_path: Path) -> bool:
        """Determine if the file is a Kubernetes/Helm manifest."""
        if file_path.suffix not in {".yml", ".yaml"}:
            return False

        name_lower = file_path.name.lower()
        path_lower = str(file_path).lower()

        if name_lower in self.HELM_FILES:
            return True

        if any(keyword in path_lower for keyword in ("k8s", "kubernetes", "helm", "manifests", "charts")):
            return True

        # Peek into the file to detect apiVersion/kind markers
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                for _ in range(20):
                    line = handle.readline()
                    if not line:
                        break
                    if "apiVersion" in line and "kind" in line:
                        return True
        except Exception as exc:
            logger.debug("Failed to probe %s for Kubernetes markers: %s", file_path, exc)

        return False

    def extract(self, file_path: Path) -> tuple[list[CodeEntity], list[CodeRelationship]]:
        """Extract Kubernetes/Helm entities from a manifest."""
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []

        content = self.safe_read_file(file_path)
        if not content:
            return entities, relationships

        rel_path = self.get_relative_path(file_path)

        try:
            documents = list(yaml.safe_load_all(content))
        except yaml.YAMLError as exc:
            self.errors.append(f"Failed to parse Kubernetes YAML {file_path}: {exc}")
            return entities, relationships

        for doc in documents:
            if not isinstance(doc, dict):
                continue

            if "kind" in doc and "apiVersion" in doc:
                resource_entity, container_relationships = self._build_resource_entity(
                    rel_path, doc
                )
                if resource_entity:
                    entities.append(resource_entity)
                    entities.extend(container_relationships["entities"])
                    relationships.extend(container_relationships["relationships"])
            elif file_path.name.lower() in self.HELM_FILES:
                helm_entity = self._build_helm_entity(rel_path, doc, file_path.name)
                if helm_entity:
                    entities.append(helm_entity)

        return entities, relationships

    def _build_resource_entity(
        self,
        file_path: str,
        document: dict[str, Any],
    ) -> tuple[CodeEntity | None, dict[str, list[Any]]]:
        """Create a CodeEntity for a Kubernetes resource."""
        kind = document.get("kind", "Resource")
        metadata = document.get("metadata", {})
        spec = document.get("spec", {})
        name = metadata.get("name") or f"{kind.lower()}_{metadata.get('generateName', 'resource')}"

        entity_type = self.KIND_ENTITY_MAP.get(kind, CodeEntityType.RESOURCE)
        entity_id = self.generate_entity_id(file_path, f"{kind}:{name}", "kubernetes_resource")

        containers = self._extract_containers(spec)
        container_entities: list[CodeEntity] = []
        container_relationships: list[CodeRelationship] = []

        for container in containers:
            container_entity_id = self.generate_entity_id(
                f"{file_path}:{name}",
                container["name"],
                "container",
            )
            container_entity = CodeEntity(
                id=container_entity_id,
                name=container["name"],
                entity_type=CodeEntityType.CONTAINER,
                language=CodeLanguage.UNKNOWN,
                source_type=SourceType.KUBERNETES,
                file_path=file_path,
                attributes={
                    "image": container.get("image"),
                    "ports": container.get("ports", []),
                    "env": container.get("env", []),
                },
                parent_entity_id=entity_id,
                confidence=0.95,
            )
            container_entities.append(container_entity)

            rel_id = self.generate_relationship_id(entity_id, container_entity_id, "contains")
            container_relationships.append(
                CodeRelationship(
                    id=rel_id,
                    source_entity_id=entity_id,
                    target_entity_id=container_entity_id,
                    relationship_type=CodeRelationType.CONTAINS,
                    confidence=0.95,
                )
            )

        entity = CodeEntity(
            id=entity_id,
            name=name,
            entity_type=entity_type,
            language=CodeLanguage.UNKNOWN,
            source_type=SourceType.KUBERNETES,
            file_path=file_path,
            attributes={
                "kind": kind,
                "apiVersion": document.get("apiVersion"),
                "namespace": metadata.get("namespace"),
                "labels": metadata.get("labels"),
                "annotations": metadata.get("annotations"),
                "containers": [c["name"] for c in containers],
                "images": [c.get("image") for c in containers if c.get("image")],
            },
            confidence=0.95,
        )

        return entity, {"entities": container_entities, "relationships": container_relationships}

    def _build_helm_entity(
        self,
        file_path: str,
        document: dict[str, Any],
        filename: str,
    ) -> CodeEntity | None:
        """Create entities for Helm Chart metadata."""
        if not isinstance(document, dict):
            return None

        entity_id = self.generate_entity_id(file_path, filename, "helm")
        return CodeEntity(
            id=entity_id,
            name=document.get("name", filename),
            entity_type=CodeEntityType.CONFIG_FILE,
            language=CodeLanguage.UNKNOWN,
            source_type=SourceType.KUBERNETES,
            file_path=file_path,
            attributes=document,
            confidence=0.9,
        )

    def _extract_containers(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract container definitions from a workload spec."""
        candidates: list[dict[str, Any]] = []

        if not isinstance(spec, dict):
            return candidates

        pod_template = spec.get("template", {})
        if "spec" in pod_template:
            pod_spec = pod_template.get("spec", {})
        else:
            # Some resources (e.g., Pod) define containers directly
            pod_spec = spec

        for container in pod_spec.get("containers", []):
            name = container.get("name")
            if not name:
                continue
            candidates.append(
                {
                    "name": name,
                    "image": container.get("image"),
                    "ports": container.get("ports", []),
                    "env": container.get("env", []),
                }
            )

        return candidates
