"""add lat/lng/sublocation columns to user_addresses

Revision ID: e2f7a9c4b6d8
Revises: d1e4b7c9f2a5
Create Date: 2026-09-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e2f7a9c4b6d8"
down_revision = "d1e4b7c9f2a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_addresses", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("user_addresses", sa.Column("lng", sa.Float(), nullable=True))
    op.add_column("user_addresses", sa.Column("sublocation", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("user_addresses", "sublocation")
    op.drop_column("user_addresses", "lng")
    op.drop_column("user_addresses", "lat")