"""WebSocket manager for real-time dashboard updates."""

import json
import logging
from typing import Any

from fastapi import WebSocket

from callswarm.models.data_models import Task

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts task updates."""

    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
        logger.info("WebSocket connected. Total: %d", len(self.connections))

    def disconnect(self, ws: WebSocket):
        self.connections.remove(ws)
        logger.info("WebSocket disconnected. Total: %d", len(self.connections))

    async def broadcast_task(self, task: Task):
        """Broadcast task state to all connected clients."""
        data = _serialize_task(task)
        dead: list[WebSocket] = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections.remove(ws)

    async def send_to(self, ws: WebSocket, data: Any):
        """Send data to a specific client."""
        try:
            await ws.send_json(data)
        except Exception:
            pass


def _serialize_task(task: Task) -> dict:
    """Serialize a Task to a JSON-friendly dict."""
    return json.loads(task.model_dump_json())
