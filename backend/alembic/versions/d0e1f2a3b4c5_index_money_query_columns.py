"""index the columns every money query filters on

Moving the admin dashboard from `order_groups.created_at` to `payments.paid_at`
put a date filter onto a table that had no indexes at all. `payments` declared
two foreign keys and a unique `provider_ref`, and nothing else -- and Postgres
does not index foreign keys automatically.

Every window query is now "successful payments where coalesce(paid_at,
created_at) falls between X and Y", and the trend groups that by day. Against an
unindexed table that is a sequential scan of every payment ever taken, on every
stat card, on every page load. It is correct but it gets slower every month, and
the payments table is the one that grows fastest.

The composite indexes are ordered (status, time) because the status is always an
equality filter and the window is always a range.

`coalesce(paid_at, created_at)` cannot use a plain index on either column, so
this adds an expression index over the same expression the queries use. That is
the difference between an index scan and a sequential scan.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""

from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The expression every money query filters on. Partial, because pending and
    # failed payments are never counted in a figure -- indexing them would only
    # bloat the index.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_payments_money_instant
            ON payments (coalesce(paid_at, created_at))
         WHERE status = 'success'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_payments_status_money_instant
            ON payments (status, coalesce(paid_at, created_at))
        """
    )
    # Foreign keys: unindexed, so joining groups to their payments or listing a
    # payer's history means scanning.
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_order_group_id ON payments (order_group_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_user_id ON payments (user_id)")
    # provider_ref is already unique; no index needed.

    # Order-group lookups still used by the orders list and merchant metrics.
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_groups_status_created_at ON order_groups (status, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_groups_buyer_id ON order_groups (buyer_id)")

    # The churn query groups by buyer and takes max(created_at) per buyer.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_order_groups_buyer_created_at
            ON order_groups (buyer_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_order_groups_buyer_created_at")
    op.execute("DROP INDEX IF EXISTS ix_order_groups_buyer_id")
    op.execute("DROP INDEX IF EXISTS ix_order_groups_status_created_at")
    op.execute("DROP INDEX IF EXISTS ix_payments_user_id")
    op.execute("DROP INDEX IF EXISTS ix_payments_order_group_id")
    op.execute("DROP INDEX IF EXISTS ix_payments_status_money_instant")
    op.execute("DROP INDEX IF EXISTS ix_payments_money_instant")