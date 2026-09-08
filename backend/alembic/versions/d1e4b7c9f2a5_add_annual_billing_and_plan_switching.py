"""add annual billing option and staged plan-switching to subscriptions

Revision ID: d1e4b7c9f2a5
Revises: b6d3f9a1c8e2
Create Date: 2026-09-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d1e4b7c9f2a5"
down_revision = "b6d3f9a1c8e2"
branch_labels = None
depends_on = None

# 10-months-for-12 discount on the monthly price.
ANNUAL_PRICES = {
    "duka_starter": "5000.00",
    "duka_premium": "99990.00",
}


def upgrade() -> None:
    op.add_column("subscription_plans", sa.Column("price_yearly", sa.String(length=20)))

    op.add_column(
        "subscriptions",
        sa.Column(
            "billing_interval",
            sa.String(length=20),
            nullable=False,
            server_default="monthly",
        ),
    )
    op.add_column(
        "subscriptions",
        sa.Column("pending_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_plans.id")),
    )
    op.add_column(
        "subscriptions",
        sa.Column("pending_billing_interval", sa.String(length=20)),
    )

    subscription_plans = sa.table(
        "subscription_plans",
        sa.column("code", sa.String),
        sa.column("price_yearly", sa.String),
    )
    for code, price in ANNUAL_PRICES.items():
        op.execute(
            subscription_plans.update().where(subscription_plans.c.code == code).values(price_yearly=price)
        )


def downgrade() -> None:
    op.drop_column("subscriptions", "pending_billing_interval")
    op.drop_column("subscriptions", "pending_plan_id")
    op.drop_column("subscriptions", "billing_interval")
    op.drop_column("subscription_plans", "price_yearly")
