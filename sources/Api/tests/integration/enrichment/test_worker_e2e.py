"""End-to-end integration test for LLMEnrichmentWorker using pre-recorded LLM responses."""

import asyncio
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from app.services.c4.enrichment.evidence_corpus import EvidenceCorpus
from app.services.c4.enrichment.worker import LLMEnrichmentWorker

FIXTURES = Path(__file__).parent / "fixtures" / "sample_repo"


def _resp(stop: str, tool_uses=None, in_t: int = 200, out_t: int = 200):
    blocks = []
    for tu in (tool_uses or []):
        blocks.append(SimpleNamespace(
            type="tool_use",
            id=tu["id"],
            name=tu["name"],
            input=tu.get("input", {}),
        ))
    return SimpleNamespace(
        stop_reason=stop,
        content=blocks,
        usage=SimpleNamespace(input_tokens=in_t, output_tokens=out_t),
    )


@pytest.fixture
def sample_repo(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURES, repo, dirs_exist_ok=True)
    return repo.resolve()


@pytest.fixture(autouse=True)
def _wire_env(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    monkeypatch.setenv("ENRICHMENT_ENABLED", "true")


def test_worker_e2e_emits_acme_payments(sample_repo, monkeypatch):
    """Worker discovers Acme Payments via grep→read_file→emit_node sequence."""
    monkeypatch.chdir(sample_repo)

    fake_client = MagicMock()
    fake_client.messages_create = AsyncMock(side_effect=[
        _resp("tool_use", tool_uses=[
            {"id": "g1", "name": "grep",
             "input": {"pattern": "acme-payments", "path": "."}},
        ]),
        _resp("tool_use", tool_uses=[
            {"id": "r1", "name": "read_file",
             "input": {"path": "app/main.py"}},
        ]),
        _resp("tool_use", tool_uses=[
            {"id": "e1", "name": "emit_node",
             "input": {
                 "type_": "external_dep",
                 "name": "Acme Payments",
                 "props": {
                     "confidence": 0.9,
                     "dep_type": "payment",
                     "evidence": [
                         {"file": "app/main.py", "line": 3,
                          "snippet": "http.post(...)"},
                     ],
                 },
             }},
        ]),
        _resp("end_turn"),
    ])

    ws_mgr = MagicMock()
    ws_mgr.broadcast_to_task = AsyncMock()
    driver = MagicMock()
    persister_inst = MagicMock()

    evidence = EvidenceCorpus(
        repo_path=sample_repo, task_id="t1",
        languages=["python"], frameworks=["fastapi"],
        deterministic_deps=[], entrypoints=[],
        detected_urls=[], env_vars=[], docker_images=[],
        package_files=[Path("requirements.txt")],
    )

    with patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env",
               return_value=fake_client), \
         patch("app.services.c4.enrichment.worker._get_ws_manager",
               return_value=ws_mgr), \
         patch("app.services.c4.enrichment.worker._get_neo4j_driver",
               return_value=driver), \
         patch("app.services.c4.enrichment.worker._DATA_DIR",
               return_value=sample_repo / "data" / "c4_enrichments"), \
         patch("app.services.c4.enrichment.worker.EnrichmentJSONPersister",
               return_value=persister_inst):
        w = LLMEnrichmentWorker()
        asyncio.run(w.run("t1", sample_repo, evidence))

    events = [c.args[1]["event"] for c in ws_mgr.broadcast_to_task.call_args_list]
    assert "enrichment_started" in events, f"missing enrichment_started in {events}"
    assert "node_added" in events, f"missing node_added in {events}"
    assert "enrichment_complete" in events, f"missing enrichment_complete in {events}"

    node_event = next(
        c.args[1] for c in ws_mgr.broadcast_to_task.call_args_list
        if c.args[1]["event"] == "node_added"
    )
    assert node_event["data"]["name"] == "Acme Payments", \
        f"expected 'Acme Payments', got {node_event['data']['name']}"

    persister_inst.append.assert_called()
    persister_inst.finalize.assert_called_with(
        {"partial": False, "reason": None, "nodes_added": 1}
    )


def test_worker_e2e_budget_exceeded_marks_partial(sample_repo, monkeypatch):
    """25 tool calls triggers budget_exceeded partial completion."""
    monkeypatch.chdir(sample_repo)

    fake_client = MagicMock()
    fake_client.messages_create = AsyncMock(side_effect=[
        _resp("tool_use", tool_uses=[
            {"id": f"g{i}", "name": "grep",
             "input": {"pattern": f"p{i}", "path": "."}}
        ])
        for i in range(25)
    ] + [_resp("end_turn")])

    ws_mgr = MagicMock()
    ws_mgr.broadcast_to_task = AsyncMock()
    driver = MagicMock()

    evidence = EvidenceCorpus(
        repo_path=sample_repo, task_id="t2",
        languages=["python"], frameworks=["fastapi"],
        deterministic_deps=[], entrypoints=[],
        detected_urls=[], env_vars=[], docker_images=[],
        package_files=[],
    )

    with patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env",
               return_value=fake_client), \
         patch("app.services.c4.enrichment.worker._get_ws_manager",
               return_value=ws_mgr), \
         patch("app.services.c4.enrichment.worker._get_neo4j_driver",
               return_value=driver), \
         patch("app.services.c4.enrichment.worker._DATA_DIR",
               return_value=sample_repo / "data" / "c4_enrichments"):
        w = LLMEnrichmentWorker()
        asyncio.run(w.run("t2", sample_repo, evidence))

    final = ws_mgr.broadcast_to_task.call_args_list[-1].args[1]
    assert final["event"] == "enrichment_complete"
    assert final["data"]["partial"] is True
    assert final["data"]["reason"] == "budget"


def test_worker_e2e_no_tool_calls_emits_complete(sample_repo, monkeypatch):
    """LLM responds without calling any tools — natural stop."""
    monkeypatch.chdir(sample_repo)

    fake_client = MagicMock()
    fake_client.messages_create = AsyncMock(return_value=_resp("end_turn"))

    ws_mgr = MagicMock()
    ws_mgr.broadcast_to_task = AsyncMock()

    evidence = EvidenceCorpus(
        repo_path=sample_repo, task_id="t3",
        languages=[], frameworks=[], deterministic_deps=[],
        entrypoints=[], detected_urls=[], env_vars=[],
        docker_images=[], package_files=[],
    )

    with patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env",
               return_value=fake_client), \
         patch("app.services.c4.enrichment.worker._get_ws_manager",
               return_value=ws_mgr), \
         patch("app.services.c4.enrichment.worker._get_neo4j_driver",
               return_value=MagicMock()), \
         patch("app.services.c4.enrichment.worker._DATA_DIR",
               return_value=sample_repo / "data" / "c4_enrichments"):
        w = LLMEnrichmentWorker()
        asyncio.run(w.run("t3", sample_repo, evidence))

    events = [c.args[1]["event"] for c in ws_mgr.broadcast_to_task.call_args_list]
    assert events[0] == "enrichment_started"
    assert events[-1] == "enrichment_complete"
    node_events = [c for c in ws_mgr.broadcast_to_task.call_args_list
                   if c.args[1]["event"] == "node_added"]
    assert len(node_events) == 0


def test_worker_e2e_skipped_when_no_api_key(sample_repo, monkeypatch):
    """No API key → enrichment_skipped event, no LLM call."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.chdir(sample_repo)

    fake_client = MagicMock()
    ws_mgr = MagicMock()

    evidence = EvidenceCorpus(
        repo_path=sample_repo, task_id="t4",
        languages=[], frameworks=[], deterministic_deps=[],
        entrypoints=[], detected_urls=[], env_vars=[],
        docker_images=[], package_files=[],
    )

    with patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env",
               return_value=None), \
         patch("app.services.c4.enrichment.worker._get_ws_manager",
               return_value=ws_mgr):
        w = LLMEnrichmentWorker()
        asyncio.run(w.run("t4", sample_repo, evidence))

    args = ws_mgr.broadcast_to_task.call_args_list
    assert any(c.args[1]["event"] == "enrichment_skipped" for c in args)
    assert not any(c.args[1]["event"] == "enrichment_started" for c in args)
    assert not any(c.args[1]["event"] == "enrichment_complete" for c in args)


def test_worker_e2e_rollback_on_exception(sample_repo, monkeypatch, tmp_path):
    """LLM throws → rollback called, enrichment_failed emitted."""
    monkeypatch.chdir(sample_repo)

    fake_client = MagicMock()
    fake_client.messages_create = AsyncMock(side_effect=RuntimeError("LLM boom"))

    ws_mgr = MagicMock()
    ws_mgr.broadcast_to_task = AsyncMock()
    writer_inst = MagicMock()
    persister_inst = MagicMock()

    evidence = EvidenceCorpus(
        repo_path=sample_repo, task_id="t5",
        languages=[], frameworks=[], deterministic_deps=[],
        entrypoints=[], detected_urls=[], env_vars=[],
        docker_images=[], package_files=[],
    )

    with patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env",
               return_value=fake_client), \
         patch("app.services.c4.enrichment.worker._get_ws_manager",
               return_value=ws_mgr), \
         patch("app.services.c4.enrichment.worker._get_neo4j_driver",
               return_value=MagicMock()), \
         patch("app.services.c4.enrichment.worker._DATA_DIR",
               return_value=sample_repo / "data" / "c4_enrichments"), \
         patch("app.services.c4.enrichment.worker.EnrichmentGraphWriter",
               return_value=writer_inst), \
         patch("app.services.c4.enrichment.worker.EnrichmentJSONPersister",
               return_value=persister_inst):
        w = LLMEnrichmentWorker()
        asyncio.run(w.run("t5", sample_repo, evidence))

    writer_inst.rollback.assert_called_once()
    persister_inst.rollback.assert_called_once()
    final = ws_mgr.broadcast_to_task.call_args_list[-1].args[1]
    assert final["event"] == "enrichment_failed"
    assert final["data"]["reason"] == "internal"