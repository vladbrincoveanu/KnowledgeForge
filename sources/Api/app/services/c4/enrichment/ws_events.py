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