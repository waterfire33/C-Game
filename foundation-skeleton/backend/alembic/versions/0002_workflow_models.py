"""add workflow models

Revision ID: 0002_workflow_models
Revises: 0001_initial
Create Date: 2026-03-29 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_workflow_models"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_status_enum = postgresql.ENUM(
        'pending', 'running', 'awaiting_approval', 'paused', 'completed', 'failed', 'cancelled',
        name='run_status',
        create_type=True
    )
    run_status_enum.create(op.get_bind(), checkfirst=True)

    step_status_enum = postgresql.ENUM(
        'pending', 'running', 'awaiting_approval', 'completed', 'failed', 'skipped',
        name='step_status',
        create_type=True
    )
    step_status_enum.create(op.get_bind(), checkfirst=True)

    event_type_enum = postgresql.ENUM(
        'run_created', 'run_started', 'run_paused', 'run_resumed', 'run_completed', 'run_failed',
        'run_cancelled', 'run_retry_requested', 'step_started', 'step_completed', 'step_failed',
        'step_retry_scheduled', 'approval_requested', 'approval_granted', 'approval_denied',
        'state_updated',
        name='event_type',
        create_type=True
    )
    event_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "workflow_definitions",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name=op.f("fk_workflow_definitions_created_by_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_workflow_definitions_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_definitions")),
    )
    op.create_index(op.f("ix_workflow_definitions_tenant_id"), "workflow_definitions", ["tenant_id"], unique=False)

    op.create_table(
        "workflow_step_definitions",
        sa.Column("workflow_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("step_type", sa.String(length=50), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("config", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["workflow_definition_id"], ["workflow_definitions.id"], name=op.f("fk_workflow_step_definitions_workflow_definition_id_workflow_definitions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_step_definitions")),
        sa.UniqueConstraint("workflow_definition_id", "order", name="uq_workflow_step_definitions_workflow_definition_order"),
    )
    op.create_index(op.f("ix_workflow_step_definitions_workflow_definition_id"), "workflow_step_definitions", ["workflow_definition_id"], unique=False)

    op.create_table(
        "workflow_runs",
        sa.Column("workflow_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", postgresql.ENUM('pending', 'running', 'awaiting_approval', 'paused', 'completed', 'failed', 'cancelled', name='run_status', create_type=False), nullable=False, server_default="pending"),
        sa.Column("current_step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("input_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("output_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(length=255), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_workflow_runs_tenant_id_tenants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], name=op.f("fk_workflow_runs_triggered_by_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_definition_id"], ["workflow_definitions.id"], name=op.f("fk_workflow_runs_workflow_definition_id_workflow_definitions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_runs")),
        sa.UniqueConstraint("idempotency_key", name="uq_workflow_runs_idempotency_key"),
    )
    op.create_index(op.f("ix_workflow_runs_idempotency_key"), "workflow_runs", ["idempotency_key"], unique=False)
    op.create_index(op.f("ix_workflow_runs_status"), "workflow_runs", ["status"], unique=False)
    op.create_index(op.f("ix_workflow_runs_tenant_id"), "workflow_runs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_workflow_runs_workflow_definition_id"), "workflow_runs", ["workflow_definition_id"], unique=False)

    op.create_table(
        "workflow_run_steps",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", postgresql.ENUM('pending', 'running', 'awaiting_approval', 'completed', 'failed', 'skipped', name='step_status', create_type=False), nullable=False, server_default="pending"),
        sa.Column("input_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("output_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], name=op.f("fk_workflow_run_steps_approved_by_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], name=op.f("fk_workflow_run_steps_run_id_workflow_runs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_definition_id"], ["workflow_step_definitions.id"], name=op.f("fk_workflow_run_steps_step_definition_id_workflow_step_definitions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_run_steps")),
        sa.UniqueConstraint("run_id", "step_index", name="uq_workflow_run_steps_run_step_index"),
    )
    op.create_index(op.f("ix_workflow_run_steps_idempotency_key"), "workflow_run_steps", ["idempotency_key"], unique=False)
    op.create_index(op.f("ix_workflow_run_steps_run_id"), "workflow_run_steps", ["run_id"], unique=False)

    op.create_table(
        "workflow_events",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", postgresql.ENUM(
            'run_created', 'run_started', 'run_paused', 'run_resumed', 'run_completed', 'run_failed',
            'run_cancelled', 'run_retry_requested', 'step_started', 'step_completed', 'step_failed',
            'step_retry_scheduled', 'approval_requested', 'approval_granted', 'approval_denied',
            'state_updated',
            name='event_type', create_type=False
        ), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.String(length=50), nullable=False, server_default="system"),
        sa.Column("previous_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=True),
        sa.Column("payload", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name=op.f("fk_workflow_events_actor_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], name=op.f("fk_workflow_events_run_id_workflow_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_events")),
        sa.UniqueConstraint("run_id", "sequence_number", name="uq_workflow_events_run_sequence"),
    )
    op.create_index(op.f("ix_workflow_events_event_type"), "workflow_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_workflow_events_created_at"), "workflow_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_workflow_events_run_id"), "workflow_events", ["run_id"], unique=False)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS workflow_events CASCADE")
    op.execute("DROP TABLE IF EXISTS workflow_run_steps CASCADE")
    op.execute("DROP TABLE IF EXISTS workflow_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS workflow_step_definitions CASCADE")
    op.execute("DROP TABLE IF EXISTS workflow_definitions CASCADE")
    op.execute("DROP TYPE IF EXISTS event_type")
    op.execute("DROP TYPE IF EXISTS step_status")
    op.execute("DROP TYPE IF EXISTS run_status")
