"""Add richer inventory catalog data and item tasks.

Revision ID: 019_inventory_catalog
Revises: 019_whatsapp_knowledge_sources
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "019_inventory_catalog"
down_revision: str | None = "019_whatsapp_knowledge_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("items", sa.Column("barcode", sa.String(length=64), nullable=True))
    op.add_column("items", sa.Column("brand", sa.String(length=255), nullable=True))
    op.add_column("items", sa.Column("category", sa.String(length=255), nullable=True))
    op.add_column("items", sa.Column("package_quantity", sa.String(length=128), nullable=True))
    op.add_column("items", sa.Column("image_url", sa.Text(), nullable=True))

    op.create_table(
        "item_todos",
        sa.Column("todo_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assigned_to", sa.String(length=255), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.item_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("todo_id"),
        sa.CheckConstraint(
            "status IN ('TODO', 'IN_PROGRESS', 'DONE')",
            name="ck_item_todos_status",
        ),
    )
    op.create_index("ix_item_todos_tenant_id", "item_todos", ["tenant_id"])
    op.create_index("ix_item_todos_tenant_item", "item_todos", ["tenant_id", "item_id"])


def downgrade() -> None:
    op.drop_index("ix_item_todos_tenant_item", table_name="item_todos")
    op.drop_index("ix_item_todos_tenant_id", table_name="item_todos")
    op.drop_table("item_todos")
    op.drop_column("items", "image_url")
    op.drop_column("items", "package_quantity")
    op.drop_column("items", "category")
    op.drop_column("items", "brand")
    op.drop_column("items", "barcode")
