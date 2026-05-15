import asyncio
from pathlib import Path
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


def test_skipped_when_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    with patch("app.services.c4.enrichment.worker._get_ws_manager") as gws:
        mgr = MagicMock()
        mgr.broadcast_to_task = AsyncMock()
        gws.return_value = mgr
        w = LLMEnrichmentWorker()
        asyncio.run(w.run(task_id="t1", repo_path=tmp_path, evidence=_ec(tmp_path)))
    args = mgr.broadcast_to_task.call_args_list
    assert any(c.args[1]["event"] == "enrichment_skipped" for c in args)


def test_happy_path_emits_started_and_complete(tmp_path):
    with patch("app.services.c4.enrichment.worker._get_ws_manager") as gws, \
         patch("app.services.c4.enrichment.worker._get_neo4j_driver") as gnd, \
         patch("app.services.c4.enrichment.worker.LLMAgentLoop") as L, \
         patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env") as fe, \
         patch("app.services.c4.enrichment.worker.EnrichmentGraphWriter") as W, \
         patch("app.services.c4.enrichment.worker.EnrichmentJSONPersister") as P:
        mgr = MagicMock()
        mgr.broadcast_to_task = AsyncMock()
        gws.return_value = mgr
        gnd.return_value = MagicMock()
        L.return_value.run = AsyncMock(return_value=LoopResult(
            stop_reason=StopReason.natural_stop, tool_calls_used=3, tokens_used=2000))
        fe.return_value = MagicMock()
        w_inst = MagicMock(); p_inst = MagicMock()
        W.return_value = w_inst; P.return_value = p_inst
        w = LLMEnrichmentWorker()
        asyncio.run(w.run(task_id="t1", repo_path=tmp_path, evidence=_ec(tmp_path)))
    events = [c.args[1]["event"] for c in mgr.broadcast_to_task.call_args_list]
    assert events[0] == "enrichment_started"
    assert events[-1] == "enrichment_complete"


def test_budget_exceeded_marks_partial(tmp_path):
    with patch("app.services.c4.enrichment.worker._get_ws_manager") as gws, \
         patch("app.services.c4.enrichment.worker._get_neo4j_driver") as gnd, \
         patch("app.services.c4.enrichment.worker.LLMAgentLoop") as L, \
         patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env") as fe, \
         patch("app.services.c4.enrichment.worker.EnrichmentGraphWriter") as W, \
         patch("app.services.c4.enrichment.worker.EnrichmentJSONPersister") as P:
        mgr = MagicMock()
        mgr.broadcast_to_task = AsyncMock()
        gws.return_value = mgr
        gnd.return_value = MagicMock()
        L.return_value.run = AsyncMock(return_value=LoopResult(
            stop_reason=StopReason.budget_exceeded, tool_calls_used=15, tokens_used=50000))
        fe.return_value = MagicMock()
        w_inst = MagicMock(); p_inst = MagicMock()
        W.return_value = w_inst; P.return_value = p_inst
        w = LLMEnrichmentWorker()
        asyncio.run(w.run(task_id="t1", repo_path=tmp_path, evidence=_ec(tmp_path)))
    final = mgr.broadcast_to_task.call_args_list[-1].args[1]
    assert final["event"] == "enrichment_complete"
    assert final["data"]["partial"] is True
    assert final["data"]["reason"] == "budget"


def test_exception_triggers_rollback_and_failed_event(tmp_path):
    with patch("app.services.c4.enrichment.worker._get_ws_manager") as gws, \
         patch("app.services.c4.enrichment.worker._get_neo4j_driver") as gnd, \
         patch("app.services.c4.enrichment.worker.LLMAgentLoop") as L, \
         patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env") as fe, \
         patch("app.services.c4.enrichment.worker.EnrichmentGraphWriter") as W, \
         patch("app.services.c4.enrichment.worker.EnrichmentJSONPersister") as P:
        mgr = MagicMock()
        mgr.broadcast_to_task = AsyncMock()
        gws.return_value = mgr
        gnd.return_value = MagicMock()
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
         patch("app.services.c4.enrichment.worker._get_neo4j_driver") as gnd, \
         patch("app.services.c4.enrichment.worker.LLMAgentLoop") as L, \
         patch("app.services.c4.enrichment.worker.EnrichmentLLMClient.from_env") as fe, \
         patch("app.services.c4.enrichment.worker.config.ENRICHMENT_TIMEOUT_S",
               return_value=0.05), \
         patch("app.services.c4.enrichment.worker.EnrichmentGraphWriter") as W, \
         patch("app.services.c4.enrichment.worker.EnrichmentJSONPersister") as P:
        mgr = MagicMock()
        mgr.broadcast_to_task = AsyncMock()
        gws.return_value = mgr
        gnd.return_value = MagicMock()
        L.return_value.run = AsyncMock(side_effect=_slow)
        fe.return_value = MagicMock()
        w_inst = MagicMock(); p_inst = MagicMock()
        W.return_value = w_inst; P.return_value = p_inst
        w = LLMEnrichmentWorker()
        asyncio.run(w.run(task_id="t1", repo_path=tmp_path, evidence=_ec(tmp_path)))
    final = mgr.broadcast_to_task.call_args_list[-1].args[1]
    assert final["data"].get("reason") == "timeout"