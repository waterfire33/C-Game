import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ToolSourceType(str, enum.Enum):
    INTERNAL = "internal"
    MCP = "mcp"


class ToolExecutionStatus(str, enum.Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class ToolFailureCategory(str, enum.Enum):
    NONE = "none"
    VALIDATION = "validation"
    NOT_ALLOWED = "not_allowed"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    TRANSIENT = "transient"
    INTERNAL = "internal"


class ToolDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tool_definitions"

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[ToolSourceType] = mapped_column(
        Enum(ToolSourceType, name="tool_source_type", create_constraint=True),
        nullable=False,
        default=ToolSourceType.INTERNAL,
        index=True,
    )
    is_read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    default_max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    tenant_registrations = relationship(
        "TenantToolRegistration",
        back_populates="tool_definition",
        cascade="all, delete-orphan",
    )
    tool_calls = relationship("ToolCall", back_populates="tool_definition")


class TenantToolRegistration(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "tenant_tool_registrations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "tool_definition_id", name="uq_tenant_tool_registrations_tenant_tool"),
    )

    tool_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    override_timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    override_max_retries: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    tool_definition = relationship("ToolDefinition", back_populates="tenant_registrations")
    tool_calls = relationship("ToolCall", back_populates="tenant_tool_registration")


class ToolCall(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tool_calls"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_run_steps.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tool_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_tool_registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_tool_registrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ToolExecutionStatus] = mapped_column(
        Enum(ToolExecutionStatus, name="tool_execution_status", create_constraint=True),
        nullable=False,
        index=True,
    )
    failure_category: Mapped[ToolFailureCategory] = mapped_column(
        Enum(ToolFailureCategory, name="tool_failure_category", create_constraint=True),
        nullable=False,
        default=ToolFailureCategory.NONE,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    normalized_output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run = relationship("WorkflowRun", back_populates="tool_calls")
    tool_definition = relationship("ToolDefinition", back_populates="tool_calls")
    tenant_tool_registration = relationship("TenantToolRegistration", back_populates="tool_calls")
