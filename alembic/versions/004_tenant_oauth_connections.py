"""004 Tenant OAuth Connections Schema (Gmail OAuth 2.0 Persistence)

Revision ID: 004_tenant_oauth_connections
Revises: 003_complete_business_cycles
Create Date: 2026-09-19 20:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004_tenant_oauth_connections"
down_revision: str | None = "003_complete_business_cycles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "tenant_oauth_connections" not in existing_tables:
        op.create_table(
            "tenant_oauth_connections",
            sa.Column("connection_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("provider", sa.String(64), nullable=False, server_default="google_gmail"),
            sa.Column("is_connected", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("connected_email", sa.String(255), nullable=True),
            sa.Column("access_token", sa.Text(), nullable=True),
            sa.Column("refresh_token", sa.Text(), nullable=True),
            sa.Column("token_type", sa.String(32), nullable=False, server_default="Bearer"),
            sa.Column("scopes", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("last_synced_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("synced_messages_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("tenant_id", "provider", name="uq_tenant_provider"),
        )
        op.create_index(
            "idx_tenant_oauth_provider",
            "tenant_oauth_connections",
            ["tenant_id", "provider"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "tenant_oauth_connections" in existing_tables:
        op.drop_index("idx_tenant_oauth_provider", table_name="tenant_oauth_connections")
        op.drop_table("tenant_oauth_connections")
