"""Allow a POS profile to pin its selling price list.

Revision ID: 054_pos_profile_price_list
Revises: 053_pos_bundle_snapshots
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "054_pos_profile_price_list"
down_revision = "053_pos_bundle_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_profiles", sa.Column("price_list_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_pos_profile_price_list", "pos_profiles", "price_lists", ["price_list_id"], ["price_list_id"])


def downgrade() -> None:
    op.drop_constraint("fk_pos_profile_price_list", "pos_profiles", type_="foreignkey")
    op.drop_column("pos_profiles", "price_list_id")
