"""Data models for CallSwarm."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---

class TaskStatus(str, Enum):
    TASK_CREATED = "task_created"
    SEARCHING_BUSINESSES = "searching_businesses"
    AGENTS_SPAWNED = "agents_spawned"
    CALLS_RUNNING = "calls_running"
    PROCESSING_RESULTS = "processing_results"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"


class AgentStatus(str, Enum):
    QUEUED = "queued"
    DIALING = "dialing"
    SPEAKING = "speaking"
    WAITING = "waiting"
    EXTRACTING = "extracting"
    FINISHED = "finished"
    FAILED = "failed"


# --- Intent Parsing ---

class ParsedIntent(BaseModel):
    service_type: str
    location: str
    time_preference: str = "today"
    urgency: str = "normal"
    constraints: list[str] = Field(default_factory=list)


# --- Business Search ---

class Business(BaseModel):
    name: str
    phone: str
    address: str = ""
    rating: float = 0.0
    place_id: str = ""


# --- Call Results ---

class CallResult(BaseModel):
    business: Business
    available: bool = False
    times: list[str] = Field(default_factory=list)
    walk_in: bool = False
    notes: str = ""
    transcript: str = ""
    call_duration: float = 0.0


# --- Agent State ---

class AgentState(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    business_name: str
    phone: str
    status: AgentStatus = AgentStatus.QUEUED
    result: Optional[CallResult] = None
    transcript: str = ""
    call_id: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None


# --- Task ---

class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    query: str
    demo: bool = False
    status: TaskStatus = TaskStatus.TASK_CREATED
    parsed_intent: Optional[ParsedIntent] = None
    businesses: list[Business] = Field(default_factory=list)
    agents: list[AgentState] = Field(default_factory=list)
    results: list[CallResult] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


# --- API Models ---

class TaskRequest(BaseModel):
    query: str
    location: Optional[str] = None
    demo: bool = False


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    summary: str = ""
    results: list[CallResult] = Field(default_factory=list)
    agents: list[AgentState] = Field(default_factory=list)
    businesses_found: int = 0
