"""add promotion sort_order and is_active

Revision ID: 9f2d4a6c1b8e
Revises: 7c1a9e2b4d3f
Create Date: 2026-08-01 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f2d4a6c1b8e"
down_revision = "7c1a9e2b4d3f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("promotions", sa.Column("sort_order", sa.Integer(), server_default="0"))
    op.add_column(
        "promotions",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("promotions", "is_active")
    op.drop_column("promotions", "sort_order")
