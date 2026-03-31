"""Pydantic schemas for workflow API."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.tool_models import ToolExecutionStatus, ToolFailureCategory
from app.db.workflow_models import (
    ActionRiskClass,
    ApprovalRequestStatus,
    EventType,
    RunStatus,
    StepStatus,
)


# =====================
# Workflow Definition Schemas
# =====================


class StepDefinitionCreate(BaseModel):
    """Schema for creating a workflow step definition."""
    name: str
    step_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    action_risk_class: ActionRiskClass | None = None
    required_approver_role: str | None = None
    timeout_seconds: int | None = None
    max_retries: int = 3


class WorkflowDefinitionCreate(BaseModel):
    """Schema for creating a workflow definition."""
    name: str
    description: str | None = None
    steps: list[StepDefinitionCreate]


class StepDefinitionResponse(BaseModel):
    """Schema for step definition response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    step_type: str
    order: int
    config: dict[str, Any]
    requires_approval: bool
    action_risk_class: ActionRiskClass
    required_approver_role: str | None
    timeout_seconds: int | None
    max_retries: int


class WorkflowDefinitionResponse(BaseModel):
    """Schema for workflow definition response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    steps: list[StepDefinitionResponse] = Field(default_factory=list)


class WorkflowDefinitionList(BaseModel):
    """Schema for listing workflow definitions."""
    items: list[WorkflowDefinitionResponse]
    total: int


# =====================
# Workflow Run Schemas
# =====================


class RunCreate(BaseModel):
    """Schema for creating a workflow run."""
    workflow_definition_id: UUID
    idempotency_key: str
    input_data: dict[str, Any] | None = None


class RunStepResponse(BaseModel):
    """Schema for run step response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    step_index: int
    status: StepStatus
    started_at: datetime | None
    completed_at: datetime | None
    output_data: dict[str, Any] | None
    error_message: str | None
    attempt_number: int
    approved_by_user_id: UUID | None
    approved_at: datetime | None


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    run_step_id: UUID
    step_definition_id: UUID
    step_index: int
    step_name: str
    status: ApprovalRequestStatus
    action_risk_class: ActionRiskClass
    required_role: str | None
    requested_by_user_id: UUID | None
    requested_at: datetime
    decision_by_user_id: UUID | None
    decided_at: datetime | None
    decision_reason: str | None
    request_context: dict[str, Any]


class RunToolCallSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tool_name: str
    step_index: int | None
    status: ToolExecutionStatus
    failure_category: ToolFailureCategory
    attempt_count: int
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None


class RunResponse(BaseModel):
    """Schema for workflow run response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    workflow_definition_id: UUID
    tenant_id: UUID
    idempotency_key: str
    status: RunStatus
    current_step_index: int
    input_data: dict[str, Any] | None
    output_data: dict[str, Any] | None
    state: dict[str, Any]
    error_message: str | None
    retry_count: int
    max_retries: int
    triggered_by_user_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    steps: list[RunStepResponse] = Field(default_factory=list)
    tool_calls: list[RunToolCallSummary] = Field(default_factory=list)
    approval_requests: list[ApprovalRequestResponse] = Field(default_factory=list)


class RunList(BaseModel):
    """Schema for listing workflow runs."""
    items: list[RunResponse]
    total: int


class ApprovalDecisionRequest(BaseModel):
    """Schema for approving or rejecting a pending approval request."""

    reason: str | None = None


class ApprovalRequest(BaseModel):
    """Legacy schema for run-scoped approval actions."""

    step_index: int
    reason: str | None = None


class ApprovalDenyRequest(BaseModel):
    """Schema for denying approval."""
    step_index: int
    reason: str | None = None


class ApprovalRequestList(BaseModel):
    items: list[ApprovalRequestResponse]
    total: int


# =====================
# Event Schemas
# =====================


class EventResponse(BaseModel):
    """Schema for workflow event response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    run_id: UUID
    event_type: EventType
    sequence_number: int
    previous_status: str | None
    new_status: str | None
    step_index: int | None
    payload: dict[str, Any]
    actor_user_id: UUID | None
    created_at: datetime


class TimelineResponse(BaseModel):
    """Schema for run timeline (list of events)."""
    run_id: UUID
    events: list[EventResponse]
