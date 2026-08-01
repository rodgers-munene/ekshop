"""add shop is_featured flag

Revision ID: 7c1a9e2b4d3f
Revises: 3aa77bcd1dc3
Create Date: 2026-08-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7c1a9e2b4d3f"
down_revision = "3aa77bcd1dc3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shops",
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("shops", "is_featured")
