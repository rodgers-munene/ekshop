"""widen subscriptions.status to fit pending_payment

The column was originally created as VARCHAR(9), sized off an enum literal
list ('active', 'cancelled', 'past_due', 'trialing') in the master schema
migration that predates `pending_payment` (15 chars) being added to the
SubscriptionStatus model. Every seller registration since then has crashed
with a StringDataRightTruncation error inserting the pending_payment row.

Revision ID: a91c4e0f6b7d
Revises: f2a6c91b8d47
Create Date: 2026-09-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a91c4e0f6b7d"
down_revision = "f2a6c91b8d47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "subscriptions",
        "status",
        existing_type=sa.String(length=9),
        type_=sa.String(length=20),
    )


def downgrade() -> None:
    op.alter_column(
        "subscriptions",
        "status",
        existing_type=sa.String(length=20),
        type_=sa.String(length=9),
    )
