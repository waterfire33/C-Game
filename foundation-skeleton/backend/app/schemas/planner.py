"""Pydantic schemas for the agent router and planner API."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.planner_models import (
    PlannerFailureCategory,
    PlannerStrategy,
    PlanStatus,
    WorkflowType,
)


# =====================
# Request intake
# =====================


class AgentRequestCreate(BaseModel):
    """Payload for the request intake endpoint."""

    body: str = Field(..., min_length=1, max_length=10_000)
    context: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(..., min_length=1, max_length=255)


class AgentRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    submitted_by_user_id: UUID | None
    body: str
    context: dict[str, Any]
    idempotency_key: str
    created_at: datetime
    plan: "PlanResponse | None" = None


# =====================
# Planner output
# =====================


class PlannedStep(BaseModel):
    """One step the planner proposes."""

    name: str
    step_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    reasoning: str | None = None


class PlannerOutput(BaseModel):
    """Structured output the planner must return (deterministic or LLM)."""

    workflow_type: WorkflowType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    steps: list[PlannedStep]


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agent_request_id: UUID
    workflow_type: WorkflowType
    strategy: PlannerStrategy
    status: PlanStatus
    confidence: float | None
    reasoning: str | None
    planned_steps: list[dict[str, Any]]
    selected_workflow_definition_id: UUID | None
    run_id: UUID | None
    failure_category: PlannerFailureCategory
    error_message: str | None
    latency_ms: int | None
    created_at: datetime


class PlanList(BaseModel):
    items: list[PlanResponse]
    total: int


# Forward-ref update
AgentRequestResponse.model_rebuild()
