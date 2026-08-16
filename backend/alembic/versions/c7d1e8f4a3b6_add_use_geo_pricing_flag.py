"""add use_geo_pricing flag to delivery_rate_settings

Revision ID: c7d1e8f4a3b6
Revises: b4e6c9a1d7f2
Create Date: 2026-08-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c7d1e8f4a3b6"
down_revision = "b4e6c9a1d7f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delivery_rate_settings",
        sa.Column("use_geo_pricing", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("delivery_rate_settings", "use_geo_pricing")
