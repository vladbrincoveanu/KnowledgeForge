# Design: Neo4j Graph Storage for Extraction Pipeline

**Date:** 2026-05-03
**Status:** Draft
**Type:** Infrastructure — Data Persistence

---

## Context

The KnowledgeForge extraction pipeline currently writes to JSON files only. Data flows: `Extraction → JSON file → API response → React UI`. There is no graph database backing.

The goal is to add Neo4j as a secondary storage layer written during extraction, enabling graph traversals and relationship queries that the current JSON-only architecture cannot serve.

---

## Architecture

```
C4ArchitectureExtractor.extract()
    │
    ├── 1. Detection & Classification (existing)
    ├── 2. JSON serialization (existing)
    │       └── writes: sources/data/c4_extractions/{task_id}.json
    │
    └── 3. Neo4j graph write (NEW)
            └── upserts nodes + relationships into Neo4j
```

**Upsert strategy:** Match on composite `id` key — existing nodes updated in-place. Each extraction run overwrites prior state.

---

## Neo4j Data Model

### Node ID Scheme

All nodes use composite key: `"${level}:${name}"`

Examples:
- `"context:System"`
- `"container:openapi2jsonschema"`
- `"component:PaymentController"`
- `"external_system:AWS S3"`
- `"person:CLI User"`

This ensures consistent ID matching between JSON and Neo4j, enabling comparison tests.

### Node Labels

| Label | Created From | Examples |
|-------|-------------|----------|
| `:System` | `system_context.name` | Airbyte |
| `:Container` | `containers[]` where `is_infrastructure_only != true` | openapi2jsonschema, docker, generator |
| `:Component` | `components[]` | PaymentController, OrderService |
| `:ExternalSystem` | `system_context.external_dependencies[]` | AWS S3, Stripe, PostgreSQL |
| `:Person` | `system_context.actors[]` | CLI User, Admin |
| `:Evidence` | `external_dependencies[].evidence[]` | Per-external-system evidence nodes |

### Node Properties

Each node stores:
- `id`: String — composite key (primary key for upsert)
- `name`: String — display name
- `entity_type`: String — entity type
- `level`: String — "context" | "container" | "component"
- `extraction_task_id`: String — links to extraction run
- `properties`: Map — all remaining fields as node properties

Property names use **snake_case** to match JSON/Python source (e.g., `classification_confidence`, `runtime_info`, `container_type`).

For `:ExternalSystem` nodes, `properties` includes: `provider`, `company`, `url`, `classification_confidence`, `decision_mode`, `review_status`, etc. The `evidence` array is NOT stored as a property — it is materialized as linked `:Evidence` nodes (see below).

For `:Container` nodes, `properties` includes: `technology`, `container_type`, `protocol`, `runtime_info`, `deployment`, `description`, `repository_url`, `health_endpoint`.

For `:Component` nodes, `properties` includes: `component_type`, `container`, `endpoint_path`, `endpoint_method`, `language`.

### Evidence Nodes (ExternalSystem)

Each evidence item from `external_dependencies[].evidence[]` becomes a `:Evidence` node linked via `:PROVIDED`:

| From | To | Type | Properties |
|------|----|------|------------|
| `:ExternalSystem` | `:Evidence` | `:PROVIDED` | `evidence_type`, `source`, `snippet` |

Evidence node ID: `"evidence:${external_system_id}:${index}"` (e.g., `"evidence:external_system:AWS S3:0"`).

### Relationship Types

| From | To | Type | Properties |
|------|----|------|------------|
| `:Container` | `:Container` | `:USES` | `protocol`, `description` |
| `:Container` | `:ExternalSystem` | `:USES` | `protocol`, `description` |
| `:Container` | `:Component` | `:CONTAINS` | — |
| `:System` | `:Person` | `:USES` | `description` |
| `:System` | `:ExternalSystem` | `:USES` | `description` |
| `:System` | `:Container` | `:USES` | `description` |

Relationship direction: **outbound from source** (e.g., Container USES ExternalSystem).

### Relationship ID Scheme

`"${sourceId}->${targetId}"` e.g., `"container:openapi2jsonschema->container:docker"`

---

## Components

### 1. `app/infrastructure/graph/neo4j_client.py`

**Responsibility:** Neo4j driver wrapper — connection management, upsert operations, queries.

**Interface:**
```python
class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j")
    def upsert_node(label: str, node_id: str, properties: dict) -> None
    def upsert_relationship(rel_type: str, rel_id: str, from_id: str, to_id: str, properties: dict) -> None
    def clear_extraction(task_id: str) -> None  # delete all nodes/rels for a task before re-writing
    def query(cypher: str, params: dict) -> list  # for testing/comparison
    def close() -> None
```

**Error handling:** All methods raise `GraphDatabaseError` on failure. Constructor raises if connection fails.

**Dependencies:** `neo4j` Python driver (via `pip install neo4j`)

### 2. `app/services/c4/graph_writer.py`

**Responsibility:** Maps extraction data to Neo4j operations. Called by `C4ArchitectureExtractor` after JSON save.

**Interface:**
```python
class GraphWriter:
    def __init__(self, neo4j_client: Neo4jClient)
    def write(self, task_id: str, c4_data: dict) -> None:
        """Main entry point. Writes all levels to Neo4j."""

    def _write_context_level(self, task_id: str, system_context: dict, relationships: list) -> None
    def _write_container_level(self, task_id: str, containers: list, relationships: list) -> None
    def _write_component_level(self, task_id: str, components: list, relationships: list) -> None
    def _write_evidence_nodes(self, external_system_id: str, evidence: list) -> None
    def _upsert_node(level: str, entity: dict) -> None
    def _upsert_relationship(rel_type: str, from_id: str, to_id: str, properties: dict) -> None
```

**Evidence handling:** `_write_evidence_nodes` is called when writing `:ExternalSystem` nodes. For each evidence item, creates an `:Evidence` node and links it via `:PROVIDED` relationship.

**Validation:** Before upserting, validates that `from_id` and `to_id` nodes exist. Logs warning and skips relationship if either node is missing.

**Dependencies:** `Neo4jClient`

### 3. `C4ArchitectureExtractor` modification

In `c4_extractor.py`, after JSON is saved:
```python
# After: _save_c4_to_json() call
try:
    graph_writer = GraphWriter(Neo4jClient.from_config())
    graph_writer.write(task_id, c4_data)
except GraphDatabaseError as e:
    logger.error(f"Neo4j write failed, extraction aborting: {e}")
    raise  # extraction fails if Neo4j unavailable (per design decision)
```

---

## Testing Strategy

### Unit Tests

**`test_neo4j_client.py`:**
- Mock `neo4j.Driver` — test upsert_node with correct Cypher
- Test upsert_relationship generates correct MERGE pattern
- Test clear_extraction deletes nodes for task_id
- Test constructor raises on bad connection

**`test_graph_writer.py`:**
- Mock `Neo4jClient` — test that write() calls correct node/rel operations
- Test that correct labels are used for each entity type
- Test that missing target node causes relationship to be skipped (warning logged)
- Test all three levels (context/container/component) are written
- Test evidence nodes are created for ExternalSystem nodes

### Integration Tests

**`test_json_neo4j_comparison.py`:**
- Extracts Airbyte fixture (or loads from `.extraction-result.json`)
- Queries Neo4j for node counts by label
- Compares against JSON counts:
  - `:Container` count == `len(containers[])` (filtered)
  - `:ExternalSystem` count == `len(system_context.external_dependencies[])`
  - `:Evidence` count == total number of evidence items across all external dependencies
  - `:Component` count == `len(components[])`
  - `:System` count == 1
- Verifies `:PROVIDED` relationship count matches total evidence count
- Queries specific relationships and verifies properties match JSON

**Run via:** `cd sources/Api && python3 -m pytest tests/integration/test_json_neo4j_comparison.py -v`

### E2E Playwright Test

**`07-neo4j-consistency.spec.ts`:**
1. Ensure demo extraction is fresh (or trigger re-extraction)
2. Load `.extraction-result.json`
3. `POST /api/v1/code/scan` with `repo_path="/app/sources/demo/airbyte"`
4. Poll until `status === "completed"`
5. Query Neo4j via Python subprocess (or HTTP to Neo4j browser API)
6. Assert:
   - Node count by label matches JSON entity counts
   - Relationship count matches JSON relationship counts
   - Sample relationship properties match JSON

---

## Implementation Order

1. **`neo4j_client.py`** — driver wrapper, no external dependencies on extraction code
2. **`test_neo4j_client.py`** — unit tests for client
3. **`graph_writer.py`** — mapping layer
4. **`test_graph_writer.py`** — unit tests for writer
5. **`C4ArchitectureExtractor` modification** — integrate write call
6. **`test_json_neo4j_comparison.py`** — integration test comparing JSON and Neo4j
7. **Playwright E2E test** `07-neo4j-consistency.spec.ts`
8. **`make generate-demo`** — regenerate demo to populate Neo4j

---

## Dependencies

- `neo4j>=5.x` Python driver
- Neo4j database running (configured via environment: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`)
- If Neo4j unavailable during extraction: **extraction fails** (per design decision)

---

## Open Questions

All design decisions resolved. No open questions remaining.
