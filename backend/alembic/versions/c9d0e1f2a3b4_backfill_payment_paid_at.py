"""backfill paid_at on payments recorded before the column was populated

`payments.paid_at` was declared in the schema but never assigned by any code
path, so every existing successful payment had it NULL. Money-based analytics
cannot filter on a NULL timestamp, and `created_at` is the record-write time
rather than the moment the money landed -- for an M-Pesa STK push resolved by a
delayed callback those can be hours apart, which is exactly the window where
"what did we take yesterday" gives the wrong answer.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""

from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # created_at is the best available proxy: it is when the payment row was
    # committed, which for every write path in app/routers/payments.py is the
    # moment the provider confirmed success.
    op.execute(
        """
        UPDATE payments
           SET paid_at = created_at
         WHERE paid_at IS NULL
           AND status IN ('success', 'refunded')
        """
    )


def downgrade() -> None:
    # Deliberately a no-op. These timestamps were inferred, not known, so
    # clearing them would destroy information rather than restore it.
    pass