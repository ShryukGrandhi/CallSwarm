"""Orchestrator agent - coordinates the full task lifecycle."""

import asyncio
import logging
from datetime import datetime

from callswarm.agents.aggregator_agent import aggregate_results
from callswarm.agents.call_agent import run_call_agent
from callswarm.agents.demo_call_agent import run_demo_call_agent
from callswarm.agents.parser_agent import parse_intent
from callswarm.models.data_models import (
    AgentState,
    AgentStatus,
    Task,
    TaskStatus,
)
from callswarm.search.google_maps_search import search_businesses

logger = logging.getLogger(__name__)


class Orchestrator:
    """Central coordinator for the call swarm."""

    def __init__(self, on_task_update=None):
        """
        Args:
            on_task_update: async callback(task) called whenever task state changes.
        """
        self.on_task_update = on_task_update

    async def _notify(self, task: Task):
        """Push task state to listeners."""
        if self.on_task_update:
            await self.on_task_update(task)

    async def run_task(self, task: Task) -> Task:
        """Execute the full task lifecycle."""
        try:
            # 1. Parse intent
            task.status = TaskStatus.SEARCHING_BUSINESSES
            await self._notify(task)

            intent = await parse_intent(
                task.query,
                default_location=task.parsed_intent.location if task.parsed_intent else "nearby",
            )
            task.parsed_intent = intent
            await self._notify(task)

            # 2. Search businesses
            businesses = await search_businesses(
                service_type=intent.service_type,
                location=intent.location,
                max_results=10,
            )
            task.businesses = businesses

            if not businesses:
                task.status = TaskStatus.TASK_FAILED
                task.summary = "No businesses found with phone numbers. Try a different location or service."
                await self._notify(task)
                return task

            # 3. Spawn agents
            task.status = TaskStatus.AGENTS_SPAWNED
            agents: list[AgentState] = []
            for biz in businesses:
                agent = AgentState(
                    business_name=biz.name,
                    phone=biz.phone,
                    status=AgentStatus.QUEUED,
                )
                agents.append(agent)
            task.agents = agents
            await self._notify(task)

            # 4. Run calls in parallel
            task.status = TaskStatus.CALLS_RUNNING
            await self._notify(task)

            async def _on_agent_change(agent_state: AgentState):
                await self._notify(task)

            call_fn = run_demo_call_agent if task.demo else run_call_agent
            call_tasks = [
                call_fn(
                    business=biz,
                    service_type=intent.service_type,
                    time_preference=intent.time_preference,
                    agent_state=agent,
                    on_status_change=_on_agent_change,
                )
                for biz, agent in zip(businesses, agents)
            ]

            results = await asyncio.gather(*call_tasks, return_exceptions=True)

            # Filter out exceptions
            valid_results = []
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    logger.error("Agent %s failed: %s", agents[i].agent_id, r)
                    agents[i].status = AgentStatus.FAILED
                    agents[i].error = str(r)
                else:
                    valid_results.append(r)

            # 5. Aggregate results
            task.status = TaskStatus.PROCESSING_RESULTS
            await self._notify(task)

            ranked, summary = aggregate_results(valid_results)
            task.results = ranked
            task.summary = summary

            # 6. Complete
            task.status = TaskStatus.TASK_COMPLETE
            task.completed_at = datetime.utcnow()
            await self._notify(task)

            logger.info("Task %s complete: %s", task.task_id, summary)
            return task

        except Exception as e:
            logger.error("Task %s failed: %s", task.task_id, e)
            task.status = TaskStatus.TASK_FAILED
            task.summary = f"Task failed: {e}"
            await self._notify(task)
            return task
