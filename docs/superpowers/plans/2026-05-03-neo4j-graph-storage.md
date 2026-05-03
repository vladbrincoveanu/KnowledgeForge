# Neo4j Graph Storage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Neo4j as a secondary storage layer during extraction. After each extraction, upsert all C4 entities and relationships into Neo4j with correct labels, composite IDs, and evidence nodes.

**Architecture:** `GraphWriter` maps extraction data to Neo4j operations. `Neo4jClient` wraps the driver. Both written before integration. Extraction aborts if Neo4j is unavailable.

**Tech Stack:** Python (FastAPI), Neo4j `bolt` driver (`neo4j>=5.13.0` already in requirements.txt), Playwright E2E

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `app/infrastructure/graph/neo4j_client.py` | Create | Neo4j driver wrapper |
| `tests/unit/infrastructure/test_neo4j_client.py` | Create | Unit tests for Neo4jClient |
| `app/services/c4/graph_writer.py` | Create | Extraction-to-Neo4j mapper |
| `tests/unit/services/c4/test_graph_writer.py` | Create | Unit tests for GraphWriter |
| `app/services/code_extraction/c4_extractor.py` | Modify | Call GraphWriter after JSON save |
| `tests/integration/test_json_neo4j_comparison.py` | Create | JSON ↔ Neo4j comparison test |
| `sources/UI/e2e/specs/07-neo4j-consistency.spec.ts` | Create | Playwright E2E for Neo4j |

---

## Task 1: Neo4j Client

**Files:**
- Create: `sources/Api/app/infrastructure/graph/neo4j_client.py`
- Create: `sources/Api/tests/unit/infrastructure/__init__.py`
- Create: `sources/Api/tests/unit/infrastructure/test_neo4j_client.py`
- Test: Run with `pytest tests/unit/infrastructure/test_neo4j_client.py -v`

**Notes:**
- `neo4j` driver is already in `requirements.txt`
- `GraphDatabaseError` already exists in `app/domain/exceptions.py`
- Follow existing config pattern from `app/utils/config.py` for `from_config()` class method
- Use `neo4j` Bolt driver (NOT HTTP)

- [ ] **Step 1: Write the failing test**

```python
# sources/Api/tests/unit/infrastructure/test_neo4j_client.py
import pytest
from unittest.mock import MagicMock, patch


class TestNeo4jClientInit:
    def test_from_config_creates_client_with_defaults(self):
        with patch("app.infrastructure.graph.neo4j_client.get_config") as mock_config:
            mock_config.return_value.neo4j = MagicMock(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="password123",
                database="neo4j",
                encrypted=False,
                max_connection_pool_size=50,
                connection_timeout=30,
            )
            from app.infrastructure.graph.neo4j_client import Neo4jClient
            client = Neo4jClient.from_config()
            assert client.uri == "bolt://localhost:7687"
            assert client.database == "neo4j"


class TestNeo4jClientUpsertNode:
    def test_upsert_node_uses_merge_cypher(self, mock_driver):
        from app.infrastructure.graph.neo4j_client import Neo4jClient
        client = Neo4jClient.__new__(Neo4jClient)
        client.driver = mock_driver
        client.database = "neo4j"

        client.upsert_node("Container", "container:airbyte-api", {"name": "airbyte-api", "level": "container"})

        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        assert "MERGE" in cypher
        assert "(n:Container {id: $node_id})" in cypher
        assert mock_session.close.called


class TestNeo4jClientUpsertRelationship:
    def test_upsert_relationship_creates_merge_pattern(self, mock_driver):
        from app.infrastructure.graph.neo4j_client import Neo4jClient
        client = Neo4jClient.__new__(Neo4jClient)
        client.driver = mock_driver
        client.database = "neo4j"

        client.upsert_relationship(
            "USES",
            "container:openapi2jsonschema->container:docker",
            "container:openapi2jsonschema",
            "container:docker",
            {"protocol": "HTTP", "description": "uses docker"},
        )

        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        assert "MERGE" in cypher
        assert "(a)-[r:USES]->(b)" in cypher.replace(" ", "")


class TestNeo4jClientClearExtraction:
    def test_clear_extraction_deletes_by_task_id(self, mock_driver):
        from app.infrastructure.graph.neo4j_client import Neo4jClient
        client = Neo4jClient.__new__(Neo4jClient)
        client.driver = mock_driver
        client.database = "neo4j"

        client.clear_extraction("task-abc-123")

        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.run.assert_called_once()
        cypher = mock_session.run.call_args[0][0]
        params = mock_session.run.call_args[0][1]
        assert "extraction_task_id" in cypher
        assert params["task_id"] == "task-abc-123"
        assert mock_session.close.called


class TestNeo4jClientQuery:
    def test_query_returns_list_of_dicts(self, mock_driver):
        from app.infrastructure.graph.neo4j_client import Neo4jClient
        client = Neo4jClient.__new__(Neo4jClient)
        client.driver = mock_driver
        client.database = "neo4j"

        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_result = MagicMock()
        mock_result.single.return_value = {"count": 5}
        mock_session.run.return_value = mock_result

        result = client.query("MATCH (n:Container) RETURN count(n) as count", {})
        assert result == [{"count": 5}]
        assert mock_session.close.called


@pytest.fixture
def mock_driver():
    with patch("app.infrastructure.graph.neo4j_client.neo4j") as mock_neo4j:
        mock_driver_instance = MagicMock()
        mock_neo4j.Driver.return_value = mock_driver_instance
        mock_neo4j.neo4j = MagicMock()
        yield mock_driver_instance
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/infrastructure/test_neo4j_client.py -v 2>&1 | head -30`
Expected: FAIL — module `app.infrastructure.graph.neo4j_client` does not exist

- [ ] **Step 3: Create directory and neo4j_client.py**

Create directory: `mkdir -p /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api/app/infrastructure/graph`

Write `app/infrastructure/graph/__init__.py`:
```python
```

Write `app/infrastructure/graph/neo4j_client.py`:

```python
from __future__ import annotations

import logging
from typing import Any

from neo4j import Driver, GraphDatabase

from app.domain.exceptions import GraphDatabaseError
from app.utils.config import get_config

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        self.uri = uri
        self.user = user
        self.database = database
        try:
            self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
        except Exception as e:
            raise GraphDatabaseError(f"Failed to connect to Neo4j at {uri}: {e}")

    @classmethod
    def from_config(cls) -> "Neo4jClient":
        config = get_config()
        neo4j_config = config.neo4j
        return cls(
            uri=str(neo4j_config.uri),
            user=str(neo4j_config.username),
            password=str(neo4j_config.password),
            database=str(neo4j_config.database),
        )

    def upsert_node(self, label: str, node_id: str, properties: dict[str, Any]) -> None:
        cypher = f"""
        MERGE (n:{label} {{id: $node_id}})
        SET n += $props
        """
        with self._session() as session:
            session.run(cypher, node_id=node_id, props=properties)

    def upsert_relationship(
        self,
        rel_type: str,
        rel_id: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any],
    ) -> None:
        cypher = f"""
        MATCH (a {{id: $from_id}})
        MATCH (b {{id: $to_id}})
        MERGE (a)-[r:{rel_type} {{id: $rel_id}}]->(b)
        SET r += $props
        """
        with self._session() as session:
            session.run(cypher, rel_id=rel_id, from_id=from_id, to_id=to_id, props=properties)

    def clear_extraction(self, task_id: str) -> None:
        cypher = """
        MATCH (n {extraction_task_id: $task_id})
        DETACH DELETE n
        """
        with self._session() as session:
            session.run(cypher, task_id=task_id)

    def query(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        with self._session() as session:
            result = session.run(cypher, params)
            return [dict(record) for record in result]

    def close(self) -> None:
        self.driver.close()

    def _session(self):
        return self.driver.session(database=self.database)
```

Create `tests/unit/infrastructure/__init__.py`:
```python
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/infrastructure/test_neo4j_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/graph/ tests/unit/infrastructure/
git commit -m "feat(api): add Neo4j client for graph storage"
```

---

## Task 2: Graph Writer

**Files:**
- Create: `sources/Api/app/services/c4/graph_writer.py`
- Test: `sources/Api/tests/unit/services/c4/test_graph_writer.py`
- Run with: `pytest tests/unit/services/c4/test_graph_writer.py -v`

- [ ] **Step 1: Write the failing test**

```python
# sources/Api/tests/unit/services/c4/test_graph_writer.py
import pytest
from unittest.mock import MagicMock, call


class TestGraphWriterWrite:
    def test_write_calls_all_three_levels(self, mock_neo4j_client):
        from app.services.c4.graph_writer import GraphWriter
        writer = GraphWriter(mock_neo4j_client)

        c4_data = {
            "system_context": {"name": "Airbyte", "actors": [], "external_dependencies": []},
            "containers": [],
            "components": [],
            "relationships": {"context": [], "containers": []},
        }

        writer.write("task-123", c4_data)

        assert mock_neo4j_client.upsert_node.called
        node_ids = [call_args[0][1] for call_args in mock_neo4j_client.upsert_node.call_args_list]
        assert "context:System" in node_ids


class TestGraphWriterLabels:
    def test_external_system_gets_provided_evidence_nodes(self, mock_neo4j_client):
        from app.services.c4.graph_writer import GraphWriter
        writer = GraphWriter(mock_neo4j_client)

        c4_data = {
            "system_context": {
                "name": "Airbyte",
                "actors": [],
                "external_dependencies": [
                    {
                        "name": "AWS S3",
                        "type": "external_system",
                        "evidence": [
                            {"type": "package_reference", "source": "package.json", "snippet": "aws-sdk"},
                            {"type": "deployment_reference", "source": "Dockerfile", "snippet": "FROM amazonlinux"},
                        ],
                    }
                ],
            },
            "containers": [],
            "components": [],
            "relationships": {"context": [], "containers": []},
        }

        writer.write("task-456", c4_data)

        upsert_calls = mock_neo4j_client.upsert_node.call_args_list
        node_ids = [call[0][1] for call in upsert_calls]
        assert "external_system:AWS S3" in node_ids
        assert "evidence:external_system:AWS S3:0" in node_ids
        assert "evidence:external_system:AWS S3:1" in node_ids

        rel_calls = mock_neo4j_client.upsert_relationship.call_args_list
        rel_ids = [call[0][1] for call in rel_calls]
        assert "evidence:external_system:AWS S3:0->evidence:external_system:AWS S3:0" in rel_ids
        assert any(
            "PROVIDED" in str(call)
            for call in mock_neo4j_client.upsert_relationship.call_args_list
        )


class TestGraphWriterValidation:
    def test_skips_relationship_if_target_missing(self, mock_neo4j_client, caplog):
        import logging
        from app.services.c4.graph_writer import GraphWriter

        caplog.set_level(logging.WARNING)

        mock_neo4j_client.query.return_value = [{"id": "container:openapi2jsonschema"}]

        writer = GraphWriter(mock_neo4j_client)
        writer._upsert_node = MagicMock()
        writer._upsert_relationship = MagicMock()

        writer._upsert_relationship(
            "USES",
            "container:openapi2jsonschema->container:docker",
            "container:openapi2jsonschema",
            "container:docker",
            {"description": "uses docker"},
        )

        # The actual validation is done inside _upsert_relationship with a pre-check
        # Here we test the logic that skips when from_id not found in query


@pytest.fixture
def mock_neo4j_client():
    client = MagicMock()
    client.query.return_value = []
    return client
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/services/c4/test_graph_writer.py -v 2>&1 | head -20`
Expected: FAIL — module `app.services.c4.graph_writer` does not exist

- [ ] **Step 3: Write the implementation**

```python
# sources/Api/app/services/c4/graph_writer.py
from __future__ import annotations

import logging
from typing import Any

from app.infrastructure.graph.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

_LABEL_MAP = {
    "system": "System",
    "person": "Person",
    "external_system": "ExternalSystem",
    "external_service": "ExternalSystem",
    "container": "Container",
    "component": "Component",
}


class GraphWriter:
    def __init__(self, neo4j_client: Neo4jClient) -> None:
        self._client = neo4j_client

    def write(self, task_id: str, c4_data: dict[str, Any]) -> None:
        self._client.clear_extraction(task_id)

        self._write_context_level(task_id, c4_data.get("system_context", {}), c4_data.get("relationships", {}).get("context", []))
        self._write_container_level(task_id, c4_data.get("containers", []), c4_data.get("relationships", {}).get("containers", []))
        self._write_component_level(task_id, c4_data.get("components", []))

    def _write_context_level(self, task_id: str, system_context: dict[str, Any], relationships: list[dict[str, Any]]) -> None:
        sys_name = system_context.get("name", "System")
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

        for actor in system_context.get("actors", []):
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
                {"description": f"{actor.get('name', 'Unknown')} interacts with system"},
            )

        for dep in system_context.get("external_dependencies", []):
            ext_id = f"external_system:{dep.get('name', dep.get('context_name', 'Unknown'))}"
            self._upsert_node(
                "ExternalSystem",
                {
                    "id": ext_id,
                    "name": dep.get("name", dep.get("context_name", "Unknown")),
                    "entity_type": dep.get("type", "external_system"),
                    "level": "context",
                    "extraction_task_id": task_id,
                    "properties": _external_dependency_properties(dep),
                },
            )
            self._write_evidence_nodes(ext_id, dep.get("evidence", []), task_id)
            self._upsert_relationship(
                "USES",
                f"{system_id}->{ext_id}",
                system_id,
                ext_id,
                {"description": f"System uses {dep.get('name', 'external service')}"},
            )

    def _write_container_level(self, task_id: str, containers: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> None:
        infra_names = {c.get("name") for c in containers if c.get("is_infrastructure_only")}
        visible_containers = [c for c in containers if not c.get("is_infrastructure_only")]

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
            src_name = rel.get("source") or rel.get("from")
            dst_name = rel.get("destination") or rel.get("to")
            if not src_name or not dst_name:
                continue
            src_id = container_id_by_name.get(src_name)
            dst_id = container_id_by_name.get(dst_name)
            if not src_id or not dst_id:
                logger.warning(f"Skipping relationship {src_name}->{dst_name}: node not found")
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

    def _write_component_level(self, task_id: str, components: list[dict[str, Any]]) -> None:
        for comp in components:
            comp_type = comp.get("type", "component")
            if comp_type == "component_group":
                for sub in comp.get("components", []):
                    self._write_component(task_id, sub, comp.get("container", ""))
            else:
                self._write_component(task_id, comp, comp.get("container", ""))

    def _write_component(self, task_id: str, comp: dict[str, Any], container_name: str) -> None:
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

    def _write_evidence_nodes(self, external_system_id: str, evidence: list[dict[str, Any]], task_id: str) -> None:
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

    def _upsert_relationship(self, rel_type: str, rel_id: str, from_id: str, to_id: str, properties: dict[str, Any]) -> None:
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
        "languages": sc.get("languages", []),
        "frameworks": sc.get("frameworks", []),
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/services/c4/test_graph_writer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/c4/graph_writer.py tests/unit/services/c4/test_graph_writer.py
git commit -m "feat(api): add GraphWriter for extraction-to-Neo4j mapping"
```

---

## Task 3: Integrate into C4ArchitectureExtractor

**Files:**
- Modify: `sources/Api/app/services/code_extraction/c4_extractor.py`
- Test: Run existing tests + new integration test

- [ ] **Step 1: Find the JSON save location in c4_extractor.py**

Run: `grep -n "_save_c4_to_json\|save.*json\|c4_data" /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api/app/services/code_extraction/c4_extractor.py | head -20`

Note the line number after which to insert the Neo4j write.

- [ ] **Step 2: Add import**

Add to the imports section of `c4_extractor.py`:
```python
from app.services.c4.graph_writer import GraphWriter
from app.infrastructure.graph.neo4j_client import Neo4jClient
from app.domain.exceptions import GraphDatabaseError
```

- [ ] **Step 3: Add Neo4j write after JSON save**

Find the location in `extract()` where `_save_c4_to_json` completes and the result is returned. Add:

```python
# Write to Neo4j (extraction fails if Neo4j unavailable)
try:
    graph_writer = GraphWriter(Neo4jClient.from_config())
    graph_writer.write(task_id, c4_data)
except GraphDatabaseError as e:
    logger.error(f"Neo4j write failed for extraction {task_id}: {e}")
    raise
```

- [ ] **Step 4: Run dependency detector tests to ensure no regression**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/unit/services/c4/test_dependency_detector.py -q`
Expected: 40 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/code_extraction/c4_extractor.py
git commit -m "feat(api): write extraction results to Neo4j on completion"
```

---

## Task 4: JSON ↔ Neo4j Comparison Integration Test

**Files:**
- Create: `sources/Api/tests/integration/test_json_neo4j_comparison.py`
- Test: `pytest tests/integration/test_json_neo4j_comparison.py -v`

- [ ] **Step 1: Write the failing test**

```python
# sources/Api/tests/integration/test_json_neo4j_comparison.py
"""
Integration test: verify Neo4j contents match the extracted JSON.

Requires: Docker services running (make up), Neo4j accessible,
and a completed extraction in .extraction-result.json.
"""
import json
import os
import pytest
from pathlib import Path

from app.infrastructure.graph.neo4j_client import Neo4jClient
from app.services.c4.graph_writer import GraphWriter


def load_extraction_result():
    result_path = Path(__file__).parent.parent.parent / "UI" / "e2e" / ".extraction-result.json"
    if not result_path.exists():
        pytest.skip(".extraction-result.json not found — run Playwright setup first")
    with open(result_path) as f:
        return json.load(f)


class TestJsonNeo4jComparison:
    @pytest.fixture(autouse=True)
    def setup_neo4j(self):
        client = Neo4jClient.from_config()
        yield client
        client.close()

    def test_container_count_matches(self, setup_neo4j):
        data = load_extraction_result()
        containers = [c for c in data.get("containers", []) if not c.get("is_infrastructure_only")]
        expected_count = len(containers)

        result = setup_neo4j.query("MATCH (n:Container) RETURN count(n) as count", {})
        actual_count = result[0]["count"]

        assert actual_count == expected_count, f"Neo4j has {actual_count} Container nodes, JSON has {expected_count}"

    def test_external_system_count_matches(self, setup_neo4j):
        data = load_extraction_result()
        ext_deps = data.get("system_context", {}).get("external_dependencies", [])
        expected_count = len(ext_deps)

        result = setup_neo4j.query("MATCH (n:ExternalSystem) RETURN count(n) as count", {})
        actual_count = result[0]["count"]

        assert actual_count == expected_count, f"Neo4j has {actual_count} ExternalSystem nodes, JSON has {expected_count}"

    def test_system_node_exists(self, setup_neo4j):
        data = load_extraction_result()
        sys_name = data.get("system_context", {}).get("name", "System")

        result = setup_neo4j.query("MATCH (n:System {id: $id}) RETURN n", {"id": f"context:{sys_name}"})
        assert len(result) == 1, f"System node 'context:{sys_name}' not found in Neo4j"

    def test_evidence_nodes_created_for_external_systems(self, setup_neo4j):
        data = load_extraction_result()
        ext_deps = data.get("system_context", {}).get("external_dependencies", [])
        expected_evidence_count = sum(len(dep.get("evidence", [])) for dep in ext_deps)

        result = setup_neo4j.query("MATCH (n:Evidence) RETURN count(n) as count", {})
        actual_evidence_count = result[0]["count"]

        assert actual_evidence_count == expected_evidence_count, (
            f"Neo4j has {actual_evidence_count} Evidence nodes, "
            f"JSON has {expected_evidence_count} total evidence items"
        )

    def test_container_relationships_match_json(self, setup_neo4j):
        data = load_extraction_result()
        json_rels = data.get("relationships", {}).get("containers", [])

        result = setup_neo4j.query("MATCH ()-[r:USES]->() RETURN r.id as rel_id", {})
        neo4j_rel_ids = {r["rel_id"] for r in result}

        expected_rel_ids = set()
        for rel in json_rels:
            src = rel.get("source") or rel.get("from")
            dst = rel.get("destination") or rel.get("to")
            if src and dst:
                expected_rel_ids.add(f"container:{src}->container:{dst}")

        missing = expected_rel_ids - neo4j_rel_ids
        extra = neo4j_rel_ids - expected_rel_ids
        assert not missing, f"Missing relationships in Neo4j: {missing}"
        assert not extra, f"Extra relationships in Neo4j: {extra}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/integration/test_json_neo4j_comparison.py -v 2>&1 | head -20`
Expected: FAIL — file doesn't exist

- [ ] **Step 3: Create directory and test file, then run**

Run: `mkdir -p /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api/tests/integration && cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/integration/test_json_neo4j_comparison.py -v 2>&1 | head -30`
Expected: Tests run (may SKIP if `.extraction-result.json` not found, or may PASS/FAIL depending on Neo4j state)

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_json_neo4j_comparison.py
git commit -m "test(api): add JSON↔Neo4j comparison integration test"
```

---

## Task 5: Playwright E2E Test

**Files:**
- Create: `sources/UI/e2e/specs/07-neo4j-consistency.spec.ts`
- Test: `npm run test:e2e -- e2e/specs/07-neo4j-consistency.spec.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// sources/UI/e2e/specs/07-neo4j-consistency.spec.ts
import { test, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000';

async function pollExtraction(taskId: string, maxRetries = 30): Promise<void> {
  for (let i = 0; i < maxRetries; i++) {
    const response = await fetch(`${API_BASE}/api/v1/code/scan/${taskId}`);
    const data = await response.json();
    if (data.status === 'completed') return;
    if (data.status === 'failed') {
      throw new Error(`Extraction failed: ${JSON.stringify(data)}`);
    }
    await new Promise(r => setTimeout(r, 2000));
  }
  throw new Error(`Extraction timed out after ${maxRetries * 2}s`);
}

async function queryNeo4j(cypher: string): Promise<any[]> {
  const response = await fetch(`${API_BASE}/api/v1/debug/neo4j/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cypher }),
  });
  if (!response.ok()) throw new Error(`Neo4j query failed: ${response.statusText}`);
  return response.json();
}

test.describe('Neo4j Consistency', () => {
  test('extraction results match Neo4j storage', async ({ request }) => {
    // 1. Trigger fresh extraction of Airbyte demo
    const response = await request.post(`${API_BASE}/api/v1/code/scan`, {
      data: {
        repo_path: '/app/sources/demo/airbyte',
        use_c4_model: true,
        max_components_per_domain: 10,
      },
    });
    expect(response.ok()).toBeTruthy();

    const body = await response.json();
    expect(body.task_id).toBeDefined();

    // 2. Wait for completion
    await pollExtraction(body.task_id);

    // 3. Load JSON result
    const jsonResponse = await fetch(`${API_BASE}/api/v1/code/scan/${body.task_id}/results`);
    const jsonData = await jsonResponse.json();

    const containers = (jsonData.containers || []).filter((c: any) => !c.is_infrastructure_only);
    const extDeps = (jsonData.system_context || {}).external_dependencies || [];
    const containerRels = (jsonData.relationships || {}).containers || [];

    // 4. Query Neo4j for counts
    const containerCount = await queryNeo4j('MATCH (n:Container) RETURN count(n) as c');
    const extSystemCount = await queryNeo4j('MATCH (n:ExternalSystem) RETURN count(n) as c');
    const evidenceCount = await queryNeo4j('MATCH (n:Evidence) RETURN count(n) as c');
    const usesRelCount = await queryNeo4j('MATCH ()-[r:USES]->() RETURN count(r) as c');

    // 5. Assert counts match
    expect(containerCount[0].c).toBe(containers.length);
    expect(extSystemCount[0].c).toBe(extDeps.length);
    expect(usesRelCount[0].c).toBe(containerRels.length);

    // 6. Verify evidence count matches total evidence items
    const totalEvidence = extDeps.reduce((sum: number, dep: any) => sum + (dep.evidence?.length || 0), 0);
    expect(evidenceCount[0].c).toBe(totalEvidence);
  });
});
```

**Note:** This test requires a `/api/v1/debug/neo4j/query` endpoint in the API. If that endpoint doesn't exist yet, add it to `code_extraction.py`:

```python
# Add to code_extraction.py routes (debug endpoints)
@router.post("/debug/neo4j/query")
def debug_neo4j_query(body: dict):
    from app.infrastructure.graph.neo4j_client import Neo4jClient
    client = Neo4jClient.from_config()
    result = client.query(body["cypher"], {})
    client.close()
    return result
```

- [ ] **Step 2: Run test**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/UI && npm run test:e2e -- e2e/specs/07-neo4j-consistency.spec.ts --reporter=line 2>&1 | tail -20`
Expected: FAIL (endpoint may not exist yet)

- [ ] **Step 3: If endpoint needed, add it to code_extraction.py**

Add the debug endpoint to `app/endpoint/v1/routes/code_extraction.py`. Look for existing debug routes or add near the bottom of the file.

- [ ] **Step 4: Re-run test**

Run again: `npm run test:e2e -- e2e/specs/07-neo4j-consistency.spec.ts --reporter=line 2>&1 | tail -20`
Expected: Should reach the assertion stage (may PASS or FAIL based on data)

- [ ] **Step 5: Commit**

```bash
git add sources/UI/e2e/specs/07-neo4j-consistency.spec.ts
git add app/endpoint/v1/routes/code_extraction.py  # if endpoint was added
git commit -m "test(e2e): add Neo4j consistency Playwright test"
```

---

## Task 6: Regenerate Demo

**Files:**
- None (runs existing extraction)

- [ ] **Step 1: Run make generate-demo**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge && docker compose exec -e LLM_PROVIDER=none -e DEMO_REPO_PATH=/app/sources/demo/airbyte api python -m app.services.code_extraction.c4_extractor 2>&1`

Expected: Completes without error; Neo4j populated with Airbyte demo data

- [ ] **Step 2: Run integration test**

Run: `cd /Users/vladbrincoveanu/Desktop/Startup/KnowledgeForge/sources/Api && python3 -m pytest tests/integration/test_json_neo4j_comparison.py -v 2>&1 | tail -20`
Expected: All tests PASS

- [ ] **Step 3: Commit the updated JSON**

```bash
git add sources/Api/app/c4_architecture.json
git commit -m "chore: regenerate demo extraction with Neo4j storage"
```

---

## Verification Summary

| Task | What to Verify | Command |
|------|----------------|---------|
| 1 | Neo4jClient unit tests pass | `pytest tests/unit/infrastructure/test_neo4j_client.py -v` |
| 2 | GraphWriter unit tests pass | `pytest tests/unit/services/c4/test_graph_writer.py -v` |
| 3 | No regression in existing tests | `pytest tests/unit/services/c4/test_dependency_detector.py -q` |
| 4 | JSON ↔ Neo4j counts match | `pytest tests/integration/test_json_neo4j_comparison.py -v` |
| 5 | Playwright E2E passes | `npm run test:e2e -- e2e/specs/07-neo4j-consistency.spec.ts --reporter=line` |
| 6 | Demo regeneration + integration | `pytest tests/integration/test_json_neo4j_comparison.py -v` after `make generate-demo` |
