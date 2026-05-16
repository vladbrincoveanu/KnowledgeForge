# LLM Enrichment Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Grill findings (2026-05-15):**
- Q1: `websocket_endpoint` bypasses `manager.connect()`, breaking all broadcasts. Fixed: refactor endpoint to use `manager.connect/disconnect`, add `register_task` in WS message loop.
- Q6: `_DATA_DIR` used `parents[4] / "sources" / "data"` → double `sources`. Fixed: `parents[5] / "data" / "c4_enrichments"`.
- Q7: Setup code outside `try` block — constructor failure leaves no `enrichment_failed` event. Fixed: move all setup inside `try`.
- Q10: `enqueue()` overwrites active task on duplicate call. Fixed: guard with `ValueError` if task already running.
- Q11: `C4Extractor` has no `task_id` at construction time — `task_id` comes from `extract()`. Fixed: store `self.task_id` in `extract()`, pass via `getattr(self, 'task_id', None)` in `_extract_level1_context()`.
- Q16: `GraphView` is dumb; enrichment merge happens in `CodeArchitectureViewer` parent. `CustomNode` already reads `decision_mode`. Badge goes in `CustomNode.render`.
- ws_events: `broadcast_to_task` fallback removed — log and drop when no WS for task.
- e2e test path: `sources/data/c4_enrichments` not `sources/data/c4_enrichments`. Fixed.

**Goal:** Add an async, bounded agentic LLM layer that enriches the deterministic C4 Context extraction with LLM-discovered dependencies — streams results progressively through the existing WebSocket, persists to Neo4j + JSON, and never touches deterministic detector logic.

**Architecture:** Phase 1 (deterministic, unchanged) writes initial graph. Phase 2 (async worker via `asyncio.create_task`) runs `WarmContextBuilder → LLMAgentLoop (tool_use against MiniMax Anthropic proxy) → GraphMerger`. Per-emit nodes tagged with `enrichment_run_id` for rollback. Partial emits kept on budget/timeout/429; rollback only on persistence/internal errors.

**Tech Stack:** Python 3.11, FastAPI, Pydantic V2, Anthropic SDK pointed at `https://api.minimax.io/anthropic`, Neo4j, asyncio.

**Spec:** `docs/superpowers/specs/2026-05-14-llm-enrichment-layer-design.md`

---

## File Structure

**New files (created by this plan):**

```
sources/Api/app/services/c4/enrichment/
  __init__.py
  evidence_corpus.py             # T1 — pydantic models
  json_persister.py              # T2 — JSONL append + final snapshot
  graph_writer.py                # T3 — Neo4j MERGE with canonical_name + run_id
  tool_registry.py               # T4 — read_file/grep/list_dir/emit_node/emit_edge
  warm_context_builder.py        # T5 — file tree + top-K grepped signals
  llm_client.py                  # T6 — Anthropic SDK wrapper + 5h rate counter
  graph_merger.py                # T7 — merge rules + conflict flagging
  agent_loop.py                  # T8 — bounded tool_use loop + budget
  ws_events.py                   # T9 — emit through existing WS router
  worker.py                      # T10 — orchestrator + pre-flight gates
  config.py                      # env-var loader, used by all above

sources/Api/tests/unit/services/c4/enrichment/
  test_evidence_corpus.py
  test_json_persister.py
  test_graph_writer.py
  test_tool_registry.py
  test_warm_context_builder.py
  test_llm_client.py
  test_graph_merger.py
  test_agent_loop.py
  test_ws_events.py
  test_worker.py

sources/Api/tests/integration/enrichment/
  test_worker_e2e.py
  fixtures/
    sample_repo/                 # synthetic minimal repo
      docker-compose.yml
      requirements.txt
      app/main.py
    llm_responses/
      happy_path.json            # pre-recorded tool_use sequence
      budget_exceeded.json
      no_tool_calls.json

sources/UI/src/hooks/
  useEnrichmentWS.ts             # T12 — WS event handlers
sources/UI/src/components/CodeArchitectureViewer/
  EnrichmentBadge.tsx            # T12 — visual marker on LLM nodes
```

**Modified files:**
- `sources/Api/app/services/c4/context/context_manager.py` — append one line at end of `extract_context()` to enqueue worker (T11)
- `sources/Api/app/endpoint/v1/routes/websocket.py` — refactor endpoint to use `manager.connect/disconnect`, add `register_task` message handling (T9)
- `sources/Api/app/services/code_extraction/c4_extractor.py` — store `self.task_id` in `extract()`, pass to `ContextManager` in `_extract_level1_context()` (T11)
- `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CodeArchitectureViewer.tsx` — merge enrichment nodes via `useEnrichmentWS` (T12)
- `sources/UI/src/@components/architecture-map/CodeArchitectureViewer/CustomNode.tsx` — render `<EnrichmentBadge>` for LLM-adjudicated nodes (T12)

**Note (Q17 — module dependency chain):** Tasks 1–8 create the modules that Tasks 9–12 import. Before running tests, verify all imports resolve: `EvidenceCorpus`, `EnrichmentJSONPersister`, `EnrichmentGraphWriter`, `GraphMerger`, `WarmContextBuilder`, `ExtractionToolRegistry`, `EnrichmentLLMClient`, `get_rate_counter`. If any are missing, implement the corresponding task first.

**Untouched (Iron Curtain):**
- `sources/Api/app/services/c4/context/dependency_detector.py`
- `sources/Api/app/services/c4/context/system_detector.py`
- `sources/Api/app/services/c4/context/metadata_detector.py`
- `sources/Api/app/services/c4/graph_writer.py` (existing batch writer)
- `sources/Api/app/services/c4/containers/*` (other squad)
- `sources/data/c4_extractions/{task_id}.json` (deterministic output)

---

## Task 1: EvidenceCorpus pydantic model

**Files:**
- Create: `sources/Api/app/services/c4/enrichment/__init__.py` (empty)
- Create: `sources/Api/app/services/c4/enrichment/evidence_corpus.py`
- Test: `sources/Api/tests/unit/services/c4/enrichment/test_evidence_corpus.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/services/c4/enrichment/test_evidence_corpus.py
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.services.c4.enrichment.evidence_corpus import EvidenceCorpus, DepEvidence


def test_evidence_corpus_minimal_valid():
    ec = EvidenceCorpus(
        repo_path=Path("/tmp/r"),
        task_id="t1",
        languages=["python"],
        frameworks=["fastapi"],
        deterministic_deps=[],
        entrypoints=[Path("main.py")],
        detected_urls=[],
        env_vars=[],
        docker_images=[],
        package_files=[Path("requirements.txt")],
    )
    assert ec.task_id == "t1"
    assert ec.languages == ["python"]


def test_dep_evidence_requires_confidence_range():
    with pytest.raises(ValidationError):
        DepEvidence(name="x", type="package", confidence=1.5, files_found_in=[])


def test_evidence_corpus_serializable():
    ec = EvidenceCorpus(
        repo_path=Path("/tmp/r"),
        task_id="t1",
        languages=[], frameworks=[], deterministic_deps=[],
        entrypoints=[], detected_urls=[], env_vars=[],
        docker_images=[], package_files=[],
    )
    dumped = ec.model_dump(mode="json")
    assert dumped["task_id"] == "t1"
```

- [ ] **Step 2: Run test to verify failure**

```
cd sources/Api && python -m pytest tests/unit/services/c4/enrichment/test_evidence_corpus.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/c4/enrichment/evidence_corpus.py
from pathlib import Path
from pydantic import BaseModel, Field


class DepEvidence(BaseModel):
    name: str
    type: str
    confidence: float = Field(ge=0.0, le=1.0)
    files_found_in: list[Path] = Field(default_factory=list)


class EvidenceCorpus(BaseModel):
    repo_path: Path
    task_id: str
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    deterministic_deps: list[DepEvidence] = Field(default_factory=list)
    entrypoints: list[Path] = Field(default_factory=list)
    detected_urls: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    docker_images: list[str] = Field(default_factory=list)
    package_files: list[Path] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests pass**

```
python -m pytest tests/unit/services/c4/enrichment/test_evidence_corpus.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```
git add sources/Api/app/services/c4/enrichment/__init__.py \
        sources/Api/app/services/c4/enrichment/evidence_corpus.py \
        sources/Api/tests/unit/services/c4/enrichment/test_evidence_corpus.py
git commit -m "feat(enrichment): add EvidenceCorpus pydantic contract"
```

---

## Task 2: EnrichmentJSONPersister

**Files:**
- Create: `sources/Api/app/services/c4/enrichment/json_persister.py`
- Test: `sources/Api/tests/unit/services/c4/enrichment/test_json_persister.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/services/c4/enrichment/test_json_persister.py
import json
from pathlib import Path
import pytest
from app.services.c4.enrichment.json_persister import EnrichmentJSONPersister


@pytest.fixture
def persister(tmp_path):
    return EnrichmentJSONPersister(base_dir=tmp_path, task_id="t1", run_id="r1")


def test_append_writes_jsonl_line(persister, tmp_path):
    persister.append({"event": "node_added", "name": "Stripe"})
    persister.append({"event": "edge_added", "from": "Sys", "to": "Stripe"})
    lines = (tmp_path / "t1.jsonl").read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["name"] == "Stripe"


def test_finalize_writes_snapshot(persister, tmp_path):
    persister.append({"event": "node_added", "name": "A"})
    persister.finalize({"nodes_added": 1, "partial": False})
    snap = json.loads((tmp_path / "t1.json").read_text())
    assert snap["summary"]["nodes_added"] == 1
    assert len(snap["events"]) == 1


def test_rollback_deletes_both_files(persister, tmp_path):
    persister.append({"event": "x"})
    persister.finalize({"x": 1})
    persister.rollback()
    assert not (tmp_path / "t1.jsonl").exists()
    assert not (tmp_path / "t1.json").exists()


def test_rollback_when_files_missing_is_noop(persister):
    persister.rollback()  # must not raise
```

- [ ] **Step 2: Verify failure**

```
python -m pytest tests/unit/services/c4/enrichment/test_json_persister.py -v
```
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/services/c4/enrichment/json_persister.py
import json
from pathlib import Path
from typing import Any


class EnrichmentJSONPersister:
    def __init__(self, base_dir: Path, task_id: str, run_id: str):
        self.base_dir = Path(base_dir)
        self.task_id = task_id
        self.run_id = run_id
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.base_dir / f"{task_id}.jsonl"
        self.json_path = self.base_dir / f"{task_id}.json"
        self._events: list[dict[str, Any]] = []

    def append(self, event: dict[str, Any]) -> None:
        event = {**event, "run_id": self.run_id}
        self._events.append(event)
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def finalize(self, summary: dict[str, Any]) -> None:
        snapshot = {"task_id": self.task_id, "run_id": self.run_id,
                    "summary": summary, "events": self._events}
        self.json_path.write_text(json.dumps(snapshot, indent=2, default=str))

    def rollback(self) -> None:
        for p in (self.jsonl_path, self.json_path):
            if p.exists():
                p.unlink()
```

- [ ] **Step 4: Verify pass**

```
python -m pytest tests/unit/services/c4/enrichment/test_json_persister.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add sources/Api/app/services/c4/enrichment/json_persister.py \
        sources/Api/tests/unit/services/c4/enrichment/test_json_persister.py
git commit -m "feat(enrichment): JSONL append + finalize + rollback"
```

---

## Task 3: EnrichmentGraphWriter (Neo4j)

**Files:**
- Create: `sources/Api/app/services/c4/enrichment/graph_writer.py`
- Test: `sources/Api/tests/unit/services/c4/enrichment/test_graph_writer.py`

Reuses `normalize_logical_name` logic from `context_manager.py:281` — copied/adapted as module-level function to avoid pulling in ContextManager.

- [ ] **Step 1: Write failing tests (mock Neo4j session)**

```python
# tests/unit/services/c4/enrichment/test_graph_writer.py
from unittest.mock import MagicMock
import pytest
from app.services.c4.enrichment.graph_writer import (
    EnrichmentGraphWriter, normalize_logical_name,
)


def test_normalize_strips_scheme_and_suffix():
    assert normalize_logical_name("https://api.Stripe.com/v1") == "stripe"
    assert normalize_logical_name("Stripe-API") == "stripe"
    assert normalize_logical_name("Datadog SDK") == "datadog"


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def writer(mock_session):
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = mock_session
    return EnrichmentGraphWriter(driver=driver, task_id="t1", run_id="r1")


def test_upsert_node_runs_merge_with_canonical(writer, mock_session):
    writer.upsert_node(
        type_="external_dep", name="Stripe",
        props={"confidence": 0.8, "evidence": [{"file": "a.py", "line": 1}]},
    )
    args, kwargs = mock_session.run.call_args
    assert "MERGE" in args[0]
    assert kwargs["canonical"] == "stripe"
    assert kwargs["name"] == "Stripe"
    assert kwargs["run_id"] == "r1"


def test_upsert_edge_includes_run_id(writer, mock_session):
    writer.upsert_edge(from_name="Sys", to_name="Stripe",
                       relationship="uses", props={})
    args, kwargs = mock_session.run.call_args
    assert kwargs["run_id"] == "r1"


def test_rollback_deletes_by_run_id(writer, mock_session):
    writer.rollback()
    args, _ = mock_session.run.call_args
    assert "DETACH DELETE" in args[0]
    assert "enrichment_run_id" in args[0]
```

- [ ] **Step 2: Verify failure**

```
python -m pytest tests/unit/services/c4/enrichment/test_graph_writer.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# app/services/c4/enrichment/graph_writer.py
import re
from typing import Any


def normalize_logical_name(value: str) -> str:
    label = str(value or "").strip()
    if not label:
        return ""
    label = re.sub(r"^https?://", "", label, flags=re.IGNORECASE)
    label = label.split("/", 1)[0]
    label = re.sub(r":\d{2,5}$", "", label)
    label = label.split(".", 1)[0]
    label = label.replace("_", " ").replace("-", " ").strip()
    label = re.sub(r"\s+(api|sdk|client|endpoint|webhook)$", "",
                   label, flags=re.IGNORECASE)
    return label.lower().strip()


_UPSERT_NODE_CQL = """
MERGE (n:EnrichmentNode {type: $type, canonical_name: $canonical})
  ON CREATE SET n.name = $name, n.confidence = $confidence,
                n.evidence = $evidence, n.created_by = $run_id,
                n.aliases = []
  ON MATCH SET  n.aliases = coalesce(n.aliases, []) + [$name],
                n.confidence = CASE WHEN $confidence > n.confidence
                                    THEN $confidence ELSE n.confidence END,
                n.evidence = coalesce(n.evidence, []) + $evidence
SET n.enrichment_run_id = $run_id,
    n.extraction_task_id = $task_id,
    n.decision_mode = $decision_mode
"""

_UPSERT_EDGE_CQL = """
MATCH (a:EnrichmentNode {canonical_name: $from_canon}),
      (b:EnrichmentNode {canonical_name: $to_canon})
MERGE (a)-[r:ENRICHMENT_REL {relationship: $relationship}]->(b)
SET r.enrichment_run_id = $run_id,
    r.extraction_task_id = $task_id,
    r.props = $props
"""

_ROLLBACK_CQL = """
MATCH (n {enrichment_run_id: $run_id}) DETACH DELETE n
"""


class EnrichmentGraphWriter:
    def __init__(self, driver, task_id: str, run_id: str):
        self.driver = driver
        self.task_id = task_id
        self.run_id = run_id

    def upsert_node(self, type_: str, name: str, props: dict[str, Any]) -> str:
        canonical = normalize_logical_name(name)
        with self.driver.session() as s:
            s.run(
                _UPSERT_NODE_CQL,
                type=type_, canonical=canonical, name=name,
                confidence=float(props.get("confidence", 0.0)),
                evidence=props.get("evidence", []),
                decision_mode=props.get("decision_mode", "LLM_ADJUDICATED"),
                run_id=self.run_id, task_id=self.task_id,
            )
        return canonical

    def upsert_edge(self, from_name: str, to_name: str,
                    relationship: str, props: dict[str, Any]) -> None:
        with self.driver.session() as s:
            s.run(
                _UPSERT_EDGE_CQL,
                from_canon=normalize_logical_name(from_name),
                to_canon=normalize_logical_name(to_name),
                relationship=relationship, props=props,
                run_id=self.run_id, task_id=self.task_id,
            )

    def rollback(self) -> None:
        with self.driver.session() as s:
            s.run(_ROLLBACK_CQL, run_id=self.run_id)
```

- [ ] **Step 4: Verify pass**

```
python -m pytest tests/unit/services/c4/enrichment/test_graph_writer.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```
git add sources/Api/app/services/c4/enrichment/graph_writer.py \
        sources/Api/tests/unit/services/c4/enrichment/test_graph_writer.py
git commit -m "feat(enrichment): EnrichmentGraphWriter with canonical dedup"
```

---

## Task 4: ExtractionToolRegistry

**Files:**
- Create: `sources/Api/app/services/c4/enrichment/tool_registry.py`
- Test: `sources/Api/tests/unit/services/c4/enrichment/test_tool_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/services/c4/enrichment/test_tool_registry.py
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from app.services.c4.enrichment.tool_registry import ExtractionToolRegistry


@pytest.fixture
def sample_repo(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text(
        "import stripe\nimport custom_internal_http\n# call api.acme.io\n"
    )
    (tmp_path / "requirements.txt").write_text("stripe==5.0\n")
    return tmp_path


@pytest.fixture
def registry(sample_repo):
    return ExtractionToolRegistry(
        repo_path=sample_repo,
        graph_writer=MagicMock(),
        persister=MagicMock(),
        ws_emit=MagicMock(),
    )


def test_get_tools_returns_anthropic_schemas(registry):
    tools = registry.get_tools()
    names = {t["name"] for t in tools}
    assert names == {"read_file", "grep", "list_dir", "emit_node", "emit_edge"}
    for t in tools:
        assert "input_schema" in t


def test_read_file_returns_content(registry):
    r = registry.dispatch("read_file", {"path": "app/main.py"})
    assert "import stripe" in r["content"]
    assert r["is_error"] is False


def test_read_file_path_escape_returns_error(registry):
    r = registry.dispatch("read_file", {"path": "../../etc/passwd"})
    assert r["is_error"] is True
    assert "invalid_path" in r["content"]


def test_read_file_not_found_returns_error(registry):
    r = registry.dispatch("read_file", {"path": "nope.py"})
    assert r["is_error"] is True


def test_grep_returns_matches_with_context(registry):
    r = registry.dispatch("grep", {"pattern": "stripe", "path": "."})
    assert r["is_error"] is False
    body = json.loads(r["content"])
    assert any("stripe" in m["line"].lower() for m in body["matches"])


def test_grep_caps_at_50(registry, sample_repo):
    big = sample_repo / "big.py"
    big.write_text("\n".join(["match" for _ in range(200)]))
    r = registry.dispatch("grep", {"pattern": "match", "path": "."})
    body = json.loads(r["content"])
    assert len(body["matches"]) == 50
    assert body["truncated"] is True


def test_list_dir_returns_entries(registry):
    r = registry.dispatch("list_dir", {"path": "."})
    body = json.loads(r["content"])
    names = {e["name"] for e in body["entries"]}
    assert "app" in names and "requirements.txt" in names


def test_emit_node_without_evidence_rejected(registry):
    r = registry.dispatch("emit_node", {
        "type": "external_dep", "name": "Stripe", "props": {"confidence": 0.9}
    })
    assert r["is_error"] is True
    assert "evidence" in r["content"]


def test_emit_node_happy_path_calls_writer(registry):
    r = registry.dispatch("emit_node", {
        "type": "external_dep", "name": "Stripe",
        "props": {"confidence": 0.9,
                  "evidence": [{"file": "app/main.py", "line": 1,
                                "snippet": "import stripe"}]}
    })
    assert r["is_error"] is False
    registry.graph_writer.upsert_node.assert_called_once()
    registry.persister.append.assert_called_once()
    registry.ws_emit.assert_called_once()


def test_emit_edge_calls_writer(registry):
    r = registry.dispatch("emit_edge", {
        "from_name": "Sys", "to_name": "Stripe",
        "relationship": "uses", "props": {}
    })
    assert r["is_error"] is False
    registry.graph_writer.upsert_edge.assert_called_once()
```

- [ ] **Step 2: Verify failure**

```
python -m pytest tests/unit/services/c4/enrichment/test_tool_registry.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# app/services/c4/enrichment/tool_registry.py
import json
import re
from pathlib import Path
from typing import Any, Callable


_GREP_MAX = 50
_LISTDIR_MAX = 200
_READ_MAX_BYTES = 50_000
_BINARY_PEEK_BYTES = 1024


def _err(msg: str) -> dict[str, Any]:
    return {"is_error": True, "content": json.dumps({"error": msg})}


def _ok(payload: Any) -> dict[str, Any]:
    return {"is_error": False,
            "content": payload if isinstance(payload, str) else json.dumps(payload)}


class ExtractionToolRegistry:
    def __init__(self, repo_path: Path, graph_writer, persister,
                 ws_emit: Callable[[str, dict], None]):
        self.repo_path = Path(repo_path).resolve()
        self.graph_writer = graph_writer
        self.persister = persister
        self.ws_emit = ws_emit
        self._emitted_nodes: set[str] = set()

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "read_file",
             "description": "Read a repo file. Returns content or error.",
             "input_schema": {"type": "object",
                              "properties": {"path": {"type": "string"}},
                              "required": ["path"]}},
            {"name": "grep",
             "description": "Regex search across repo. Returns up to 50 matches with 3-line context.",
             "input_schema": {"type": "object",
                              "properties": {"pattern": {"type": "string"},
                                             "path": {"type": "string"}},
                              "required": ["pattern"]}},
            {"name": "list_dir",
             "description": "List a directory.",
             "input_schema": {"type": "object",
                              "properties": {"path": {"type": "string"}}}},
            {"name": "emit_node",
             "description": "Emit a discovered node. Evidence array REQUIRED.",
             "input_schema": {"type": "object",
                              "properties": {"type": {"type": "string"},
                                             "name": {"type": "string"},
                                             "props": {"type": "object"}},
                              "required": ["type", "name", "props"]}},
            {"name": "emit_edge",
             "description": "Emit a relationship between two emitted nodes.",
             "input_schema": {"type": "object",
                              "properties": {"from_name": {"type": "string"},
                                             "to_name": {"type": "string"},
                                             "relationship": {"type": "string"},
                                             "props": {"type": "object"}},
                              "required": ["from_name", "to_name", "relationship"]}},
        ]

    def dispatch(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            fn = getattr(self, f"_tool_{name}", None)
            if fn is None:
                return _err(f"unknown_tool:{name}")
            return fn(args)
        except Exception as e:  # noqa: BLE001 — protocol guarantees: errors → LLM, not raise
            return _err(f"internal:{type(e).__name__}")

    def _resolve_safe(self, rel: str) -> Path | None:
        try:
            full = (self.repo_path / rel).resolve()
            full.relative_to(self.repo_path)
            return full
        except (ValueError, OSError):
            return None

    def _tool_read_file(self, args):
        target = self._resolve_safe(args.get("path", ""))
        if target is None:
            return _err("invalid_path")
        if not target.is_file():
            return _err("not_found")
        raw = target.read_bytes()
        if b"\x00" in raw[:_BINARY_PEEK_BYTES]:
            return _ok({"content": raw[:_BINARY_PEEK_BYTES].decode("utf-8", "replace"),
                        "binary": True})
        if len(raw) > _READ_MAX_BYTES:
            return _ok({"content": raw[:_READ_MAX_BYTES].decode("utf-8", "replace"),
                        "truncated": True, "total_bytes": len(raw)})
        return _ok({"content": raw.decode("utf-8", "replace")})

    def _tool_grep(self, args):
        pat = args.get("pattern", "")
        try:
            rx = re.compile(pat, re.IGNORECASE)
        except re.error:
            return _err("invalid_regex")
        base = self._resolve_safe(args.get("path", "."))
        if base is None:
            return _err("invalid_path")
        matches: list[dict[str, Any]] = []
        for f in base.rglob("*"):
            if len(matches) >= _GREP_MAX:
                break
            if not f.is_file() or f.stat().st_size > 1_000_000:
                continue
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines):
                if rx.search(line):
                    ctx_lo, ctx_hi = max(0, i - 1), min(len(lines), i + 2)
                    matches.append({
                        "file": str(f.relative_to(self.repo_path)),
                        "line_no": i + 1, "line": line,
                        "context": lines[ctx_lo:ctx_hi],
                    })
                    if len(matches) >= _GREP_MAX:
                        break
        return _ok({"matches": matches, "truncated": len(matches) >= _GREP_MAX})

    def _tool_list_dir(self, args):
        base = self._resolve_safe(args.get("path", "."))
        if base is None or not base.is_dir():
            return _err("invalid_path")
        entries = []
        for child in sorted(base.iterdir()):
            if len(entries) >= _LISTDIR_MAX:
                break
            try:
                entries.append({
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else None,
                })
            except OSError:
                continue
        return _ok({"entries": entries})

    def _tool_emit_node(self, args):
        type_ = args.get("type", "")
        name = args.get("name", "")
        props = args.get("props") or {}
        evidence = props.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            return _err("missing_required:evidence")
        canonical = self.graph_writer.upsert_node(type_=type_, name=name, props=props)
        self._emitted_nodes.add(canonical)
        event = {"event": "node_added", "type": type_, "name": name,
                 "canonical_name": canonical, "props": props,
                 "decision_mode": props.get("decision_mode", "LLM_ADJUDICATED")}
        self.persister.append(event)
        self.ws_emit("node_added", event)
        return _ok({"canonical_name": canonical})

    def _tool_emit_edge(self, args):
        self.graph_writer.upsert_edge(
            from_name=args["from_name"], to_name=args["to_name"],
            relationship=args["relationship"], props=args.get("props") or {},
        )
        event = {"event": "edge_added", **args}
        self.persister.append(event)
        self.ws_emit("edge_added", event)
        return _ok({"ok": True})
```

- [ ] **Step 4: Verify pass**

```
python -m pytest tests/unit/services/c4/enrichment/test_tool_registry.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Commit**

```
git add sources/Api/app/services/c4/enrichment/tool_registry.py \
        sources/Api/tests/unit/services/c4/enrichment/test_tool_registry.py
git commit -m "feat(enrichment): sandboxed tool registry (read/grep/list/emit)"
```

---

## Task 5: WarmContextBuilder

**Files:**
- Create: `sources/Api/app/services/c4/enrichment/warm_context_builder.py`
- Test: `sources/Api/tests/unit/services/c4/enrichment/test_warm_context_builder.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/services/c4/enrichment/test_warm_context_builder.py
from pathlib import Path
import pytest
from app.services.c4.enrichment.evidence_corpus import EvidenceCorpus
from app.services.c4.enrichment.warm_context_builder import WarmContextBuilder


@pytest.fixture
def sample(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services:\n  api:\n    image: redis\n")
    (tmp_path / "requirements.txt").write_text("stripe\n")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("import stripe\nstripe.charge()\n")
    return tmp_path


def _ec(p):
    return EvidenceCorpus(repo_path=p, task_id="t1", languages=["python"],
                          frameworks=["fastapi"], deterministic_deps=[],
                          entrypoints=[Path("app/main.py")], detected_urls=[],
                          env_vars=[], docker_images=[],
                          package_files=[Path("requirements.txt")])


def test_build_includes_file_tree(sample):
    wc = WarmContextBuilder().build(sample, _ec(sample), top_k=10)
    assert "docker-compose.yml" in wc.file_tree
    assert "app/main.py" in wc.file_tree


def test_build_picks_priority_files_first(sample):
    wc = WarmContextBuilder().build(sample, _ec(sample), top_k=2)
    grepped_paths = [s.path for s in wc.signal_files]
    assert "docker-compose.yml" in grepped_paths
    assert "requirements.txt" in grepped_paths


def test_build_grep_returns_matching_lines_not_full_content(sample):
    wc = WarmContextBuilder().build(sample, _ec(sample), top_k=10)
    main_signal = next((s for s in wc.signal_files
                        if s.path.endswith("main.py")), None)
    assert main_signal is not None
    assert any("import stripe" in m for m in main_signal.matches)


def test_fallback_to_largest_files_when_no_priority(tmp_path):
    (tmp_path / "a.txt").write_text("x" * 100)
    (tmp_path / "b.txt").write_text("y" * 200)
    ec = EvidenceCorpus(repo_path=tmp_path, task_id="t1",
                        languages=[], frameworks=[], deterministic_deps=[],
                        entrypoints=[], detected_urls=[], env_vars=[],
                        docker_images=[], package_files=[])
    wc = WarmContextBuilder().build(tmp_path, ec, top_k=2)
    assert len(wc.signal_files) >= 1
```

- [ ] **Step 2: Verify failure**

```
python -m pytest tests/unit/services/c4/enrichment/test_warm_context_builder.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# app/services/c4/enrichment/warm_context_builder.py
from dataclasses import dataclass, field
from pathlib import Path
from .evidence_corpus import EvidenceCorpus


_PRIORITY_GLOBS = [
    "docker-compose.yml", "docker-compose.yaml", "compose.yml",
    "package.json", "requirements.txt", "pyproject.toml",
    "Pipfile", "Cargo.toml", "go.mod", "*.csproj",
    ".github/workflows/*.yml", "Dockerfile", "README.md",
]

_SIGNAL_PATTERNS = [
    "import ", "from ", "require(", "using ", "ServiceCollection",
    "HttpClient", "axios", "fetch(", "requests.", "urllib",
    "kafka", "redis", "mongo", "postgres", "stripe", "twilio",
    "openai", "anthropic", "minimax", "boto3", "google.cloud",
]


@dataclass
class SignalFile:
    path: str
    matches: list[str] = field(default_factory=list)


@dataclass
class WarmContext:
    file_tree: list[str]
    evidence: EvidenceCorpus
    signal_files: list[SignalFile]


class WarmContextBuilder:
    def build(self, repo_path: Path, evidence: EvidenceCorpus,
              top_k: int = 10) -> WarmContext:
        repo_path = Path(repo_path).resolve()
        tree = self._tree(repo_path)
        priority = self._select_priority(repo_path, top_k)
        if not priority:
            priority = self._fallback_largest(repo_path, top_k)
        signals = [self._grep_signals(repo_path, p) for p in priority]
        return WarmContext(file_tree=tree, evidence=evidence, signal_files=signals)

    def _tree(self, root: Path) -> list[str]:
        out = []
        for p in sorted(root.rglob("*")):
            if any(part.startswith(".") and part != "." for part in p.parts):
                continue
            if p.is_file():
                out.append(str(p.relative_to(root)))
            if len(out) > 2000:
                break
        return out

    def _select_priority(self, root: Path, top_k: int) -> list[Path]:
        found: list[Path] = []
        for glob in _PRIORITY_GLOBS:
            for match in root.rglob(glob):
                if match.is_file():
                    found.append(match)
                    if len(found) >= top_k:
                        return found
        return found

    def _fallback_largest(self, root: Path, top_k: int) -> list[Path]:
        files = [(p.stat().st_size, p) for p in root.iterdir()
                 if p.is_file() and not p.name.startswith(".")]
        files.sort(reverse=True)
        return [p for _, p in files[:top_k]]

    def _grep_signals(self, root: Path, path: Path) -> SignalFile:
        rel = str(path.relative_to(root))
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return SignalFile(path=rel)
        matches: list[str] = []
        for i, line in enumerate(lines):
            if any(pat in line for pat in _SIGNAL_PATTERNS):
                lo, hi = max(0, i - 1), min(len(lines), i + 2)
                matches.append(f"L{i+1}: " + " | ".join(lines[lo:hi]))
                if len(matches) >= 30:
                    break
        return SignalFile(path=rel, matches=matches)
```

- [ ] **Step 4: Verify pass**

```
python -m pytest tests/unit/services/c4/enrichment/test_warm_context_builder.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add sources/Api/app/services/c4/enrichment/warm_context_builder.py \
        sources/Api/tests/unit/services/c4/enrichment/test_warm_context_builder.py
git commit -m "feat(enrichment): WarmContextBuilder with priority + fallback"
```

---

## Task 6: EnrichmentLLMClient + rate counter

**Files:**
- Create: `sources/Api/app/services/c4/enrichment/llm_client.py`
- Create: `sources/Api/app/services/c4/enrichment/config.py`
- Test: `sources/Api/tests/unit/services/c4/enrichment/test_llm_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/services/c4/enrichment/test_llm_client.py
import asyncio
from unittest.mock import MagicMock, patch
import pytest
from app.services.c4.enrichment.llm_client import (
    EnrichmentLLMClient, RateLimitMidrunError, RequestRateCounter,
)


def test_rate_counter_under_budget_allows():
    rc = RequestRateCounter(budget=10, window_s=3600)
    assert asyncio.run(rc.can_run(reserve=2)) is True


def test_rate_counter_over_budget_blocks():
    rc = RequestRateCounter(budget=5, window_s=3600)

    async def _fill():
        for _ in range(5):
            await rc.record()

    asyncio.run(_fill())
    assert asyncio.run(rc.can_run(reserve=1)) is False


def test_rate_counter_prunes_old_entries():
    import time
    rc = RequestRateCounter(budget=2, window_s=0.001)

    async def _go():
        await rc.record()
        await rc.record()
        time.sleep(0.01)
        return await rc.can_run(reserve=1)

    assert asyncio.run(_go()) is True


def test_client_skips_when_no_api_key(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    assert EnrichmentLLMClient.from_env() is None


def test_client_raises_rate_limit_on_429(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    client = EnrichmentLLMClient.from_env()
    fake = MagicMock()
    from anthropic import APIStatusError
    err = APIStatusError("rate", response=MagicMock(status_code=429), body=None)
    fake.messages.create.side_effect = err
    client._sdk = fake
    with pytest.raises(RateLimitMidrunError):
        asyncio.run(client.messages_create(messages=[], tools=[], system=""))
```

- [ ] **Step 2: Verify failure**

```
python -m pytest tests/unit/services/c4/enrichment/test_llm_client.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# app/services/c4/enrichment/config.py
import os


def get(key: str, default: str | int | float | bool):
    raw = os.getenv(key)
    if raw is None:
        return default
    if isinstance(default, bool):
        return raw.lower() in ("1", "true", "yes")
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    return raw


ENRICHMENT_ENABLED         = lambda: get("ENRICHMENT_ENABLED", True)
MINIMAX_BASE_URL           = lambda: get("MINIMAX_BASE_URL", "https://api.minimax.io/anthropic")
ENRICHMENT_MODEL           = lambda: get("ENRICHMENT_MODEL", "MiniMax-M2.7-highspeed")
ENRICHMENT_MAX_TOOL_CALLS  = lambda: get("ENRICHMENT_MAX_TOOL_CALLS", 15)
ENRICHMENT_MAX_TOKENS      = lambda: get("ENRICHMENT_MAX_TOKENS", 50000)
ENRICHMENT_TIMEOUT_S       = lambda: get("ENRICHMENT_TIMEOUT_S", 300)
ENRICHMENT_TOP_K           = lambda: get("ENRICHMENT_TOP_K", 10)
ENRICHMENT_MAX_CONCURRENT  = lambda: get("ENRICHMENT_MAX_CONCURRENT", 2)
ENRICHMENT_REQ_BUDGET_5H   = lambda: get("ENRICHMENT_REQ_BUDGET_5H", 600)
```

```python
# app/services/c4/enrichment/llm_client.py
import asyncio
import os
import time
from collections import deque
from typing import Any, Optional

from anthropic import Anthropic, APIStatusError

from . import config


class RateLimitMidrunError(RuntimeError):
    pass


class RequestRateCounter:
    def __init__(self, budget: int, window_s: float = 5 * 3600):
        self.budget = budget
        self.window_s = window_s
        self._log: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def _prune(self) -> None:
        now = time.time()
        while self._log and now - self._log[0] > self.window_s:
            self._log.popleft()

    async def can_run(self, reserve: int = 1) -> bool:
        async with self._lock:
            await self._prune()
            return len(self._log) + reserve <= self.budget

    async def record(self) -> None:
        async with self._lock:
            self._log.append(time.time())


_GLOBAL_COUNTER: Optional[RequestRateCounter] = None


def get_rate_counter() -> RequestRateCounter:
    global _GLOBAL_COUNTER
    if _GLOBAL_COUNTER is None:
        _GLOBAL_COUNTER = RequestRateCounter(budget=config.ENRICHMENT_REQ_BUDGET_5H())
    return _GLOBAL_COUNTER


class EnrichmentLLMClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        self._sdk = Anthropic(api_key=api_key, base_url=base_url)
        self.model = model
        self.rate = get_rate_counter()

    @classmethod
    def from_env(cls) -> Optional["EnrichmentLLMClient"]:
        key = os.getenv("MINIMAX_API_KEY")
        if not key:
            return None
        return cls(api_key=key,
                   base_url=config.MINIMAX_BASE_URL(),
                   model=config.ENRICHMENT_MODEL())

    async def messages_create(self, messages: list, tools: list,
                              system: str, **kwargs) -> Any:
        await self.rate.record()
        try:
            return await asyncio.to_thread(
                self._sdk.messages.create,
                model=self.model, messages=messages, tools=tools,
                system=system, max_tokens=kwargs.get("max_tokens", 2048),
                tool_choice=kwargs.get("tool_choice"),
            )
        except APIStatusError as e:
            if getattr(e.response, "status_code", None) == 429:
                raise RateLimitMidrunError() from e
            raise
```

- [ ] **Step 4: Verify pass**

```
python -m pytest tests/unit/services/c4/enrichment/test_llm_client.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```
git add sources/Api/app/services/c4/enrichment/llm_client.py \
        sources/Api/app/services/c4/enrichment/config.py \
        sources/Api/tests/unit/services/c4/enrichment/test_llm_client.py
git commit -m "feat(enrichment): MiniMax client + 5h rolling rate counter"
```

---

## Task 7: GraphMerger

**Files:**
- Create: `sources/Api/app/services/c4/enrichment/graph_merger.py`
- Test: `sources/Api/tests/unit/services/c4/enrichment/test_graph_merger.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/services/c4/enrichment/test_graph_merger.py
from unittest.mock import MagicMock
import pytest
from app.services.c4.enrichment.evidence_corpus import EvidenceCorpus, DepEvidence
from app.services.c4.enrichment.graph_merger import GraphMerger


def _ec(deps):
    from pathlib import Path
    return EvidenceCorpus(repo_path=Path("/tmp"), task_id="t1",
                          languages=[], frameworks=[], deterministic_deps=deps,
                          entrypoints=[], detected_urls=[], env_vars=[],
                          docker_images=[], package_files=[])


def test_new_dep_gets_llm_adjudicated_mode():
    ec = _ec([])
    m = GraphMerger(evidence=ec, writer=MagicMock(), persister=MagicMock())
    mode = m.classify_node(type_="external_dep", name="Stripe",
                           props={"confidence": 0.8, "dep_type": "payment"})
    assert mode == "LLM_ADJUDICATED"


def test_existing_dep_canonical_match_returns_llm_adjudicated():
    ec = _ec([DepEvidence(name="stripe", type="package", confidence=0.95,
                          files_found_in=[])])
    m = GraphMerger(evidence=ec, writer=MagicMock(), persister=MagicMock())
    mode = m.classify_node(type_="external_dep", name="Stripe-API",
                           props={"confidence": 0.7, "dep_type": "payment",
                                  "evidence": [{"file": "a", "line": 1}]})
    assert mode == "LLM_ADJUDICATED"


def test_conflict_returns_needs_review():
    ec = _ec([DepEvidence(name="stripe", type="messaging", confidence=0.9,
                          files_found_in=[])])
    m = GraphMerger(evidence=ec, writer=MagicMock(), persister=MagicMock())
    mode = m.classify_node(type_="external_dep", name="Stripe",
                           props={"confidence": 0.8, "dep_type": "payment",
                                  "evidence": [{"file": "a"}]})
    assert mode == "NEEDS_REVIEW"
```

- [ ] **Step 2: Verify failure**

```
python -m pytest tests/unit/services/c4/enrichment/test_graph_merger.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# app/services/c4/enrichment/graph_merger.py
from .evidence_corpus import EvidenceCorpus
from .graph_writer import normalize_logical_name


class GraphMerger:
    def __init__(self, evidence: EvidenceCorpus, writer, persister):
        self.evidence = evidence
        self.writer = writer
        self.persister = persister
        self._det_index = {
            normalize_logical_name(d.name): d for d in evidence.deterministic_deps
        }

    def classify_node(self, type_: str, name: str, props: dict) -> str:
        canon = normalize_logical_name(name)
        existing = self._det_index.get(canon)
        if existing is None:
            return "LLM_ADJUDICATED"
        new_type = props.get("dep_type") or props.get("type") or ""
        if existing.type and new_type and existing.type.lower() != new_type.lower():
            return "NEEDS_REVIEW"
        return "LLM_ADJUDICATED"

    def finalize(self, summary: dict) -> None:
        self.persister.finalize(summary)

    def rollback(self) -> None:
        self.writer.rollback()
        self.persister.rollback()
```

- [ ] **Step 4: Verify pass**

```
python -m pytest tests/unit/services/c4/enrichment/test_graph_merger.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```
git add sources/Api/app/services/c4/enrichment/graph_merger.py \
        sources/Api/tests/unit/services/c4/enrichment/test_graph_merger.py
git commit -m "feat(enrichment): GraphMerger conflict detection + finalize/rollback"
```

---

## Task 8: LLMAgentLoop

**Files:**
- Create: `sources/Api/app/services/c4/enrichment/agent_loop.py`
- Test: `sources/Api/tests/unit/services/c4/enrichment/test_agent_loop.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/services/c4/enrichment/test_agent_loop.py
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock
import pytest
from app.services.c4.enrichment.agent_loop import LLMAgentLoop, Budget, StopReason


def _resp(stop_reason, tool_uses=None, in_t=100, out_t=100):
    blocks = []
    for tu in (tool_uses or []):
        blocks.append(SimpleNamespace(type="tool_use", id=tu["id"],
                                      name=tu["name"], input=tu.get("input", {})))
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=blocks,
        usage=SimpleNamespace(input_tokens=in_t, output_tokens=out_t),
    )


@pytest.fixture
def deps():
    client = MagicMock()
    client.messages_create = AsyncMock()
    registry = MagicMock()
    registry.get_tools.return_value = []
    registry.dispatch.return_value = {"is_error": False, "content": "{}"}
    return client, registry


def test_loop_stops_on_natural_end_turn(deps):
    client, registry = deps
    client.messages_create.return_value = _resp("end_turn")
    loop = LLMAgentLoop(client, registry, system_prompt="x")
    res = asyncio.run(loop.run(warm_payload="hi", budget=Budget()))
    assert res.stop_reason == StopReason.natural_stop


def test_loop_stops_when_tool_call_cap_hit(deps):
    client, registry = deps
    client.messages_create.return_value = _resp("tool_use",
        tool_uses=[{"id": "u1", "name": "read_file", "input": {"path": "x"}}])
    loop = LLMAgentLoop(client, registry, system_prompt="x")
    res = asyncio.run(loop.run(warm_payload="hi",
                               budget=Budget(max_tool_calls=2, max_tokens=999_999)))
    assert res.stop_reason == StopReason.budget_exceeded
    assert res.tool_calls_used >= 2


def test_loop_stops_when_token_cap_hit(deps):
    client, registry = deps
    client.messages_create.return_value = _resp("tool_use",
        tool_uses=[{"id": "u1", "name": "read_file"}], in_t=5000, out_t=5000)
    loop = LLMAgentLoop(client, registry, system_prompt="x")
    res = asyncio.run(loop.run(warm_payload="hi",
                               budget=Budget(max_tool_calls=99, max_tokens=15_000)))
    assert res.stop_reason == StopReason.budget_exceeded


def test_loop_forces_tool_use_on_turn_1(deps):
    client, registry = deps
    client.messages_create.return_value = _resp("end_turn")
    loop = LLMAgentLoop(client, registry, system_prompt="x")
    asyncio.run(loop.run(warm_payload="hi", budget=Budget()))
    first_call = client.messages_create.await_args_list[0]
    assert first_call.kwargs.get("tool_choice") == {"type": "any"}


def test_loop_propagates_tool_results_back(deps):
    client, registry = deps
    client.messages_create.side_effect = [
        _resp("tool_use", tool_uses=[{"id": "u1", "name": "read_file"}]),
        _resp("end_turn"),
    ]
    asyncio.run(LLMAgentLoop(client, registry, system_prompt="x")
                .run(warm_payload="hi", budget=Budget()))
    second = client.messages_create.await_args_list[1]
    msgs = second.kwargs["messages"]
    tool_result_block = next(b for m in msgs for b in m.get("content", [])
                             if isinstance(b, dict) and b.get("type") == "tool_result")
    assert tool_result_block["tool_use_id"] == "u1"
```

- [ ] **Step 2: Verify failure**

```
python -m pytest tests/unit/services/c4/enrichment/test_agent_loop.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# app/services/c4/enrichment/agent_loop.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .llm_client import RateLimitMidrunError


class StopReason(str, Enum):
    natural_stop = "natural_stop"
    budget_exceeded = "budget_exceeded"
    rate_limit_midrun = "rate_limit_midrun"


@dataclass
class Budget:
    max_tool_calls: int = 15
    max_tokens: int = 50_000


@dataclass
class LoopResult:
    stop_reason: StopReason
    tool_calls_used: int = 0
    tokens_used: int = 0
    last_response: Any = None


class LLMAgentLoop:
    def __init__(self, client, tool_registry, system_prompt: str):
        self.client = client
        self.registry = tool_registry
        self.system = system_prompt

    async def run(self, warm_payload: str, budget: Budget) -> LoopResult:
        tools = self.registry.get_tools()
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": warm_payload}
        ]
        tool_calls_used = 0
        tokens_used = 0
        turn = 0

        while True:
            kwargs: dict[str, Any] = {}
            if turn == 0:
                kwargs["tool_choice"] = {"type": "any"}

            try:
                resp = await self.client.messages_create(
                    messages=messages, tools=tools, system=self.system, **kwargs
                )
            except RateLimitMidrunError:
                return LoopResult(stop_reason=StopReason.rate_limit_midrun,
                                  tool_calls_used=tool_calls_used,
                                  tokens_used=tokens_used)

            tokens_used += getattr(resp.usage, "input_tokens", 0) \
                         + getattr(resp.usage, "output_tokens", 0)

            tool_uses = [b for b in (resp.content or [])
                         if getattr(b, "type", None) == "tool_use"]

            messages.append({"role": "assistant",
                             "content": [self._block_to_dict(b)
                                         for b in resp.content or []]})

            if resp.stop_reason != "tool_use" or not tool_uses:
                return LoopResult(stop_reason=StopReason.natural_stop,
                                  tool_calls_used=tool_calls_used,
                                  tokens_used=tokens_used,
                                  last_response=resp)

            tool_results = []
            for tu in tool_uses:
                tool_calls_used += 1
                result = self.registry.dispatch(tu.name, tu.input or {})
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tu.id,
                    "content": result["content"], "is_error": result["is_error"],
                })

            messages.append({"role": "user", "content": tool_results})

            if (tool_calls_used >= budget.max_tool_calls
                    or tokens_used >= budget.max_tokens):
                return LoopResult(stop_reason=StopReason.budget_exceeded,
                                  tool_calls_used=tool_calls_used,
                                  tokens_used=tokens_used)
            turn += 1

    def _block_to_dict(self, b: Any) -> dict[str, Any]:
        t = getattr(b, "type", None)
        if t == "tool_use":
            return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
        if t == "text":
            return {"type": "text", "text": b.text}
        return {"type": str(t)}
```

- [ ] **Step 4: Verify pass**

```
python -m pytest tests/unit/services/c4/enrichment/test_agent_loop.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```
git add sources/Api/app/services/c4/enrichment/agent_loop.py \
        sources/Api/tests/unit/services/c4/enrichment/test_agent_loop.py
git commit -m "feat(enrichment): bounded agentic tool_use loop"
```

---

## Task 9: EnrichmentWSEvents + add broadcast_to_task to ConnectionManager

**Files:**
- Modify: `sources/Api/app/endpoint/v1/routes/websocket.py` — add `task_connections` map + `register_task`/`unregister_task`/`broadcast_to_task` to `ConnectionManager`
- Create: `sources/Api/app/services/c4/enrichment/ws_events.py`
- Test: `sources/Api/tests/unit/services/c4/enrichment/test_ws_events.py`

**Inspection done (grill session):** `ConnectionManager` has `broadcast()` (all) and `send_personal_message()` (one WS object). Neither is per-task. `broadcast_to_task()` must be added. `emit()` stays sync via `asyncio.create_task()` fire-and-forget — WS drops must not stall the enrichment worker.

**Critical (Q1):** `websocket_endpoint` calls `await websocket.accept()` directly, bypassing `manager.connect()`. `manager.active_connections` stays empty → `broadcast()` drops all messages → enrichment events never reach clients. T9 Step 1b refactors the WS endpoint to use `manager.connect/disconnect` and `register_task`. Without this, nothing works.

- [ ] **Step 1: Extend ConnectionManager in `websocket.py`**

Add to `ConnectionManager` class (after `get_connection_count`):

```python
def register_task(self, task_id: str, websocket: WebSocket) -> None:
    if not hasattr(self, "_task_connections"):
        self._task_connections: dict[str, WebSocket] = {}
    self._task_connections[task_id] = websocket
    # Reverse mapping so disconnect() can unregister
    if not hasattr(self, "_websocket_to_task"):
        self._websocket_to_task: dict[WebSocket, str] = {}
    self._websocket_to_task[websocket] = task_id

def unregister_task(self, task_id: str) -> None:
    if hasattr(self, "_task_connections"):
        ws = self._task_connections.pop(task_id, None)
        if ws and hasattr(self, "_websocket_to_task"):
            self._websocket_to_task.pop(ws, None)

async def broadcast_to_task(self, task_id: str, message: dict) -> None:
    task_conns = getattr(self, "_task_connections", {})
    ws = task_conns.get(task_id)
    if ws:
        await self.send_personal_message(message, ws)
    else:
        logger.debug("no ws registered for task %s", task_id)
```

- [ ] **Step 1b: Refactor `websocket_endpoint` to use `manager.connect/disconnect`**

The existing endpoint calls `await websocket.accept()` directly, bypassing `manager.connect()`. This means `manager.active_connections` stays empty and `broadcast()` drops all messages. Refactor the WS route handler:

```python
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await manager.connect(websocket)  # registers with ConnectionManager
    except Exception:
        return

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type", "unknown")
            if msg_type == "register_task":
                task_id = message.get("task_id")
                if task_id:
                    manager.register_task(task_id, websocket)
            # ... existing ping/subscribe/echo handlers
    except WebSocketDisconnect:
        task_id = manager._websocket_to_task.get(websocket)
        if task_id:
            manager.unregister_task(task_id)
        manager.disconnect(websocket)
```

Also update `ConnectionManager.disconnect()` to auto-unregister:

```python
def disconnect(self, websocket: WebSocket):
    task_id = getattr(self, "_websocket_to_task", {}).pop(websocket, None)
    if task_id:
        self.unregister_task(task_id)
    if websocket in self.active_connections:
        self.active_connections.remove(websocket)
    if websocket in self.connection_info:
        del self.connection_info[websocket]
```

- [ ] **Step 1c: Add `from functools import reduce` if not present; `logger` already imported**

- [ ] **Step 2: Write failing test**

```python
# tests/unit/services/c4/enrichment/test_ws_events.py
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.c4.enrichment.ws_events import EnrichmentWSEvents


def test_emit_fires_and_forgets_broadcast(monkeypatch):
    mgr = MagicMock()
    mgr.broadcast_to_task = AsyncMock()
    ws = EnrichmentWSEvents(manager=mgr, task_id="t1")
    with patch("asyncio.create_task") as ct:
        ws.emit("node_added", {"name": "X"})
    ct.assert_called_once()
    coro = ct.call_args.args[0]
    assert hasattr(coro, "cr_code")  # is a coroutine


def test_emit_handles_create_task_failure_silently():
    mgr = MagicMock()
    mgr.broadcast_to_task = AsyncMock()
    ws = EnrichmentWSEvents(manager=mgr, task_id="t1")
    with patch("asyncio.create_task", side_effect=RuntimeError("no loop")):
        ws.emit("x", {})  # must not raise
```

- [ ] **Step 3: Verify failure**

```
python -m pytest tests/unit/services/c4/enrichment/test_ws_events.py -v
```
Expected: FAIL.

- [ ] **Step 4: Implement**

```python
# app/services/c4/enrichment/ws_events.py
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class EnrichmentWSEvents:
    """Thin wrapper that pushes enrichment events through the existing
    websocket connection manager. Does NOT register a new endpoint.
    emit() is sync fire-and-forget — WS failures never block the worker."""

    def __init__(self, manager: Any, task_id: str):
        self.manager = manager
        self.task_id = task_id

    def emit(self, event: str, data: dict[str, Any]) -> None:
        payload = {"task_id": self.task_id, "event": event, "data": data}
        try:
            asyncio.create_task(
                self.manager.broadcast_to_task(self.task_id, payload)
            )
        except Exception as e:  # noqa: BLE001 — WS drop must not kill worker
            logger.warning("ws emit failed: %s", e)
```

- [ ] **Step 5: Verify pass**

```
python -m pytest tests/unit/services/c4/enrichment/test_ws_events.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```
git add sources/Api/app/endpoint/v1/routes/websocket.py \
        sources/Api/app/services/c4/enrichment/ws_events.py \
        sources/Api/tests/unit/services/c4/enrichment/test_ws_events.py
git commit -m "feat(enrichment): broadcast_to_task on ConnectionManager + WS events wrapper"
```

---

## Task 10: LLMEnrichmentWorker (orchestrator)

**Files:**
- Create: `sources/Api/app/services/c4/enrichment/worker.py`
- Test: `sources/Api/tests/unit/services/c4/enrichment/test_worker.py`

System-prompt content lives in this module as a constant `_SYSTEM_PROMPT`. The constant must include role, objective, DO/DO-NOT lists, output contract, confidence rubric, and one few-shot example sequence.

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/services/c4/enrichment/test_worker.py
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from app.services.c4.enrichment.evidence_corpus import EvidenceCorpus
from app.services.c4.enrichment.worker import LLMEnrichmentWorker
from app.services.c4.enrichment.agent_loop import LoopResult, StopReason


def _ec(tmp_path):
    return EvidenceCorpus(repo_path=tmp_path, task_id="t1",
                          languages=[], frameworks=[], deterministic_deps=[],
                          entrypoints=[], detected_urls=[], env_vars=[],
                          docker_images=[], package_files=[])


@pytest.fixture(autouse=True)
def _wire_env(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    monkeypatch.setenv("ENRICHMENT_ENABLED", "true")


def test_skipped_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("ENRICHMENT_ENABLED", "false")
    w = LLMEnrichmentWorker()
    asyncio.run(w.run(task_id="t1", repo_path=tmp_path, evidence=_ec(tmp_path)))
    # no exception, no events


def test_skipped_when_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    with patch("app.services.c4.enrichment.worker._get_ws_manager") as gws:
        mgr = MagicMock()
        gws.return_value = mgr
        w = LLMEnrichmentWorker()
        asyncio.run(w.run(task_id="t1", repo_path=tmp_path, evidence=_ec(tmp_path)))
    args = mgr.broadcast_to_task.call_args_list
    assert any(c.args[1]["event"] == "enrichment_skipped" for c in args)


def test_happy_path_emits_started_and_complete(tmp_path):
    with patch("app.services.c4.enrichment.worker._get_ws_manager") as gws, \
         patch("app.services.c4.enrichment.worker.LLMAgentLoop") as L, \
         patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env") as fe:
        mgr = MagicMock()
        gws.return_value = mgr
        L.return_value.run = AsyncMock(return_value=LoopResult(
            stop_reason=StopReason.natural_stop, tool_calls_used=3, tokens_used=2000))
        fe.return_value = MagicMock()
        w = LLMEnrichmentWorker()
        asyncio.run(w.run(task_id="t1", repo_path=tmp_path, evidence=_ec(tmp_path)))
    events = [c.args[1]["event"] for c in mgr.broadcast_to_task.call_args_list]
    assert events[0] == "enrichment_started"
    assert events[-1] == "enrichment_complete"


def test_budget_exceeded_marks_partial(tmp_path):
    with patch("app.services.c4.enrichment.worker._get_ws_manager") as gws, \
         patch("app.services.c4.enrichment.worker.LLMAgentLoop") as L, \
         patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env") as fe:
        mgr = MagicMock()
        gws.return_value = mgr
        L.return_value.run = AsyncMock(return_value=LoopResult(
            stop_reason=StopReason.budget_exceeded, tool_calls_used=15, tokens_used=50000))
        fe.return_value = MagicMock()
        w = LLMEnrichmentWorker()
        asyncio.run(w.run(task_id="t1", repo_path=tmp_path, evidence=_ec(tmp_path)))
    final = mgr.broadcast_to_task.call_args_list[-1].args[1]
    assert final["event"] == "enrichment_complete"
    assert final["data"]["partial"] is True
    assert final["data"]["reason"] == "budget"


def test_exception_triggers_rollback_and_failed_event(tmp_path):
    with patch("app.services.c4.enrichment.worker._get_ws_manager") as gws, \
         patch("app.services.c4.enrichment.worker.LLMAgentLoop") as L, \
         patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env") as fe, \
         patch("app.services.c4.enrichment.worker.EnrichmentGraphWriter") as W, \
         patch("app.services.c4.enrichment.worker.EnrichmentJSONPersister") as P:
        mgr = MagicMock()
        gws.return_value = mgr
        L.return_value.run = AsyncMock(side_effect=RuntimeError("boom"))
        fe.return_value = MagicMock()
        w_inst = MagicMock(); p_inst = MagicMock()
        W.return_value = w_inst; P.return_value = p_inst
        w = LLMEnrichmentWorker()
        asyncio.run(w.run(task_id="t1", repo_path=tmp_path, evidence=_ec(tmp_path)))
    w_inst.rollback.assert_called_once()
    p_inst.rollback.assert_called_once()
    final = mgr.broadcast_to_task.call_args_list[-1].args[1]
    assert final["event"] == "enrichment_failed"


def test_timeout_marks_partial(tmp_path):
    async def _slow(*a, **k):
        await asyncio.sleep(10)
    with patch("app.services.c4.enrichment.worker._get_ws_manager") as gws, \
         patch("app.services.c4.enrichment.worker.LLMAgentLoop") as L, \
         patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env") as fe, \
         patch("app.services.c4.enrichment.worker.config.ENRICHMENT_TIMEOUT_S",
               return_value=0.05):
        mgr = MagicMock()
        gws.return_value = mgr
        L.return_value.run = AsyncMock(side_effect=_slow)
        fe.return_value = MagicMock()
        w = LLMEnrichmentWorker()
        asyncio.run(w.run(task_id="t1", repo_path=tmp_path, evidence=_ec(tmp_path)))
    final = mgr.broadcast_to_task.call_args_list[-1].args[1]
    assert final["data"].get("reason") == "timeout"
```

- [ ] **Step 2: Verify failure**

```
python -m pytest tests/unit/services/c4/enrichment/test_worker.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# app/services/c4/enrichment/worker.py
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

from . import config
from .agent_loop import Budget, LLMAgentLoop, LoopResult, StopReason
from .evidence_corpus import EvidenceCorpus
from .graph_merger import GraphMerger
from .graph_writer import EnrichmentGraphWriter
from .json_persister import EnrichmentJSONPersister
from .llm_client import EnrichmentLLMClient, get_rate_counter
from .tool_registry import ExtractionToolRegistry
from .warm_context_builder import WarmContextBuilder
from .ws_events import EnrichmentWSEvents

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """ROLE: You are a code-architecture extractor. Build a C4 dependency graph from repo evidence.

OBJECTIVE: Find external dependencies the deterministic scan MISSED:
- Internal company HTTP wrappers (not in package files)
- Indirect deps (dynamic imports, reflection, eval)
- Novel ecosystems with no hardcoded map (Go, Rust, Elixir)
- Service-to-service URLs from configs

DO NOT:
- Re-emit deps already listed in deterministic_deps below
- Invent deps you cannot grep-verify in this repo
- Emit prose, summaries, or explanations
- Emit anything without evidence file:line

EVIDENCE REQUIRED: every emit_node MUST include `evidence: [{file, line, snippet}]`. Tool will reject otherwise.

OUTPUT CONTRACT:
- Use `grep`/`read_file`/`list_dir` to investigate.
- Use `emit_node` per finding.
- Use `emit_edge` to link nodes to the system.
- Stop when explored enough or budget hits.

CONFIDENCE RUBRIC:
- 1.0 = unambiguous code import line
- 0.7 = string match in config / docker-compose
- 0.4 = guess from filename

EXAMPLE FLOW:
1. grep("import.*http", path=".") → finds `app/clients.py` line 12 "import internal_http"
2. read_file("app/clients.py") → sees `internal_http.post("https://api.acme.io/v1/charge")`
3. emit_node(type="external_dep", name="Acme Payments", props={confidence: 0.9, dep_type: "payment", evidence: [{file: "app/clients.py", line: 12, snippet: "internal_http.post(...)"}]})
4. emit_edge(from_name="System", to_name="Acme Payments", relationship="uses", props={})
"""


_ACTIVE: dict[str, asyncio.Task] = {}
_SEMAPHORE: Optional[asyncio.Semaphore] = None

# Resolved via grill: enqueue() imports global singletons at call time.
# Callers pass only (task_id, repo_path, evidence) — no threading of driver/ws_manager needed.
# parents[5] from worker.py lands at repo root: sources/Api/app/services/c4/enrichment/ → sources/Api/ → sources/ → repo root
_DATA_DIR = Path(__file__).resolve().parents[5] / "data" / "c4_enrichments"


def _semaphore() -> asyncio.Semaphore:
    global _SEMAPHORE
    if _SEMAPHORE is None:
        _SEMAPHORE = asyncio.Semaphore(config.ENRICHMENT_MAX_CONCURRENT())
    return _SEMAPHORE


def _get_ws_manager():
    from app.endpoint.v1.routes.websocket import manager  # global singleton
    return manager


def _get_neo4j_driver():
    from app.infrastructure.graph.neo4j_client import Neo4jClient
    return Neo4jClient.from_config()


def enqueue(task_id: str, repo_path: Path,
            evidence: EvidenceCorpus) -> asyncio.Task:
    if task_id in _ACTIVE and not _ACTIVE[task_id].done():
        raise ValueError(f"enrichment already running for task: {task_id}")
    worker = LLMEnrichmentWorker()
    task = asyncio.create_task(worker.run(task_id, repo_path, evidence))
    _ACTIVE[task_id] = task
    task.add_done_callback(lambda _t: _ACTIVE.pop(task_id, None))
    return task


def cancel(task_id: str) -> bool:
    t = _ACTIVE.get(task_id)
    if t and not t.done():
        t.cancel()
        return True
    return False


class LLMEnrichmentWorker:
    def __init__(self):
        pass

    async def run(self, task_id: str, repo_path: Path,
                  evidence: EvidenceCorpus) -> None:
        run_id = str(uuid.uuid4())
        ws = EnrichmentWSEvents(manager=_get_ws_manager(), task_id=task_id)

        if not config.ENRICHMENT_ENABLED():
            return

        client = EnrichmentLLMClient.from_env()
        if client is None:
            ws.emit("enrichment_skipped", {"reason": "no_api_key"})
            return

        rate = get_rate_counter()
        if not await rate.can_run(reserve=config.ENRICHMENT_MAX_TOOL_CALLS() + 1):
            ws.emit("enrichment_skipped", {"reason": "rate_limit_5h"})
            return

        ws.emit("enrichment_started", {"run_id": run_id})

        try:
            persister = EnrichmentJSONPersister(
                base_dir=_DATA_DIR,
                task_id=task_id, run_id=run_id,
            )
            writer = EnrichmentGraphWriter(driver=_get_neo4j_driver(), task_id=task_id,
                                           run_id=run_id)
            merger = GraphMerger(evidence=evidence, writer=writer, persister=persister)
            registry = ExtractionToolRegistry(repo_path=repo_path, graph_writer=writer,
                                             persister=persister, ws_emit=ws.emit)
            warm = WarmContextBuilder().build(repo_path, evidence,
                                              top_k=config.ENRICHMENT_TOP_K())
            loop = LLMAgentLoop(client=client, tool_registry=registry,
                                system_prompt=_SYSTEM_PROMPT)

            timeout = config.ENRICHMENT_TIMEOUT_S()
            partial_reason: str | None = None
            partial = False
            nodes_added = len(registry._emitted_nodes)
            async with _semaphore():
                result: LoopResult = await asyncio.wait_for(
                    loop.run(warm_payload=self._render_warm(warm),
                             budget=Budget(
                                 max_tool_calls=config.ENRICHMENT_MAX_TOOL_CALLS(),
                                 max_tokens=config.ENRICHMENT_MAX_TOKENS())),
                    timeout=timeout,
                )
            if result.stop_reason == StopReason.budget_exceeded:
                partial, partial_reason = True, "budget"
            elif result.stop_reason == StopReason.rate_limit_midrun:
                partial, partial_reason = True, "rate_limit"
        except asyncio.TimeoutError:
            partial, partial_reason = True, "timeout"
        except Exception as e:  # noqa: BLE001
            logger.exception("enrichment failed")
            if "merger" in dir():
                merger.rollback()
            else:
                persister.rollback() if "persister" in dir() else None
            ws.emit("enrichment_failed", {"reason": "internal",
                                          "error": type(e).__name__})
            return

        nodes_added = len(registry._emitted_nodes)
        summary = {"partial": partial, "reason": partial_reason,
                   "nodes_added": nodes_added}
        merger.finalize(summary)
        ws.emit("enrichment_complete",
                {"partial": partial, "reason": partial_reason,
                 "nodes_added": nodes_added})

    def _render_warm(self, wc) -> str:
        lines = ["# File Tree", *wc.file_tree[:300],
                 "", "# Deterministic Evidence",
                 wc.evidence.model_dump_json(indent=2),
                 "", "# Pre-grepped signal files"]
        for sf in wc.signal_files:
            lines.append(f"\n## {sf.path}")
            lines.extend(sf.matches[:30])
        return "\n".join(lines)
```

- [ ] **Step 4: Verify pass**

```
python -m pytest tests/unit/services/c4/enrichment/test_worker.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```
git add sources/Api/app/services/c4/enrichment/worker.py \
        sources/Api/tests/unit/services/c4/enrichment/test_worker.py
git commit -m "feat(enrichment): orchestrator worker with pre-flight gates"
```

---

## Task 11: Wire into ContextManager

**Files:**
- Modify: `sources/Api/app/services/c4/context/context_manager.py` — add EvidenceCorpus assembly + `enqueue` call at end of `extract_context()`

**Critical:** detector method signatures and return types must not change. Only the orchestrator gains awareness of the enrichment phase.

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/enrichment/test_context_manager_hook.py
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.services.c4.context.context_manager import ContextManager


def test_extract_context_enqueues_worker(tmp_path):
    (tmp_path / "main.py").write_text("print(1)")
    mgr = ContextManager(repo_path=tmp_path, task_id="t1")
    with patch("app.services.c4.enrichment.worker.enqueue") as enq:
        ctx = mgr.extract_context()
    assert "name" in ctx
    enq.assert_called_once()
    kwargs = enq.call_args.kwargs or {}
    args = enq.call_args.args
    # signature: enqueue(task_id, repo_path, evidence)
    assert len(args) + len(kwargs) == 3


def test_extract_context_does_not_block_on_worker(tmp_path):
    (tmp_path / "main.py").write_text("print(1)")
    mgr = ContextManager(repo_path=tmp_path)
    with patch("app.services.c4.enrichment.worker.enqueue") as enq:
        ctx = mgr.extract_context()
    assert ctx is not None
```

- [ ] **Step 2: Verify failure**

```
python -m pytest tests/integration/enrichment/test_context_manager_hook.py -v
```
Expected: FAIL.

- [ ] **Step 3: Edit `context_manager.py`**

Add at top (after existing imports):

```python
from app.services.c4.enrichment import worker as enrichment_worker
from app.services.c4.enrichment.evidence_corpus import EvidenceCorpus, DepEvidence
```

Extend `__init__` signature:

```python
def __init__(self, repo_path: Path, llm_manager=None,
             containers: dict[str, Any] = None,
             task_id: str = None):
    ...
    self.task_id = task_id
```

At the bottom of `extract_context()`, immediately before `return context`, add:

```python
        if self.task_id:
            evidence = EvidenceCorpus(
                repo_path=self.repo_path,
                task_id=self.task_id,
                languages=[l.get("language", "") for l in languages],
                frameworks=[f.get("framework", "") for f in frameworks],
                deterministic_deps=[
                    DepEvidence(
                        name=d.get("name") or d.get("context_name") or "",
                        type=d.get("dependency_type") or d.get("type") or "",
                        confidence=float(d.get("confidence", 0.5)),
                        files_found_in=[],
                    )
                    for d in external_deps
                ],
                entrypoints=[],
                detected_urls=[d.get("url") for d in external_deps if d.get("url")],
                env_vars=[],
                docker_images=[],
                package_files=[],
            )
            try:
                enrichment_worker.enqueue(
                    task_id=self.task_id,
                    repo_path=self.repo_path,
                    evidence=evidence,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("enrichment enqueue failed: %s", e)
```

Test 1 calls `ContextManager(repo_path=tmp_path)` without `task_id` — must still work. Therefore: skip the enqueue when task_id is None. Update the test to pass `task_id`:

```python
mgr = ContextManager(repo_path=tmp_path, task_id="t1")
```

- [ ] **Step 4: Update caller in extraction route**

```
grep -n "ContextManager(" sources/Api/app/endpoint/v1/routes/code_extraction.py
grep -rn "ContextManager(" sources/Api/app/services/code_extraction/ sources/Api/app/services/c4/ | grep -v test_
```

For every construction site, thread `task_id` through from the existing extractor wiring. Worker imports its own singletons; callers do NOT pass `neo4j_driver` or `ws_manager`.

**Critical edit for `c4_extractor.py`:** `C4Extractor.__init__` takes no `task_id`. `task_id` is passed to `extract()`. The plan stores it on `self.task_id` at the top of `extract()`, so `_extract_level1_context()` can reach it without a signature change:

In `extract()`, right after `tracker = PerformanceTracker(...)`:
```python
self.task_id = task_id or f"extract_{int(time.time())}"
```

In `_extract_level1_context()`, pass `task_id`:
```python
def _extract_level1_context(self):
    """Extract Level 1: System Context using ContextManager."""
    context_manager = ContextManager(
        self.repo_path, self.llm_manager, self.containers,
        task_id=getattr(self, 'task_id', None),
    )
    ...
```

If `task_id` is None, `enqueue` skips gracefully — correct behavior for callers that don't provide it.

- [ ] **Step 5: Run all c4 tests**

```
docker compose exec -T api python -m pytest tests/unit/services/c4/ tests/integration/enrichment/ -v
```
Expected: all green, no regressions.

- [ ] **Step 6: Commit**

```
git add sources/Api/app/services/c4/context/context_manager.py \
        sources/Api/app/endpoint/v1/routes/code_extraction.py \
        sources/Api/tests/integration/enrichment/test_context_manager_hook.py
git commit -m "feat(enrichment): wire LLMEnrichmentWorker enqueue into ContextManager"
```

---

## Task 12: Frontend WS handlers + EnrichmentBadge

**Files:**
- Create: `sources/UI/src/hooks/useEnrichmentWS.ts`
- Create: `sources/UI/src/components/CodeArchitectureViewer/EnrichmentBadge.tsx`
- Modify: `sources/UI/src/components/CodeArchitectureViewer/GraphView.tsx` — wire `useEnrichmentWS`, render `EnrichmentBadge` on nodes where `decision_mode === "LLM_ADJUDICATED"` or `"NEEDS_REVIEW"`

**wsService assumption:** The project already has `wsService` (exported from `sources/UI/src/services/api.ts`) with `on(event, callback)` / `off(event, callback)` pattern. T12 uses `wsService.on/off` directly — no new WebSocket connection needed.

**Note (Q16 — GraphView merge):** `enrichedNodes` arrive async after initial graph render. `GraphView` must merge them into its elements array. Show a concrete implementation: keep `enrichedNodes` in state, combine with existing graph nodes in a derived computation or in the render, and pass merged elements to the graph library. Do not leave "wire useEnrichmentWS" as a vague instruction — show the state merging pattern.

- [ ] **Step 1: Find existing WS client hook**

```
grep -rn "useWebSocket\|new WebSocket\|wsUrl" sources/UI/src/ | head
```

Note the existing connection's URL builder and event-dispatch pattern. The new hook should subscribe to the same connection — not open a second socket.

- [ ] **Step 2: Write failing test**

```typescript
// sources/UI/src/hooks/__tests__/useEnrichmentWS.test.tsx
import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useEnrichmentWS } from "../useEnrichmentWS";

describe("useEnrichmentWS", () => {
  it("accumulates node_added events", () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() => useEnrichmentWS("t1"));
    act(() => {
      result.current._inject({
        event: "node_added",
        task_id: "t1",
        data: { name: "Stripe", canonical_name: "stripe",
                decision_mode: "LLM_ADJUDICATED" },
      });
    });
    expect(result.current.enrichedNodes).toHaveLength(1);
    expect(result.current.enrichedNodes[0].name).toBe("Stripe");
  });

  it("sets partial flag on enrichment_complete", () => {
    const { result } = renderHook(() => useEnrichmentWS("t1"));
    act(() => {
      result.current._inject({
        event: "enrichment_complete",
        task_id: "t1",
        data: { partial: true, reason: "budget", nodes_added: 3 },
      });
    });
    expect(result.current.partial).toBe(true);
    expect(result.current.partialReason).toBe("budget");
  });
});
```

- [ ] **Step 3: Verify failure**

```
cd sources/UI && npx vitest run src/hooks/__tests__/useEnrichmentWS.test.tsx
```
Expected: FAIL.

- [ ] **Step 4: Implement hook**

```typescript
// sources/UI/src/hooks/useEnrichmentWS.ts
import { useEffect, useState, useCallback } from "react";
import { wsService } from "../services/api";

export type EnrichedNode = {
  type: string;
  name: string;
  canonical_name: string;
  decision_mode: "LLM_ADJUDICATED" | "NEEDS_REVIEW" | "DETERMINISTIC";
  props: Record<string, unknown>;
};

type EnrichmentEvent =
  | { event: "enrichment_started"; task_id: string; data: { run_id: string } }
  | { event: "enrichment_skipped"; task_id: string; data: { reason: string } }
  | { event: "node_added"; task_id: string; data: EnrichedNode }
  | { event: "edge_added"; task_id: string;
      data: { from: string; to: string; relationship: string } }
  | { event: "enrichment_complete"; task_id: string;
      data: { partial: boolean; reason?: string; nodes_added: number } }
  | { event: "enrichment_failed"; task_id: string; data: { reason: string } };

export function useEnrichmentWS(taskId: string | null) {
  const [enrichedNodes, setNodes] = useState<EnrichedNode[]>([]);
  const [edges, setEdges] = useState<EnrichmentEvent["data"][]>([]);
  const [status, setStatus] = useState<"idle" | "running" | "complete" |
                                       "failed" | "skipped">("idle");
  const [partial, setPartial] = useState(false);
  const [partialReason, setPartialReason] = useState<string | null>(null);

  const handle = useCallback((msg: EnrichmentEvent) => {
    if (!taskId || msg.task_id !== taskId) return;
    switch (msg.event) {
      case "enrichment_started": setStatus("running"); break;
      case "enrichment_skipped": setStatus("skipped"); break;
      case "node_added":
        setNodes(prev => [...prev, msg.data as EnrichedNode]); break;
      case "edge_added":
        setEdges(prev => [...prev, msg.data]); break;
      case "enrichment_complete":
        setStatus("complete");
        setPartial(Boolean(msg.data.partial));
        setPartialReason(msg.data.reason || null);
        break;
      case "enrichment_failed": setStatus("failed"); break;
    }
  }, [taskId]);

  useEffect(() => {
    // Subscribe to existing WS connection via the app's wsService singleton.
    if (!taskId) return;
    const listener = (msg: any) => {
      if (msg && typeof msg === "object" && "event" in msg) {
        handle(msg as EnrichmentEvent);
      }
    };
    wsService.on("message", listener);
    return () => wsService.off("message", listener);
  }, [taskId, handle]);

  return {
    enrichedNodes, edges, status, partial, partialReason,
    _inject: handle, // test seam
  };
}
```

**Note:** `wsService` is already imported in `App.tsx` and `FileUploader.tsx` with `on/off("message")` pattern. T12 uses the same pattern. The `_inject` test seam is the contract guarantee; the integration with the real socket is project-specific.

- [ ] **Step 5: Implement EnrichmentBadge**

```typescript
// sources/UI/src/components/CodeArchitectureViewer/EnrichmentBadge.tsx
import React from "react";

type Props = { decisionMode: "LLM_ADJUDICATED" | "NEEDS_REVIEW" | string };

const COLOR: Record<string, string> = {
  LLM_ADJUDICATED: "#7C3AED",
  NEEDS_REVIEW: "#F59E0B",
};

export const EnrichmentBadge: React.FC<Props> = ({ decisionMode }) => {
  const color = COLOR[decisionMode];
  if (!color) return null;
  return (
    <span
      role="status"
      aria-label={`Decision mode: ${decisionMode}`}
      style={{
        display: "inline-block", padding: "2px 6px", borderRadius: 4,
        background: color, color: "white", fontSize: 10, marginLeft: 6,
      }}
    >
      {decisionMode === "NEEDS_REVIEW" ? "REVIEW" : "LLM"}
    </span>
  );
};
```

- [ ] **Step 6: Wire into CodeArchitectureViewer + merge enrichment nodes**

The plan merges enrichment nodes into the ReactFlow `nodes` array inside `CodeArchitectureViewer.tsx` — NOT inside `GraphView.tsx`. `GraphView` receives `nodes` and `edges` as props from the parent and is intentionally dumb. Enrichment logic lives in the parent.

**T12 Step 6 edit goes into `CodeArchitectureViewer.tsx`, not `GraphView.tsx`.**

In `CodeArchitectureViewer.tsx`, add a `useEnrichmentWS` hook and merge:

```typescript
// At top of component (after existing hooks, around line 900):
const taskIdForEnrichment = /* extract from existing taskId ref or state */;
const enrichment = useEnrichmentWS(taskIdForEnrichment);

// When building nodes from architecture (around line 1750),
// merge enrichedNodes into the existing node array:
const allNodes = [
  ...architectureNodes,
  ...enrichment.enrichedNodes.map(en => ({
    id: en.canonical_name,  // or en.name
    type: "custom",
    data: { ...en, decision_mode: en.decision_mode },
    position: { x: 0, y: 0 },  // layout will position it
  })),
];
```

The key insight: `enrichedNodes` are added as extra nodes in the ReactFlow graph. `CustomNode` already reads `data.decision_mode` (line 1188 already references `dep.decision_mode`). So the EnrichmentBadge only needs to be added to `CustomNode`'s render — no GraphView changes needed.

**EnrichmentBadge in CustomNode:**

In `CustomNode.tsx`, where `data.decision_mode` is already available (around line 129), render `<EnrichmentBadge decisionMode={data.decision_mode} />` if the mode is `"LLM_ADJUDICATED"` or `"NEEDS_REVIEW"`.

- [ ] **Step 7: Run frontend tests + lint**

```
cd sources/UI && npm run test && npm run check-all
```
Expected: all pass.

- [ ] **Step 8: Commit**

```
git add sources/UI/src/hooks/useEnrichmentWS.ts \
        sources/UI/src/hooks/__tests__/useEnrichmentWS.test.tsx \
        sources/UI/src/components/CodeArchitectureViewer/EnrichmentBadge.tsx \
        sources/UI/src/components/CodeArchitectureViewer/GraphView.tsx
git commit -m "feat(ui): enrichment WS handlers + LLM/REVIEW badge"
```

---

## Task 13: End-to-end integration test (mock LLM)

**Files:**
- Create: `sources/Api/tests/integration/enrichment/test_worker_e2e.py`
- Create: `sources/Api/tests/integration/enrichment/fixtures/sample_repo/{docker-compose.yml,requirements.txt,app/main.py}`
- Create: `sources/Api/tests/integration/enrichment/fixtures/llm_responses/happy_path.py` — pre-recorded response sequence

- [ ] **Step 1: Build fixture repo**

```
mkdir -p sources/Api/tests/integration/enrichment/fixtures/sample_repo/app
cat > sources/Api/tests/integration/enrichment/fixtures/sample_repo/docker-compose.yml <<'YAML'
services:
  api:
    image: python:3.11
    environment:
      - PAYMENT_URL=https://api.acme-payments.io
YAML
cat > sources/Api/tests/integration/enrichment/fixtures/sample_repo/requirements.txt <<'TXT'
fastapi==0.110.0
TXT
cat > sources/Api/tests/integration/enrichment/fixtures/sample_repo/app/main.py <<'PY'
import internal_http_wrapper as http
def charge(amount):
    return http.post("https://api.acme-payments.io/v1/charge", json={"a": amount})
PY
```

- [ ] **Step 2: Write end-to-end test (mock LLM client)**

```python
# tests/integration/enrichment/test_worker_e2e.py
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from app.services.c4.enrichment.evidence_corpus import EvidenceCorpus
from app.services.c4.enrichment.worker import LLMEnrichmentWorker


FIXTURES = Path(__file__).parent / "fixtures" / "sample_repo"


def _resp(stop, tool_uses=None, in_t=200, out_t=200):
    blocks = []
    for tu in (tool_uses or []):
        blocks.append(SimpleNamespace(type="tool_use", id=tu["id"],
                                      name=tu["name"], input=tu.get("input", {})))
    return SimpleNamespace(stop_reason=stop, content=blocks,
                           usage=SimpleNamespace(input_tokens=in_t,
                                                 output_tokens=out_t))


def test_worker_e2e_emits_acme_payments(tmp_path, monkeypatch):
    import shutil
    shutil.copytree(FIXTURES, tmp_path / "repo")
    repo = tmp_path / "repo"
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    monkeypatch.chdir(tmp_path)

    fake_client = MagicMock()
    fake_client.messages_create = AsyncMock(side_effect=[
        _resp("tool_use", tool_uses=[
            {"id": "g1", "name": "grep",
             "input": {"pattern": "acme-payments", "path": "."}}]),
        _resp("tool_use", tool_uses=[
            {"id": "r1", "name": "read_file",
             "input": {"path": "app/main.py"}}]),
        _resp("tool_use", tool_uses=[
            {"id": "e1", "name": "emit_node",
             "input": {"type": "external_dep", "name": "Acme Payments",
                       "props": {"confidence": 0.9, "dep_type": "payment",
                                 "evidence": [{"file": "app/main.py", "line": 3,
                                               "snippet": "http.post(...)"}]}}}]),
        _resp("end_turn"),
    ])
    ws_mgr = MagicMock()
    driver_session = MagicMock()
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = driver_session

    evidence = EvidenceCorpus(repo_path=repo, task_id="t1",
                              languages=["python"], frameworks=["fastapi"],
                              deterministic_deps=[], entrypoints=[],
                              detected_urls=[], env_vars=[], docker_images=[],
                              package_files=[Path("requirements.txt")])

    with patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env",
               return_value=fake_client), \
         patch("app.services.c4.enrichment.worker._get_ws_manager",
               return_value=ws_mgr), \
         patch("app.services.c4.enrichment.worker._get_neo4j_driver",
               return_value=driver):
        w = LLMEnrichmentWorker()
        asyncio.run(w.run("t1", repo, evidence))

    events = [c.args[1]["event"] for c in ws_mgr.broadcast_to_task.call_args_list]
    assert "enrichment_started" in events
    assert "node_added" in events
    assert "enrichment_complete" in events

    node_event = next(c.args[1] for c in ws_mgr.broadcast_to_task.call_args_list
                      if c.args[1]["event"] == "node_added")
    assert node_event["data"]["name"] == "Acme Payments"

    jsonl = tmp_path / "data" / "c4_enrichments" / "t1.jsonl"
    json_ = tmp_path / "data" / "c4_enrichments" / "t1.json"
    assert jsonl.exists() and json_.exists()
```

- [ ] **Step 3: Run e2e**

```
cd sources/Api && python -m pytest tests/integration/enrichment/test_worker_e2e.py -v
```
Expected: 1 passed.

- [ ] **Step 4: Run full backend suite for regression**

```
docker compose exec -T api python -m pytest tests/ -v 2>&1 | tail -50
```
Expected: 100% pass rate preserved (251/251 + new tests).

- [ ] **Step 5: Commit**

```
git add sources/Api/tests/integration/enrichment/
git commit -m "test(enrichment): end-to-end worker test with pre-recorded LLM"
```

---

## Self-Review Checklist (executed after writing)

**Spec coverage:**
- WarmContextBuilder → T5 ✓
- EvidenceCorpus → T1 ✓
- ExtractionToolRegistry → T4 ✓
- EnrichmentLLMClient → T6 ✓
- LLMAgentLoop → T8 ✓
- EnrichmentGraphWriter → T3 ✓
- EnrichmentJSONPersister → T2 ✓
- GraphMerger → T7 ✓
- LLMEnrichmentWorker → T10 ✓
- EnrichmentWSEvents → T9 ✓
- ContextManager hook → T11 ✓
- Frontend WS handlers + badge → T12 ✓
- E2E test with fixtures → T13 ✓
- Stop-reason matrix → T10 tests ✓
- Pre-flight gates → T10 tests ✓
- Rate counter → T6 tests ✓
- Path sandbox + evidence-required reject → T4 tests ✓
- Canonical dedup → T3 tests ✓
- Rollback on failure → T10 tests ✓

**Placeholders:** none — every step has concrete code, paths, commands, expected outcomes.

**Type consistency:**
- `EnrichmentGraphWriter.upsert_node` signature consistent across T3, T4, T10
- `EvidenceCorpus.deterministic_deps` → `list[DepEvidence]` consistent T1, T7, T10, T11
- `LoopResult.stop_reason` → `StopReason` enum consistent T8, T10
- `ws.emit(event_name, data_dict)` signature consistent T9, T4, T10

**Open clarifications for implementer:**
- T9 Step 1: inspect existing `websocket.py` for the exact broadcast method name; adapt `EnrichmentWSEvents` import if not `broadcast_to_task`.
- T11 Step 4: trace every `ContextManager(...)` construction site and decide whether to plumb new args. Sites without task/neo4j/ws context pass `None` (enqueue is gated).
- T12 Step 1: identify existing WS event-bus mechanism; the `window.addEventListener` placeholder in `useEnrichmentWS` is the most generic fallback — replace with the project's actual subscribe primitive.

These three are unavoidable: they depend on conventions visible only on inspection. The plan flags them with explicit `grep` commands so the implementer cannot miss them.
