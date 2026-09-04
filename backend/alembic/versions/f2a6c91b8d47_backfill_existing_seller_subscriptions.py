"""backfill a Duka Starter subscription for every pre-existing shop

Sellers who registered before the subscription system existed have no
Subscription row at all, leaving them outside billing entirely. This gives
each of them an `active` subscription on Duka Starter with a 30-day grace
period before the normal renewal-reminder/expiry cycle applies to them for
the first time.

Revision ID: f2a6c91b8d47
Revises: d8b1f4c72a93
Create Date: 2026-09-04 00:00:00.000001

"""
import uuid
from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f2a6c91b8d47"
down_revision = "d8b1f4c72a93"
branch_labels = None
depends_on = None

GRACE_PERIOD_DAYS = 30

subscriptions = sa.table(
    "subscriptions",
    sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.column("shop_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.column("plan_id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.column("status", sa.String),
    sa.column("current_period_start", sa.DateTime(timezone=True)),
    sa.column("current_period_end", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    bind = op.get_bind()

    plan_id = bind.execute(
        sa.text("SELECT id FROM subscription_plans WHERE code = 'duka_starter'")
    ).scalar()
    if plan_id is None:
        raise RuntimeError("duka_starter plan not found — seed migration must run first")

    shop_ids = bind.execute(
        sa.text(
            "SELECT s.id FROM shops s "
            "LEFT JOIN subscriptions sub ON sub.shop_id = s.id "
            "WHERE sub.id IS NULL"
        )
    ).scalars().all()
    if not shop_ids:
        return

    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=GRACE_PERIOD_DAYS)

    op.bulk_insert(
        subscriptions,
        [
            {
                "id": uuid.uuid4(),
                "shop_id": shop_id,
                "plan_id": plan_id,
                "status": "active",
                "current_period_start": now,
                "current_period_end": period_end,
                "created_at": now,
                "updated_at": now,
            }
            for shop_id in shop_ids
        ],
    )


def downgrade() -> None:
    # provider_ref is left NULL only by this backfill — every other code path
    # (registration, renewal) sets it before or immediately after insert.
    op.execute("DELETE FROM subscriptions WHERE provider_ref IS NULL")
