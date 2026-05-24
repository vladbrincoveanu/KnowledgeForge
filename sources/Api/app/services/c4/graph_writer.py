from __future__ import annotations

import json
import logging
from typing import Any

from app.infrastructure.graph.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphWriter:
    def __init__(self, neo4j_client: Neo4jClient) -> None:
        self._client = neo4j_client

    def write(self, task_id: str, c4_data: dict[str, Any]) -> None:
        self._client.clear_extraction(task_id)

        self._write_context_level(
            task_id,
            c4_data.get("system_context") or {},
            (c4_data.get("relationships") or {}).get("context") or [],
        )
        self._write_container_level(
            task_id,
            c4_data.get("containers") or [],
            (c4_data.get("relationships") or {}).get("containers") or [],
        )
        self._write_component_level(
            task_id,
            c4_data.get("components") or [],
            (c4_data.get("relationships") or {}).get("components") or [],
        )

    def _write_context_level(
        self,
        task_id: str,
        system_context: dict[str, Any],
        relationships: list[dict[str, Any]],
    ) -> None:
        sys_name = system_context.get("name", "System") or "System"
        system_id = f"context:{sys_name}"
        self._upsert_node(
            "System",
            {
                "id": system_id,
                "name": sys_name,
                "entity_type": "system",
                "level": "context",
                "extraction_task_id": task_id,
                "properties": _system_context_properties(system_context),
            },
        )

        for actor in system_context.get("actors") or []:
            actor_id = f"person:{actor.get('name', 'Unknown')}"
            self._upsert_node(
                "Person",
                {
                    "id": actor_id,
                    "name": actor.get("name", "Unknown"),
                    "entity_type": "person",
                    "level": "context",
                    "extraction_task_id": task_id,
                    "properties": {"description": actor.get("description", "")},
                },
            )
            self._upsert_relationship(
                "USES",
                f"{actor_id}->{system_id}",
                actor_id,
                system_id,
                {
                    "description": f"{actor.get('name', 'Unknown')} interacts with system"
                },
            )

        for idx, dep in enumerate(system_context.get("external_dependencies") or []):
            dep_name = dep.get("name") or dep.get("context_name") or f"Unknown:{idx}"
            ext_id = f"external_system:{dep_name}:{idx}"
            self._upsert_node(
                "ExternalSystem",
                {
                    "id": ext_id,
                    "name": dep.get("name") or dep.get("context_name") or "Unknown",
                    "entity_type": dep.get("type", "external_system"),
                    "level": "context",
                    "extraction_task_id": task_id,
                    "properties": _external_dependency_properties(dep),
                },
            )
            self._write_evidence_nodes(ext_id, dep.get("evidence") or [], task_id)
            self._upsert_relationship(
                "USES",
                f"{system_id}->{ext_id}",
                system_id,
                ext_id,
                {"description": f"System uses {dep.get('name') or 'external service'}"},
            )

    def _write_container_level(
        self,
        task_id: str,
        containers: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
    ) -> None:
        infra_names = {
            c.get("name") for c in containers if c.get("is_infrastructure_only")
        }
        visible_containers = [
            c for c in containers if not c.get("is_infrastructure_only")
        ]

        container_id_by_name = {}
        for c in visible_containers:
            cid = f"container:{c.get('name', 'unknown')}"
            container_id_by_name[c.get("name")] = cid
            self._upsert_node(
                "Container",
                {
                    "id": cid,
                    "name": c.get("name", "unknown"),
                    "entity_type": "container",
                    "level": "container",
                    "extraction_task_id": task_id,
                    "properties": _container_properties(c),
                },
            )

        for rel in relationships:
            src_name = rel.get("from")
            dst_name = rel.get("to") or rel.get("destination")
            if not src_name or not dst_name:
                continue
            src_id = container_id_by_name.get(src_name)
            dst_id = container_id_by_name.get(dst_name)
            if not src_id or not dst_id:
                logger.warning(
                    f"Skipping relationship {src_name}->{dst_name}: node not found"
                )
                continue
            rel_id = f"{src_id}->{dst_id}"
            self._upsert_relationship(
                "USES",
                rel_id,
                src_id,
                dst_id,
                {
                    "protocol": rel.get("protocol", ""),
                    "description": rel.get("description", ""),
                },
            )

    def _write_component_level(
        self,
        task_id: str,
        components: list[dict[str, Any]],
        relationships: list[dict[str, Any]] | None = None,
    ) -> None:
        comp_id_by_name: dict[str, str] = {}
        for comp in components or []:
            comp_type = comp.get("type", "component")
            if comp_type == "component_group":
                for sub in comp.get("components") or []:
                    self._write_component(task_id, sub, comp.get("container") or "")
                    comp_id_by_name[sub.get("name", "")] = f"component:{sub.get('name', 'unknown')}"
            else:
                self._write_component(task_id, comp, comp.get("container") or "")
                comp_id_by_name[comp.get("name", "")] = f"component:{comp.get('name', 'unknown')}"

        for rel in relationships or []:
            src_name = rel.get("from")
            tgt_name = rel.get("to")
            if not src_name or not tgt_name:
                continue
            src_id = comp_id_by_name.get(src_name)
            tgt_id = comp_id_by_name.get(tgt_name)
            if not src_id or not tgt_id:
                logger.warning(
                    "Skipping component relationship %s->%s: node not found", src_name, tgt_name
                )
                continue
            self._upsert_relationship(
                "USES",
                f"{src_id}->{tgt_id}",
                src_id,
                tgt_id,
                {"label": rel.get("label", "uses")},
            )

    def _write_component(
        self, task_id: str, comp: dict[str, Any], container_name: str
    ) -> None:
        comp_id = f"component:{comp.get('name', 'unknown')}"
        container_id = f"container:{container_name}" if container_name else None
        self._upsert_node(
            "Component",
            {
                "id": comp_id,
                "name": comp.get("name", "unknown"),
                "entity_type": "component",
                "level": "component",
                "extraction_task_id": task_id,
                "properties": {
                    "component_type": comp.get("component_type", ""),
                    "container": container_name,
                    "endpoint_path": comp.get("endpoint_path", ""),
                    "endpoint_method": comp.get("endpoint_method", ""),
                    "language": comp.get("language", ""),
                },
            },
        )
        if container_id:
            self._upsert_relationship(
                "CONTAINS",
                f"{container_id}->{comp_id}",
                container_id,
                comp_id,
                {},
            )
        else:
            logger.warning(
                f"Skipping CONTAINS relationship for component '{comp.get('name', 'unknown')}': no container"
            )

    def _write_evidence_nodes(
        self, external_system_id: str, evidence: list[dict[str, Any]], task_id: str
    ) -> None:
        assert isinstance(
            evidence, list
        ), f"evidence must be a list, got {type(evidence)}"
        for idx, ev in enumerate(evidence):
            ev_id = f"evidence:{external_system_id}:{idx}"
            self._upsert_node(
                "Evidence",
                {
                    "id": ev_id,
                    "name": f"Evidence {idx}",
                    "entity_type": "evidence",
                    "level": "context",
                    "extraction_task_id": task_id,
                    "properties": {
                        "evidence_type": ev.get("type", ""),
                        "source": ev.get("source", ""),
                        "snippet": ev.get("snippet", ""),
                    },
                },
            )
            self._upsert_relationship(
                "PROVIDED",
                f"{external_system_id}->{ev_id}",
                external_system_id,
                ev_id,
                {},
            )

    def _upsert_node(self, label: str, node_data: dict[str, Any]) -> None:
        node_id = node_data["id"]
        props = node_data.get("properties", {})
        self._client.upsert_node(label, node_id, props)

    def _upsert_relationship(
        self,
        rel_type: str,
        rel_id: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any],
    ) -> None:
        self._client.upsert_relationship(rel_type, rel_id, from_id, to_id, properties)


def _system_context_properties(sc: dict[str, Any]) -> dict[str, Any]:
    return {
        "owner_team": sc.get("owner_team", ""),
        "owner": sc.get("owner", ""),
        "business_domain": sc.get("business_domain", ""),
        "domain": sc.get("domain", ""),
        "criticality": sc.get("criticality", ""),
        "tier": sc.get("tier", ""),
        "status": sc.get("status", ""),
        "data_class": sc.get("data_class", ""),
        "compliance": sc.get("compliance", ""),
        "languages": json.dumps(sc.get("languages", [])),
        "frameworks": json.dumps(sc.get("frameworks", [])),
        "repository_url": sc.get("repository_url", ""),
    }


def _external_dependency_properties(dep: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": dep.get("provider", ""),
        "company": dep.get("company", ""),
        "url": dep.get("url", ""),
        "classification_confidence": dep.get("classification_confidence", 0.0),
        "decision_mode": dep.get("decision_mode", ""),
        "review_status": dep.get("review_status", ""),
        "dependency_type": dep.get("dependency_type", ""),
    }


def _container_properties(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "technology": c.get("technology", ""),
        "container_type": c.get("container_type", ""),
        "protocol": c.get("protocol", ""),
        "runtime_info": c.get("runtime_info", ""),
        "runtime_environment": c.get("runtime_environment", ""),
        "deployment": c.get("deployment", ""),
        "description": c.get("description", ""),
        "repository_url": c.get("repository_url", ""),
        "health_endpoint": c.get("health_endpoint", ""),
    }
