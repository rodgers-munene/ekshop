"""add distance_km and duration_min to deliveries

Revision ID: g6h7i8j9k0l1
Revises: e3a4b5c6d7e8
Create Date: 2026-09-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "g6h7i8j9k0l1"
down_revision = "e3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deliveries", sa.Column("distance_km", sa.Float(), nullable=True))
    op.add_column("deliveries", sa.Column("duration_min", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("deliveries", "duration_min")
    op.drop_column("deliveries", "distance_km")
