"""WebSocket endpoint for real-time communication."""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Router instance
router = APIRouter()


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
        except Exception as e:
            logging.error(f"Failed to send WebSocket message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all active connections."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logging.error(f"Failed to broadcast to connection: {e}")
                disconnected.append(connection)

        # Clean up disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    try:
        await manager.connect(websocket)
        logging.info("WebSocket connection accepted successfully")

        # Keep connection alive and handle messages
        while True:
            data = await websocket.receive_text()
            logging.info(f"Received: {data}")

            try:
                # Parse the incoming message
                message = json.loads(data)
                message_type = message.get("type", "unknown")

                # Handle different message types
                if message_type == "ping":
                    response = {"type": "pong", "timestamp": datetime.now().isoformat()}
                elif message_type == "subscribe":
                    response = {
                        "type": "subscription",
                        "status": "subscribed",
                        "events": message.get("events", []),
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    response = {
                        "type": "echo",
                        "original_message": message,
                        "timestamp": datetime.now().isoformat(),
                    }

                await websocket.send_text(json.dumps(response))

            except json.JSONDecodeError:
                # Echo the raw message back if it's not JSON
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "echo",
                            "message": data,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                )

    except WebSocketDisconnect:
        logging.info("WebSocket client disconnected")
        manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# Utility function to broadcast task updates
async def broadcast_task_update(
    task_id: str, status: str, message: str = "", progress: int = None
):
    """Broadcast task update to all connected clients."""
    update_message = {
        "type": "task_update",
        "task_id": task_id,
        "status": status,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }

    if progress is not None:
        update_message["progress"] = progress

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
