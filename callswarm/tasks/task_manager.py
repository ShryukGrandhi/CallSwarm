"""Task manager - stores and manages task lifecycle."""

import asyncio
import logging
from typing import Optional

from callswarm.agents.orchestrator import Orchestrator
from callswarm.models.data_models import Task, TaskRequest, TaskStatus

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages all tasks and their background execution."""

    def __init__(self, on_task_update=None):
        self.tasks: dict[str, Task] = {}
        self.background_tasks: dict[str, asyncio.Task] = {}
        self.on_task_update = on_task_update

    async def create_task(self, request: TaskRequest) -> Task:
        """Create a new task and start it in the background."""
        task = Task(query=request.query, demo=request.demo)
        if request.location:
            from callswarm.models.data_models import ParsedIntent
            task.parsed_intent = ParsedIntent(
                service_type="",
                location=request.location,
            )

        self.tasks[task.task_id] = task
        logger.info("Task created: %s - %s", task.task_id, task.query)

        # Start task in background
        bg = asyncio.create_task(self._run_task(task))
        self.background_tasks[task.task_id] = bg
        return task

    async def _run_task(self, task: Task):
        """Run the orchestrator for a task."""
        orchestrator = Orchestrator(on_task_update=self._handle_task_update)
        try:
            await orchestrator.run_task(task)
        except Exception as e:
            logger.error("Background task %s crashed: %s", task.task_id, e)
            task.status = TaskStatus.TASK_FAILED
            task.summary = f"System error: {e}"
        finally:
            self.background_tasks.pop(task.task_id, None)

    async def _handle_task_update(self, task: Task):
        """Forward task updates to the WebSocket manager."""
        self.tasks[task.task_id] = task
        if self.on_task_update:
            await self.on_task_update(task)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        """List all tasks."""
        return list(self.tasks.values())
