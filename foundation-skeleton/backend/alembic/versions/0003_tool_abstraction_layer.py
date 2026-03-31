"""add tool abstraction layer

Revision ID: 0003_tool_abstraction_layer
Revises: 0002_workflow_models
Create Date: 2026-03-29 00:30:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_tool_abstraction_layer"
down_revision = "0002_workflow_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tool_source_type_enum = postgresql.ENUM(
        "internal",
        name="tool_source_type",
        create_type=True,
    )
    tool_source_type_enum.create(op.get_bind(), checkfirst=True)

    tool_execution_status_enum = postgresql.ENUM(
        "succeeded",
        "failed",
        "timed_out",
        name="tool_execution_status",
        create_type=True,
    )
    tool_execution_status_enum.create(op.get_bind(), checkfirst=True)

    tool_failure_category_enum = postgresql.ENUM(
        "none",
        "validation",
        "not_allowed",
        "not_found",
        "timeout",
        "transient",
        "internal",
        name="tool_failure_category",
        create_type=True,
    )
    tool_failure_category_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tool_definitions",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "source_type",
            postgresql.ENUM("internal", name="tool_source_type", create_type=False),
            nullable=False,
            server_default="internal",
        ),
        sa.Column("is_read_only", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("default_timeout_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("default_max_retries", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_definitions")),
    )
    op.create_index(op.f("ix_tool_definitions_name"), "tool_definitions", ["name"], unique=True)
    op.create_index(op.f("ix_tool_definitions_source_type"), "tool_definitions", ["source_type"], unique=False)

    op.create_table(
        "tenant_tool_registrations",
        sa.Column("tool_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("override_timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("override_max_retries", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_tenant_tool_registrations_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_definition_id"], ["tool_definitions.id"], name=op.f("fk_tenant_tool_registrations_tool_definition_id_tool_definitions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_tool_registrations")),
        sa.UniqueConstraint("tenant_id", "tool_definition_id", name="uq_tenant_tool_registrations_tenant_tool"),
    )
    op.create_index(op.f("ix_tenant_tool_registrations_tenant_id"), "tenant_tool_registrations", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_tenant_tool_registrations_tool_definition_id"), "tenant_tool_registrations", ["tool_definition_id"], unique=False)

    op.create_table(
        "tool_calls",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_tool_registration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("succeeded", "failed", "timed_out", name="tool_execution_status", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "failure_category",
            postgresql.ENUM(
                "none",
                "validation",
                "not_allowed",
                "not_found",
                "timeout",
                "transient",
                "internal",
                name="tool_failure_category",
                create_type=False,
            ),
            nullable=False,
            server_default="none",
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("request_payload", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("normalized_output", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_output", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_tool_calls_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], name=op.f("fk_tool_calls_run_id_workflow_runs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_step_id"], ["workflow_run_steps.id"], name=op.f("fk_tool_calls_run_step_id_workflow_run_steps"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tool_definition_id"], ["tool_definitions.id"], name=op.f("fk_tool_calls_tool_definition_id_tool_definitions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_tool_registration_id"], ["tenant_tool_registrations.id"], name=op.f("fk_tool_calls_tenant_tool_registration_id_tenant_tool_registrations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_calls")),
    )
    op.create_index(op.f("ix_tool_calls_tenant_id"), "tool_calls", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_tool_calls_run_id"), "tool_calls", ["run_id"], unique=False)
    op.create_index(op.f("ix_tool_calls_run_step_id"), "tool_calls", ["run_step_id"], unique=False)
    op.create_index(op.f("ix_tool_calls_tool_definition_id"), "tool_calls", ["tool_definition_id"], unique=False)
    op.create_index(op.f("ix_tool_calls_tenant_tool_registration_id"), "tool_calls", ["tenant_tool_registration_id"], unique=False)
    op.create_index(op.f("ix_tool_calls_tool_name"), "tool_calls", ["tool_name"], unique=False)
    op.create_index(op.f("ix_tool_calls_status"), "tool_calls", ["status"], unique=False)
    op.create_index(op.f("ix_tool_calls_failure_category"), "tool_calls", ["failure_category"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tool_calls_failure_category"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_status"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_tool_name"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_tenant_tool_registration_id"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_tool_definition_id"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_run_step_id"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_run_id"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_tenant_id"), table_name="tool_calls")
    op.drop_table("tool_calls")

    op.drop_index(op.f("ix_tenant_tool_registrations_tool_definition_id"), table_name="tenant_tool_registrations")
    op.drop_index(op.f("ix_tenant_tool_registrations_tenant_id"), table_name="tenant_tool_registrations")
    op.drop_table("tenant_tool_registrations")

    op.drop_index(op.f("ix_tool_definitions_source_type"), table_name="tool_definitions")
    op.drop_index(op.f("ix_tool_definitions_name"), table_name="tool_definitions")
    op.drop_table("tool_definitions")

    op.execute("DROP TYPE IF EXISTS tool_failure_category")
    op.execute("DROP TYPE IF EXISTS tool_execution_status")
    op.execute("DROP TYPE IF EXISTS tool_source_type")