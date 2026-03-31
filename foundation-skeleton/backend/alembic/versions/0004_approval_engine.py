"""add approval engine

Revision ID: 0004_approval_engine
Revises: 0003_tool_abstraction_layer
Create Date: 2026-03-29 02:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_approval_engine"
down_revision = "0003_tool_abstraction_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    action_risk_class_enum = postgresql.ENUM(
        "A",
        "B",
        "C",
        "D",
        name="action_risk_class",
        create_type=True,
    )
    action_risk_class_enum.create(op.get_bind(), checkfirst=True)

    approval_request_status_enum = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        "cancelled",
        name="approval_request_status",
        create_type=True,
    )
    approval_request_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "workflow_step_definitions",
        sa.Column(
            "action_risk_class",
            postgresql.ENUM("A", "B", "C", "D", name="action_risk_class", create_type=False),
            nullable=False,
            server_default="A",
        ),
    )
    op.add_column(
        "workflow_step_definitions",
        sa.Column("required_approver_role", sa.String(length=50), nullable=True),
    )
    op.create_index(
        op.f("ix_workflow_step_definitions_action_risk_class"),
        "workflow_step_definitions",
        ["action_risk_class"],
        unique=False,
    )

    op.execute(
        """
        UPDATE workflow_step_definitions
        SET action_risk_class = CASE
            WHEN requires_approval = true THEN 'C'::action_risk_class
            ELSE 'A'::action_risk_class
        END,
        required_approver_role = CASE
            WHEN requires_approval = true THEN 'admin'
            ELSE NULL
        END
        """
    )

    op.create_table(
        "approval_requests",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "approved",
                "rejected",
                "cancelled",
                name="approval_request_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "action_risk_class",
            postgresql.ENUM("A", "B", "C", "D", name="action_risk_class", create_type=False),
            nullable=False,
        ),
        sa.Column("required_role", sa.String(length=50), nullable=True),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("decision_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("request_context", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["decision_by_user_id"], ["users.id"], name=op.f("fk_approval_requests_decision_by_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], name=op.f("fk_approval_requests_requested_by_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], name=op.f("fk_approval_requests_run_id_workflow_runs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_step_id"], ["workflow_run_steps.id"], name=op.f("fk_approval_requests_run_step_id_workflow_run_steps"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_definition_id"], ["workflow_step_definitions.id"], name=op.f("fk_approval_requests_step_definition_id_workflow_step_definitions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_approval_requests_tenant_id_tenants"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_requests")),
    )
    op.create_index(op.f("ix_approval_requests_tenant_id"), "approval_requests", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_approval_requests_run_id"), "approval_requests", ["run_id"], unique=False)
    op.create_index(op.f("ix_approval_requests_run_step_id"), "approval_requests", ["run_step_id"], unique=False)
    op.create_index(op.f("ix_approval_requests_step_definition_id"), "approval_requests", ["step_definition_id"], unique=False)
    op.create_index(op.f("ix_approval_requests_step_index"), "approval_requests", ["step_index"], unique=False)
    op.create_index(op.f("ix_approval_requests_status"), "approval_requests", ["status"], unique=False)
    op.create_index(op.f("ix_approval_requests_action_risk_class"), "approval_requests", ["action_risk_class"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_approval_requests_action_risk_class"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_status"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_step_index"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_step_definition_id"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_run_step_id"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_run_id"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_tenant_id"), table_name="approval_requests")
    op.drop_table("approval_requests")

    op.drop_index(op.f("ix_workflow_step_definitions_action_risk_class"), table_name="workflow_step_definitions")
    op.drop_column("workflow_step_definitions", "required_approver_role")
    op.drop_column("workflow_step_definitions", "action_risk_class")

    op.execute("DROP TYPE IF EXISTS approval_request_status")
    op.execute("DROP TYPE IF EXISTS action_risk_class")