"""add last_activated_ref to subscriptions

Tracks the provider_ref that was actually applied by activate_subscription,
so idempotency no longer relies on subscription.status == active — that
shortcut made early renewal (paying again while still active, to push the
expiry date out) silently no-op instead of extending the period.

Revision ID: b6d3f9a1c8e2
Revises: a91c4e0f6b7d
Create Date: 2026-09-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b6d3f9a1c8e2"
down_revision = "a91c4e0f6b7d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("last_activated_ref", sa.String(length=100), nullable=True))
    op.execute("UPDATE subscriptions SET last_activated_ref = provider_ref WHERE status = 'active'")


def downgrade() -> None:
    op.drop_column("subscriptions", "last_activated_ref")
