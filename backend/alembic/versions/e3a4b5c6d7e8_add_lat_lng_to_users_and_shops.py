"""add latitude/longitude columns to users and shops

Revision ID: e3a4b5c6d7e8
Revises: f4a29b7c1e05
Create Date: 2026-09-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e3a4b5c6d7e8"
down_revision = "f4a29b7c1e05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("lng", sa.Float(), nullable=True))
    op.add_column("shops", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("shops", sa.Column("lng", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("shops", "lng")
    op.drop_column("shops", "lat")
    op.drop_column("users", "lng")
    op.drop_column("users", "lat")
