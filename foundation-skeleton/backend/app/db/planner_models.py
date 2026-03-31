"""Models for the agent router and planning contract."""
import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowType(str, enum.Enum):
    """Supported workflow type categories."""

    INFORMATION_REQUEST = "information_request"
    DRAFT_ACTION = "draft_action"
    EXECUTABLE_TOOL = "executable_tool"


class PlannerStrategy(str, enum.Enum):
    """How the plan was produced."""

    DETERMINISTIC = "deterministic"
    LLM = "llm"


class PlanStatus(str, enum.Enum):
    """Lifecycle of a plan."""

    PENDING = "pending"
    ROUTED = "routed"
    FAILED = "failed"


class PlannerFailureCategory(str, enum.Enum):
    """Classification of planner failures."""

    NONE = "none"
    UNPARSEABLE_OUTPUT = "unparseable_output"
    NO_MATCHING_WORKFLOW = "no_matching_workflow"
    LLM_TIMEOUT = "llm_timeout"
    LLM_REFUSAL = "llm_refusal"
    INVALID_PLAN_SCHEMA = "invalid_plan_schema"
    INTERNAL_ERROR = "internal_error"


class AgentRequest(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Canonical intake request from a user or upstream system."""

    __tablename__ = "agent_requests"

    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    plan: Mapped["PlanRecord | None"] = relationship(
        "PlanRecord", back_populates="agent_request", uselist=False
    )


class PlanRecord(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    """Persisted planner output for a single request."""

    __tablename__ = "plan_records"

    agent_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_requests.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    workflow_type: Mapped[WorkflowType] = mapped_column(
        Enum(WorkflowType, name="workflow_type", create_constraint=True),
        nullable=False,
        index=True,
    )
    strategy: Mapped[PlannerStrategy] = mapped_column(
        Enum(PlannerStrategy, name="planner_strategy", create_constraint=True),
        nullable=False,
    )
    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus, name="plan_status", create_constraint=True),
        nullable=False,
        default=PlanStatus.PENDING,
        index=True,
    )
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    planned_steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    selected_workflow_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_definitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    failure_category: Mapped[PlannerFailureCategory] = mapped_column(
        Enum(PlannerFailureCategory, name="planner_failure_category", create_constraint=True),
        nullable=False,
        default=PlannerFailureCategory.NONE,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_llm_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    agent_request: Mapped[AgentRequest] = relationship(
        "AgentRequest", back_populates="plan"
    )
    selected_workflow_definition = relationship("WorkflowDefinition")
    run = relationship("WorkflowRun")
