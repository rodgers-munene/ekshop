"""add renewal reminder timestamp columns to subscriptions

Revision ID: d8b1f4c72a93
Revises: c4f7a2e9b1d6
Create Date: 2026-09-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d8b1f4c72a93"
down_revision = "c4f7a2e9b1d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("reminder_7d_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("reminder_1d_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("subscriptions", "reminder_1d_sent_at")
    op.drop_column("subscriptions", "reminder_7d_sent_at")
