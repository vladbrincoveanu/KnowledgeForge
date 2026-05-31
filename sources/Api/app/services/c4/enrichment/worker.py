import asyncio
import logging
import time
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
_DATA_DIR = Path(__file__).resolve().parents[5] / "data" / "c4_enrichments"


def _semaphore() -> asyncio.Semaphore:
    global _SEMAPHORE
    if _SEMAPHORE is None:
        _SEMAPHORE = asyncio.Semaphore(config.ENRICHMENT_MAX_CONCURRENT())
    return _SEMAPHORE


def _get_ws_manager():
    from app.endpoint.v1.routes.websocket import manager
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
            start = time.monotonic()
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
        ws.emit("enrichment_complete", {
            "partial": partial,
            "reason": partial_reason,
            "nodes_added": nodes_added,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "tool_calls_used": result.tool_calls_used,
            "model": client.model,
            "duration_s": round(time.monotonic() - start, 2),
        })

    def _render_warm(self, wc) -> str:
        lines = ["# File Tree", *wc.file_tree[:300],
                 "", "# Deterministic Evidence",
                 wc.evidence.model_dump_json(indent=2),
                 "", "# Pre-grepped signal files"]
        for sf in wc.signal_files:
            lines.append(f"\n## {sf.path}")
            lines.extend(sf.matches[:30])
        return "\n".join(lines)