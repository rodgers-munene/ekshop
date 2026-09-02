"""add standard_delivery_hours SLA to delivery_rate_settings

Revision ID: a7c3e19f6b28
Revises: f4a29b7c1e05
Create Date: 2026-09-02 00:00:00.000002

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7c3e19f6b28"
down_revision = "f4a29b7c1e05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delivery_rate_settings",
        sa.Column("standard_delivery_hours", sa.Integer(), nullable=False, server_default="48"),
    )


def downgrade() -> None:
    op.drop_column("delivery_rate_settings", "standard_delivery_hours")
