"""add agent router and planning contract

Revision ID: 0005_agent_router
Revises: 0004_approval_engine
Create Date: 2026-03-29 12:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_agent_router"
down_revision = "0004_approval_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    workflow_type_enum = postgresql.ENUM(
        "information_request",
        "draft_action",
        "executable_tool",
        name="workflow_type",
        create_type=True,
    )
    workflow_type_enum.create(op.get_bind(), checkfirst=True)

    planner_strategy_enum = postgresql.ENUM(
        "deterministic",
        "llm",
        name="planner_strategy",
        create_type=True,
    )
    planner_strategy_enum.create(op.get_bind(), checkfirst=True)

    plan_status_enum = postgresql.ENUM(
        "pending",
        "routed",
        "failed",
        name="plan_status",
        create_type=True,
    )
    plan_status_enum.create(op.get_bind(), checkfirst=True)

    planner_failure_category_enum = postgresql.ENUM(
        "none",
        "unparseable_output",
        "no_matching_workflow",
        "llm_timeout",
        "llm_refusal",
        "invalid_plan_schema",
        "internal_error",
        name="planner_failure_category",
        create_type=True,
    )
    planner_failure_category_enum.create(op.get_bind(), checkfirst=True)

    # agent_requests table
    op.create_table(
        "agent_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_agent_requests_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"], ["users.id"],
            name=op.f("fk_agent_requests_submitted_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_requests")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_agent_requests_idempotency_key")),
    )
    op.create_index(op.f("ix_agent_requests_tenant_id"), "agent_requests", ["tenant_id"])
    op.create_index(op.f("ix_agent_requests_idempotency_key"), "agent_requests", ["idempotency_key"])

    # plan_records table
    op.create_table(
        "plan_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "workflow_type",
            postgresql.ENUM("information_request", "draft_action", "executable_tool", name="workflow_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "strategy",
            postgresql.ENUM("deterministic", "llm", name="planner_strategy", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "routed", "failed", name="plan_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("planned_steps", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("selected_workflow_definition_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "failure_category",
            postgresql.ENUM(
                "none", "unparseable_output", "no_matching_workflow", "llm_timeout",
                "llm_refusal", "invalid_plan_schema", "internal_error",
                name="planner_failure_category", create_type=False,
            ),
            nullable=False,
            server_default="none",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("prompt_snapshot", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_llm_output", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_plan_records_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_request_id"], ["agent_requests.id"],
            name=op.f("fk_plan_records_agent_request_id_agent_requests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["selected_workflow_definition_id"], ["workflow_definitions.id"],
            name=op.f("fk_plan_records_selected_workflow_definition_id_workflow_definitions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["workflow_runs.id"],
            name=op.f("fk_plan_records_run_id_workflow_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_records")),
        sa.UniqueConstraint("agent_request_id", name=op.f("uq_plan_records_agent_request_id")),
    )
    op.create_index(op.f("ix_plan_records_tenant_id"), "plan_records", ["tenant_id"])
    op.create_index(op.f("ix_plan_records_agent_request_id"), "plan_records", ["agent_request_id"])
    op.create_index(op.f("ix_plan_records_workflow_type"), "plan_records", ["workflow_type"])
    op.create_index(op.f("ix_plan_records_status"), "plan_records", ["status"])
    op.create_index(op.f("ix_plan_records_selected_workflow_definition_id"), "plan_records", ["selected_workflow_definition_id"])
    op.create_index(op.f("ix_plan_records_run_id"), "plan_records", ["run_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_plan_records_run_id"), table_name="plan_records")
    op.drop_index(op.f("ix_plan_records_selected_workflow_definition_id"), table_name="plan_records")
    op.drop_index(op.f("ix_plan_records_status"), table_name="plan_records")
    op.drop_index(op.f("ix_plan_records_workflow_type"), table_name="plan_records")
    op.drop_index(op.f("ix_plan_records_agent_request_id"), table_name="plan_records")
    op.drop_index(op.f("ix_plan_records_tenant_id"), table_name="plan_records")
    op.drop_table("plan_records")

    op.drop_index(op.f("ix_agent_requests_idempotency_key"), table_name="agent_requests")
    op.drop_index(op.f("ix_agent_requests_tenant_id"), table_name="agent_requests")
    op.drop_table("agent_requests")

    op.execute("DROP TYPE IF EXISTS planner_failure_category")
    op.execute("DROP TYPE IF EXISTS plan_status")
    op.execute("DROP TYPE IF EXISTS planner_strategy")
    op.execute("DROP TYPE IF EXISTS workflow_type")
