"""FastAPI server - main API entry point for CallSwarm."""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from callswarm.api.websocket_manager import WebSocketManager
from callswarm.models.data_models import Task, TaskRequest, TaskResponse, TaskStatus
from callswarm.tasks.task_manager import TaskManager

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="CallSwarm", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ws_manager = WebSocketManager()


async def _on_task_update(task: Task):
    """Push task updates to all WebSocket clients."""
    await ws_manager.broadcast_task(task)


task_manager = TaskManager(on_task_update=_on_task_update)


# --- REST Endpoints ---


@app.get("/")
async def root():
    return {"service": "CallSwarm", "version": "1.0.0", "status": "running"}


@app.post("/tasks", response_model=TaskResponse)
async def create_task(request: TaskRequest):
    """Create a new task. The swarm starts running immediately in the background."""
    task = await task_manager.create_task(request)
    return _to_response(task)


@app.get("/tasks", response_model=list[TaskResponse])
async def list_tasks():
    """List all tasks."""
    return [_to_response(t) for t in task_manager.list_tasks()]


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get a specific task."""
    task = task_manager.get_task(task_id)
    if not task:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Task not found")
    return _to_response(task)


# --- WebSocket ---


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket for real-time dashboard updates."""
    await ws_manager.connect(ws)
    try:
        # Send current state on connect
        for task in task_manager.list_tasks():
            await ws_manager.broadcast_task(task)
        # Keep connection alive
        while True:
            data = await ws.receive_text()
            # Client can send ping/commands
            if data == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


def _to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        task_id=task.task_id,
        status=task.status,
        summary=task.summary,
        results=task.results,
        agents=task.agents,
        businesses_found=len(task.businesses),
    )


def start():
    """Entry point for running the server."""
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("callswarm.api.server:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    start()
