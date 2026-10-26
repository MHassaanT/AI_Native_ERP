"""Enrich material requests with accountable context and UOM snapshots.

Revision ID: 049_material_request_context
Revises: 048_sales_cost_snapshots
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "049_material_request_context"
down_revision = "048_sales_cost_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("material_requests", "purchase_orders"):
        op.add_column(table, sa.Column("required_by_date", sa.Date(), nullable=True))
        op.add_column(table, sa.Column("department", sa.String(128), nullable=True))
        op.add_column(table, sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("cost_center_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("attachments", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        op.add_column(table, sa.Column("source_warehouse_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(f"fk_{table}_project", table, "projects", ["project_id"], ["project_id"])
        op.create_foreign_key(f"fk_{table}_cost_center", table, "cost_centers", ["cost_center_id"], ["cost_center_id"])
        op.create_foreign_key(f"fk_{table}_source_warehouse", table, "warehouses", ["source_warehouse_id"], ["warehouse_id"])
    op.add_column("material_requests", sa.Column("amended_from_mr_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_material_requests_amended_from", "material_requests", "material_requests", ["amended_from_mr_id"], ["mr_id"])
    op.add_column("material_request_items", sa.Column("uom_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("material_request_items", sa.Column("conversion_factor", sa.Numeric(18, 8), nullable=False, server_default="1"))
    op.add_column("material_request_items", sa.Column("stock_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"))
    op.add_column("material_request_items", sa.Column("source_mr_item_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_material_request_item_uom", "material_request_items", "uoms", ["uom_id"], ["uom_id"])
    op.create_foreign_key("fk_material_request_item_source", "material_request_items", "material_request_items", ["source_mr_item_id"], ["mr_item_id"])
    op.create_check_constraint("ck_mr_item_conversion_positive", "material_request_items", "conversion_factor > 0")
    op.create_check_constraint("ck_mr_item_stock_quantity_nonnegative", "material_request_items", "stock_quantity >= 0")
    op.execute("UPDATE material_requests SET required_by_date = schedule_date WHERE required_by_date IS NULL")
    op.execute("""UPDATE purchase_orders p SET required_by_date = m.required_by_date
        FROM material_requests m WHERE p.material_request_id = m.mr_id
          AND p.tenant_id = m.tenant_id AND p.required_by_date IS NULL""")
    op.execute("UPDATE material_request_items SET stock_quantity = quantity WHERE stock_quantity = 0")


def downgrade() -> None:
    op.drop_constraint("ck_mr_item_stock_quantity_nonnegative", "material_request_items", type_="check")
    op.drop_constraint("ck_mr_item_conversion_positive", "material_request_items", type_="check")
    op.drop_constraint("fk_material_request_item_source", "material_request_items", type_="foreignkey")
    op.drop_constraint("fk_material_request_item_uom", "material_request_items", type_="foreignkey")
    for name in ("source_mr_item_id", "stock_quantity", "conversion_factor", "uom_id"):
        op.drop_column("material_request_items", name)
    op.drop_constraint("fk_material_requests_amended_from", "material_requests", type_="foreignkey")
    op.drop_column("material_requests", "amended_from_mr_id")
    for table in ("purchase_orders", "material_requests"):
        op.drop_constraint(f"fk_{table}_source_warehouse", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_cost_center", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_project", table, type_="foreignkey")
        for name in ("source_warehouse_id", "attachments", "cost_center_id", "project_id", "department", "required_by_date"):
            op.drop_column(table, name)
