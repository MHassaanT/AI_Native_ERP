"""Remove autonomous supervisor and agent approval-queue storage.

Revision ID: 014_remove_autonomous_workforce_and_hitl
Revises: 013_durable_inbound_email_review
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014_remove_autonomous_workforce_and_hitl"
down_revision: str | None = "013_durable_inbound_email_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENUMS = {
    "agentdomain": (
        "PROCUREMENT",
        "SALES",
        "INVENTORY",
        "HR_PAYROLL",
        "MANUFACTURING",
        "FINANCE",
        "SUPPORT_QUALITY",
    ),
    "autonomylevel": ("AUTONOMOUS", "HITL_REQUIRED", "DISABLED"),
    "approvalstatus": ("PENDING", "APPROVED", "REJECTED", "MODIFIED", "EXPIRED"),
    "risklevel": ("LOW", "MEDIUM", "HIGH", "CRITICAL"),
    "channeltype": ("WHATSAPP", "GMAIL", "INTERNAL"),
}


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    for table in (
        "agent_approvals",
        "agent_step_logs",
        "agent_communications",
        "agent_execution_runs",
        "agent_definitions",
    ):
        if table in tables:
            op.drop_table(table)

    for enum_name in ENUMS:
        op.execute(sa.text(f'DROP TYPE IF EXISTS "{enum_name}"'))


def downgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    agent_domain = postgresql.ENUM(*ENUMS["agentdomain"], name="agentdomain", create_type=False)
    autonomy_level = postgresql.ENUM(*ENUMS["autonomylevel"], name="autonomylevel", create_type=False)
    approval_status = postgresql.ENUM(*ENUMS["approvalstatus"], name="approvalstatus", create_type=False)
    risk_level = postgresql.ENUM(*ENUMS["risklevel"], name="risklevel", create_type=False)
    channel_type = postgresql.ENUM(*ENUMS["channeltype"], name="channeltype", create_type=False)

    op.create_table(
        "agent_definitions",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("domain", agent_domain, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("autonomy_level", autonomy_level, nullable=False, server_default="AUTONOMOUS"),
        sa.Column("trigger_type", sa.String(32), nullable=False, server_default="SCHEDULED"),
        sa.Column("cron_expression", sa.String(64)),
        sa.Column("interval_seconds", sa.Integer(), server_default="300"),
        sa.Column("system_prompt", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
    )
    op.create_index("ix_agent_definitions_tenant_id", "agent_definitions", ["tenant_id"])
    op.create_index("ix_agent_tenant_slug", "agent_definitions", ["tenant_id", "slug"], unique=True)

    op.create_table(
        "agent_execution_runs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_definitions.agent_id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("trigger_type", sa.String(32), nullable=False),
        sa.Column("trigger_context", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="RUNNING"),
        sa.Column("summary", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("execution_metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_agent_execution_runs_tenant_id", "agent_execution_runs", ["tenant_id"])

    op.create_table(
        "agent_step_logs",
        sa.Column("step_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_execution_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("node_name", sa.String(64), nullable=False),
        sa.Column("reasoning_thought", sa.Text()),
        sa.Column("tool_name", sa.String(64)),
        sa.Column("tool_arguments", postgresql.JSONB()),
        sa.Column("tool_output", postgresql.JSONB()),
        sa.Column("status", sa.String(32), nullable=False, server_default="COMPLETED"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
    )
    op.create_index("ix_agent_step_logs_run_id", "agent_step_logs", ["run_id"])

    op.create_table(
        "agent_approvals",
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_execution_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True)),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("domain", agent_domain, nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("action_payload", postgresql.JSONB(), nullable=False),
        sa.Column("risk_level", risk_level, nullable=False, server_default="HIGH"),
        sa.Column("required_role", sa.String(32), nullable=False, server_default="Admin"),
        sa.Column("ai_rationale", sa.Text(), nullable=False),
        sa.Column("status", approval_status, nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True)),
        sa.Column("reviewer_notes", sa.Text()),
        sa.Column("modified_payload", postgresql.JSONB()),
        sa.Column("action_execution_status", sa.String(24), nullable=False, server_default="NOT_STARTED"),
        sa.Column("action_execution_result", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_agent_approvals_tenant_id", "agent_approvals", ["tenant_id"])
    op.create_index("ix_agent_approvals_status", "agent_approvals", ["status"])

    op.create_table(
        "agent_communications",
        sa.Column("comm_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("channel", channel_type, nullable=False),
        sa.Column("recipient", sa.String(256), nullable=False),
        sa.Column("subject", sa.String(256)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("external_message_id", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
    )
    op.create_index("ix_agent_communications_tenant_id", "agent_communications", ["tenant_id"])
