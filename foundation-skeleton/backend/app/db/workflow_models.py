import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RunStatus(str, enum.Enum):
    """Valid run statuses with explicit state machine transitions."""
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, enum.Enum):
    """Step execution statuses."""
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EventType(str, enum.Enum):
    """Append-only event types for audit trail."""

    RUN_CREATED = "run_created"
    RUN_STARTED = "run_started"
    RUN_PAUSED = "run_paused"
    RUN_RESUMED = "run_resumed"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    RUN_RETRY_REQUESTED = "run_retry_requested"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_RETRY_SCHEDULED = "step_retry_scheduled"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    STATE_UPDATED = "state_updated"


class ActionRiskClass(str, enum.Enum):
    """Risk classification for step actions."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"


class ApprovalRequestStatus(str, enum.Enum):
    """Lifecycle for explicit approval requests."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


# Valid state transitions for the run state machine
VALID_RUN_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.PENDING: {RunStatus.RUNNING, RunStatus.CANCELLED},
    RunStatus.RUNNING: {RunStatus.AWAITING_APPROVAL, RunStatus.PAUSED, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.AWAITING_APPROVAL: {RunStatus.RUNNING, RunStatus.CANCELLED},
    RunStatus.PAUSED: {RunStatus.RUNNING, RunStatus.CANCELLED},
    RunStatus.FAILED: {RunStatus.PENDING},  # Can retry -> back to pending
}


class WorkflowDefinition(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Blueprint for a versioned workflow definition."""

    __tablename__ = "workflow_definitions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    steps = relationship(
        "WorkflowStepDefinition",
        back_populates="workflow_definition",
        cascade="all, delete-orphan",
        order_by="WorkflowStepDefinition.order",
    )
    runs = relationship("WorkflowRun", back_populates="workflow_definition")


class WorkflowStepDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Step template within a workflow definition."""
    __tablename__ = "workflow_step_definitions"
    __table_args__ = (
        UniqueConstraint("workflow_definition_id", "order", name="uq_workflow_step_definitions_workflow_definition_order"),
    )

    workflow_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action_risk_class: Mapped[ActionRiskClass] = mapped_column(
        Enum(ActionRiskClass, name="action_risk_class", create_constraint=True),
        nullable=False,
        default=ActionRiskClass.A,
    )
    required_approver_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    workflow_definition = relationship("WorkflowDefinition", back_populates="steps")
    approval_requests = relationship("ApprovalRequestRecord", back_populates="step_definition")


class WorkflowRun(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Single execution instance of a workflow."""
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_workflow_runs_idempotency_key"),
    )

    workflow_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status", create_constraint=True),
        nullable=False,
        default=RunStatus.PENDING,
        index=True
    )
    current_step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    input_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    workflow_definition = relationship("WorkflowDefinition", back_populates="runs")
    steps = relationship("WorkflowRunStep", back_populates="run", cascade="all, delete-orphan", order_by="WorkflowRunStep.step_index")
    events = relationship("WorkflowEvent", back_populates="run", cascade="all, delete-orphan", order_by="WorkflowEvent.sequence_number")
    tool_calls = relationship("ToolCall", back_populates="run", order_by="ToolCall.started_at.desc()")
    approval_requests = relationship(
        "ApprovalRequestRecord",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ApprovalRequestRecord.requested_at.desc()",
    )


class WorkflowRunStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Execution record for each step in a run."""
    __tablename__ = "workflow_run_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uq_workflow_run_steps_run_step_index"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_step_definitions.id", ondelete="CASCADE"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[StepStatus] = mapped_column(
        Enum(StepStatus, name="step_status", create_constraint=True),
        nullable=False,
        default=StepStatus.PENDING
    )
    input_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run = relationship("WorkflowRun", back_populates="steps")
    step_definition = relationship("WorkflowStepDefinition")
    approval_requests = relationship(
        "ApprovalRequestRecord",
        back_populates="run_step",
        cascade="all, delete-orphan",
        order_by="ApprovalRequestRecord.requested_at.desc()",
    )


class ApprovalRequestRecord(UUIDPrimaryKeyMixin, Base):
    """Persisted approval requests for risky workflow actions."""

    __tablename__ = "approval_requests"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_run_steps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_step_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ApprovalRequestStatus] = mapped_column(
        Enum(ApprovalRequestStatus, name="approval_request_status", create_constraint=True),
        nullable=False,
        default=ApprovalRequestStatus.PENDING,
        index=True,
    )
    action_risk_class: Mapped[ActionRiskClass] = mapped_column(
        Enum(ActionRiskClass, name="action_risk_class", create_constraint=False),
        nullable=False,
        index=True,
    )
    required_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decision_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    run = relationship("WorkflowRun", back_populates="approval_requests")
    run_step = relationship("WorkflowRunStep", back_populates="approval_requests")
    step_definition = relationship("WorkflowStepDefinition", back_populates="approval_requests")


class WorkflowEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only event log for full audit trail and replayability."""
    __tablename__ = "workflow_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence_number", name="uq_workflow_events_run_sequence"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type", create_constraint=True),
        nullable=False,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False, default="system")
    previous_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run = relationship("WorkflowRun", back_populates="events")
