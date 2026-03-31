import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class MCPAuthType(str, enum.Enum):
    NONE = "none"
    BEARER_TOKEN = "bearer_token"
    STATIC_HEADER = "static_header"


class MCPServerHealthStatus(str, enum.Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"


class MCPAuthConfig(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "mcp_auth_configs"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_mcp_auth_configs_tenant_name"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    auth_type: Mapped[MCPAuthType] = mapped_column(
        Enum(MCPAuthType, name="mcp_auth_type", create_constraint=True),
        nullable=False,
        default=MCPAuthType.NONE,
    )
    header_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    secret_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    servers = relationship("MCPServerDescriptor", back_populates="auth_config")


class MCPServerDescriptor(UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin, Base):
    __tablename__ = "mcp_server_descriptors"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_mcp_server_descriptors_tenant_name"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auth_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mcp_auth_configs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    health_path: Mapped[str] = mapped_column(String(255), nullable=False, default="/health")
    tools_path: Mapped[str] = mapped_column(String(255), nullable=False, default="/tools")
    invoke_path_template: Mapped[str] = mapped_column(
        String(255), nullable=False, default="/tools/{tool_name}/invoke"
    )
    scope_filter: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    descriptor_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    health_status: Mapped[MCPServerHealthStatus] = mapped_column(
        Enum(MCPServerHealthStatus, name="mcp_server_health_status", create_constraint=True),
        nullable=False,
        default=MCPServerHealthStatus.UNKNOWN,
        index=True,
    )
    health_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    last_health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    auth_config = relationship("MCPAuthConfig", back_populates="servers")
