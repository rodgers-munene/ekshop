"""add current_lat/current_lng to delivery_agents

Revision ID: h7i8j9k0l1m4
Revises: 594eefc41e58
Create Date: 2026-09-21 16:45:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "h7i8j9k0l1m4"
down_revision: Union[str, None] = "594eefc41e58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("delivery_agents", sa.Column("current_lat", sa.Float(), nullable=True))
    op.add_column("delivery_agents", sa.Column("current_lng", sa.Float(), nullable=True))
    op.add_column("delivery_agents", sa.Column("last_location_update", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("delivery_agents", "last_location_update")
    op.drop_column("delivery_agents", "current_lng")
    op.drop_column("delivery_agents", "current_lat")
