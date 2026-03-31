import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SlugMixin, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

# Import workflow models so they're registered with Base.metadata
from app.db.workflow_models import (  # noqa: F401
    ApprovalRequestRecord,
    ApprovalRequestStatus,
    ActionRiskClass,
    WorkflowDefinition,
    WorkflowStepDefinition,
    WorkflowRun,
    WorkflowRunStep,
    WorkflowEvent,
    RunStatus,
    StepStatus,
    EventType,
    VALID_RUN_TRANSITIONS,
)
from app.db.tool_models import (  # noqa: F401
    ToolCall,
    ToolDefinition,
    TenantToolRegistration,
    ToolExecutionStatus,
    ToolFailureCategory,
    ToolSourceType,
)
from app.db.mcp_models import (  # noqa: F401
    MCPAuthConfig,
    MCPAuthType,
    MCPServerDescriptor,
    MCPServerHealthStatus,
)
from app.db.planner_models import (  # noqa: F401
    AgentRequest,
    PlanRecord,
    WorkflowType,
    PlannerStrategy,
    PlanStatus,
    PlannerFailureCategory,
)


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, SlugMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    memberships = relationship("Membership", back_populates="tenant", cascade="all, delete-orphan")


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")


class Membership(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_memberships_tenant_user"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")

    tenant = relationship("Tenant", back_populates="memberships")
    user = relationship("User", back_populates="memberships")
