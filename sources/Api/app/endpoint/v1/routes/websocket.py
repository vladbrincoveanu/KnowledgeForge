"""WebSocket endpoint for real-time communication."""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Router instance
router = APIRouter()
logger = logging.getLogger(__name__)


# Keep track of active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: set[WebSocket] = set()
        self.connection_info: dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.connection_info[websocket] = {
            "connected_at": datetime.now().isoformat(),
            "client": websocket.client,
        }
        logging.info(
            f"WebSocket connection accepted. Total connections: {len(self.active_connections)}"
        )

        # Send welcome message
        await self.send_personal_message(
            {
                "type": "connection",
                "status": "connected",
                "message": "WebSocket connection established",
                "timestamp": datetime.now().isoformat(),
            },
            websocket,
        )

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        task_id = getattr(self, "_websocket_to_task", {}).pop(websocket, None)
        if task_id:
            self.unregister_task(task_id)
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_info:
            del self.connection_info[websocket]
        logging.info(
            f"WebSocket connection closed. Total connections: {len(self.active_connections)}"
        )

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logging.error(f"Failed to send WebSocket message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all active connections."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logging.error(f"Failed to broadcast to connection: {e}")
                disconnected.append(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)

    def register_task(self, task_id: str, websocket: WebSocket) -> None:
        """Register a WebSocket connection for a specific task."""
        if not hasattr(self, "_task_connections"):
            self._task_connections: dict[str, WebSocket] = {}
        self._task_connections[task_id] = websocket
        if not hasattr(self, "_websocket_to_task"):
            self._websocket_to_task: dict[WebSocket, str] = {}
        self._websocket_to_task[websocket] = task_id

    def unregister_task(self, task_id: str) -> None:
        """Unregister a task's WebSocket connection."""
        if hasattr(self, "_task_connections"):
            ws = self._task_connections.pop(task_id, None)
            if ws and hasattr(self, "_websocket_to_task"):
                self._websocket_to_task.pop(ws, None)

    async def broadcast_to_task(self, task_id: str, message: dict) -> None:
        """Send a message to a specific task's WebSocket connection."""
        task_conns = getattr(self, "_task_connections", {})
        ws = task_conns.get(task_id)
        if ws:
            await self.send_personal_message(message, ws)
        else:
            logger.debug("no ws registered for task %s", task_id)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    try:
        await manager.connect(websocket)
    except Exception:
        return

    try:
        while True:
            data = await websocket.receive_text()
            logging.info(f"Received: %s", data)

            try:
                message = json.loads(data)
                msg_type = message.get("type", "unknown")

                if msg_type == "register_task":
                    task_id = message.get("task_id")
                    if task_id:
                        manager.register_task(task_id, websocket)
                        await manager.send_personal_message(
                            {
                                "type": "task_registered",
                                "task_id": task_id,
                                "timestamp": datetime.now().isoformat(),
                            },
                            websocket,
                        )
                elif msg_type == "ping":
                    await manager.send_personal_message(
                        {"type": "pong", "timestamp": datetime.now().isoformat()},
                        websocket,
                    )
                elif msg_type == "subscribe":
                    await manager.send_personal_message(
                        {
                            "type": "subscription",
                            "status": "subscribed",
                            "events": message.get("events", []),
                            "timestamp": datetime.now().isoformat(),
                        },
                        websocket,
                    )
                else:
                    await manager.send_personal_message(
                        {
                            "type": "echo",
                            "original_message": message,
                            "timestamp": datetime.now().isoformat(),
                        },
                        websocket,
                    )

            except json.JSONDecodeError:
                await manager.send_personal_message(
                    {
                        "type": "echo",
                        "message": data,
                        "timestamp": datetime.now().isoformat(),
                    },
                    websocket,
                )

    except WebSocketDisconnect:
        task_id = getattr(manager, "_websocket_to_task", {}).get(websocket)
        if task_id:
            manager.unregister_task(task_id)
        manager.disconnect(websocket)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        logger.error("WebSocket error: %s", e)
        task_id = getattr(manager, "_websocket_to_task", {}).get(websocket)
        if task_id:
            manager.unregister_task(task_id)
        manager.disconnect(websocket)


# Utility function to broadcast task updates
async def broadcast_task_update(
    task_id: str,
    status: str,
    message: str = "",
    progress: Optional[int] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Broadcast task update to all connected clients."""
    update_message: dict[str, Any] = {
        "type": "task_update",
        "task_id": task_id,
        "status": status,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }

    if progress is not None:
        update_message["progress"] = progress
    
    if extra:
        update_message.update(extra)

    await manager.broadcast(update_message)
    logging.info(f"Broadcasted task update: {task_id} - {status}")


# Utility function to broadcast extraction results
async def broadcast_extraction_complete(task_id: str, results: dict):
    """Broadcast extraction completion with results."""
    completion_message = {
        "type": "extraction_complete",
        "task_id": task_id,
        "status": "completed",
        "results": results,
        "timestamp": datetime.now().isoformat(),
    }

    await manager.broadcast(completion_message)
    logging.info(f"Broadcasted extraction completion: {task_id}")


# Export the manager for use in other modules
__all__ = [
    "router",
    "manager",
    "broadcast_task_update",
    "broadcast_extraction_complete",
]
