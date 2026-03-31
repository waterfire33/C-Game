"""MCP integration layer

Revision ID: 0006_mcp_integration
Revises: 0005_agent_router
Create Date: 2026-03-29 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_mcp_integration"
down_revision = "0005_agent_router"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE tool_source_type ADD VALUE IF NOT EXISTS 'mcp'")
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE mcp_auth_type AS ENUM ('none', 'bearer_token', 'static_header');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE mcp_server_health_status AS ENUM ('unknown', 'healthy', 'degraded', 'unreachable');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "mcp_auth_configs",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("auth_type", postgresql.ENUM("none", "bearer_token", "static_header", name="mcp_auth_type", create_type=False), nullable=False),
        sa.Column("header_name", sa.String(length=120), nullable=True),
        sa.Column("secret_ref", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_mcp_auth_configs_tenant_name"),
    )
    op.create_index(op.f("ix_mcp_auth_configs_tenant_id"), "mcp_auth_configs", ["tenant_id"], unique=False)

    op.create_table(
        "mcp_server_descriptors",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("auth_config_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("health_path", sa.String(length=255), nullable=False),
        sa.Column("tools_path", sa.String(length=255), nullable=False),
        sa.Column("invoke_path_template", sa.String(length=255), nullable=False),
        sa.Column("scope_filter", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("descriptor_metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("health_status", postgresql.ENUM("unknown", "healthy", "degraded", "unreachable", name="mcp_server_health_status", create_type=False), nullable=False),
        sa.Column("health_metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("last_health_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["auth_config_id"], ["mcp_auth_configs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_mcp_server_descriptors_tenant_name"),
    )
    op.create_index(op.f("ix_mcp_server_descriptors_tenant_id"), "mcp_server_descriptors", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_mcp_server_descriptors_auth_config_id"), "mcp_server_descriptors", ["auth_config_id"], unique=False)
    op.create_index(op.f("ix_mcp_server_descriptors_health_status"), "mcp_server_descriptors", ["health_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mcp_server_descriptors_health_status"), table_name="mcp_server_descriptors")
    op.drop_index(op.f("ix_mcp_server_descriptors_auth_config_id"), table_name="mcp_server_descriptors")
    op.drop_index(op.f("ix_mcp_server_descriptors_tenant_id"), table_name="mcp_server_descriptors")
    op.drop_table("mcp_server_descriptors")

    op.drop_index(op.f("ix_mcp_auth_configs_tenant_id"), table_name="mcp_auth_configs")
    op.drop_table("mcp_auth_configs")

    op.execute("DROP TYPE IF EXISTS mcp_server_health_status")
    op.execute("DROP TYPE IF EXISTS mcp_auth_type")
