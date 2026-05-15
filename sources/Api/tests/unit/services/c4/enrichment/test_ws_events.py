from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.c4.enrichment.ws_events import EnrichmentWSEvents


def test_emit_fires_and_forgets_broadcast(monkeypatch):
    mgr = MagicMock()
    mgr.broadcast_to_task = AsyncMock()
    ws = EnrichmentWSEvents(manager=mgr, task_id="t1")
    with patch("asyncio.create_task") as ct:
        ws.emit("node_added", {"name": "X"})
    ct.assert_called_once()
    coro = ct.call_args.args[0]
    assert hasattr(coro, "cr_code")


def test_emit_handles_create_task_failure_silently():
    mgr = MagicMock()
    mgr.broadcast_to_task = AsyncMock()
    ws = EnrichmentWSEvents(manager=mgr, task_id="t1")
    with patch("asyncio.create_task", side_effect=RuntimeError("no loop")):
        ws.emit("x", {})