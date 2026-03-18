"""Data models for the recruiter agent."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


# ── Task lifecycle ───────────────────────────────────────────


class TaskStatus(str, enum.Enum):
    PENDING = "pending"           # awaiting agent matching
    MATCHED = "matched"           # agent found, escrow pending
    ESCROWED = "escrowed"         # payment locked
    DELEGATED = "delegated"       # task sent to agent
    COMPLETED = "completed"       # output validated, payment released
    DISPUTED = "disputed"         # validation failed
    FAILED = "failed"             # no agent found or delegation failed
    CANCELLED = "cancelled"       # client cancelled


class TaskRequest(BaseModel):
    """Incoming task from a client."""
    description: str
    category: str = "general"
    required_skills: list[str] = Field(default_factory=list)
    min_agent_score: float | None = None  # override default
    min_agent_tier: str | None = None     # override default
    max_payment_wei: str = "0"            # max the client will pay (wei string)
    callback_url: str | None = None       # webhook for status updates
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentCandidate(BaseModel):
    """An agent discovered via AgentProof oracle."""
    agent_id: int
    name: str = ""
    score: float
    tier: str
    category: str = ""
    endpoint: str = ""
    risk_level: str = "unknown"


class Task(BaseModel):
    """Internal task state."""
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    request: TaskRequest
    candidates: list[AgentCandidate] = Field(default_factory=list)
    selected_agent: AgentCandidate | None = None
    escrow_tx: str | None = None
    delegation_response: dict[str, Any] | None = None
    validation_result: dict[str, Any] | None = None
    settlement_tx: str | None = None
    feedback_tx: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: str | None = None

    def update_status(self, status: TaskStatus, **kwargs: Any) -> None:
        self.status = status
        self.updated_at = datetime.now(timezone.utc).isoformat()
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)


# ── A2A protocol models ─────────────────────────────────────


class A2ASkill(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)


class A2AProvider(BaseModel):
    organization: str
    url: str


class A2ACapabilities(BaseModel):
    streaming: bool = False
    pushNotifications: bool = False


class A2AAgentCard(BaseModel):
    name: str
    description: str
    url: str
    version: str
    capabilities: A2ACapabilities
    skills: list[A2ASkill]
    provider: A2AProvider
    # DevSpot / hackathon fields
    operator_wallet: str = ""
    erc8004_identity: int | None = None
    tech_stacks: list[str] = Field(default_factory=list)
    task_categories: list[str] = Field(default_factory=list)


# ── Execution log ────────────────────────────────────────────


class LogEntry(BaseModel):
    timestamp: str
    action: str
    description: str
    outcome: str = "success"
    tool_calls: list[str] = Field(default_factory=list)
    retry_count: int = 0
    details: dict[str, Any] = Field(default_factory=dict)
