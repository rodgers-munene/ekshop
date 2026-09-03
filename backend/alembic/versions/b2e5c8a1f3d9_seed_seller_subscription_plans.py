"""seed the two interim seller subscription plans (Duka Starter / Duka Premium)

Revision ID: b2e5c8a1f3d9
Revises: a7c3e19f6b28
Create Date: 2026-09-03 00:00:00.000000

"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "b2e5c8a1f3d9"
down_revision = "a7c3e19f6b28"
branch_labels = None
depends_on = None

subscription_plans = sa.table(
    "subscription_plans",
    sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
    sa.column("name", sa.String),
    sa.column("code", sa.String),
    sa.column("price_monthly", sa.String),
    sa.column("max_products", sa.Integer),
    sa.column("commission_rate", sa.String),
    sa.column("features", JSONB),
    sa.column("is_active", sa.Boolean),
)

PLAN_CODES = ("duka_starter", "duka_premium")


def upgrade() -> None:
    op.bulk_insert(
        subscription_plans,
        [
            {
                "id": uuid.uuid4(),
                "name": "Duka Starter",
                "code": "duka_starter",
                "price_monthly": "500.00",
                "max_products": 20,
                "commission_rate": "10.00",
                "features": {"featured_placement": False},
                "is_active": True,
            },
            {
                "id": uuid.uuid4(),
                "name": "Duka Premium",
                "code": "duka_premium",
                "price_monthly": "9999.00",
                "max_products": None,
                "commission_rate": "7.00",
                "features": {"featured_placement": True},
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        subscription_plans.delete().where(subscription_plans.c.code.in_(PLAN_CODES))
    )
