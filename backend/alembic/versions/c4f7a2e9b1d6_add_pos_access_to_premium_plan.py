"""add pos_access feature flag to the seller subscription plans

Revision ID: c4f7a2e9b1d6
Revises: b2e5c8a1f3d9
Create Date: 2026-09-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c4f7a2e9b1d6"
down_revision = "b2e5c8a1f3d9"
branch_labels = None
depends_on = None

subscription_plans = sa.table(
    "subscription_plans",
    sa.column("code", sa.String),
    sa.column("features", sa.dialects.postgresql.JSONB),
)


def upgrade() -> None:
    op.execute(
        subscription_plans.update()
        .where(subscription_plans.c.code == "duka_premium")
        .values(features={"featured_placement": True, "pos_access": True})
    )
    op.execute(
        subscription_plans.update()
        .where(subscription_plans.c.code == "duka_starter")
        .values(features={"featured_placement": False, "pos_access": False})
    )


def downgrade() -> None:
    op.execute(
        subscription_plans.update()
        .where(subscription_plans.c.code == "duka_premium")
        .values(features={"featured_placement": True})
    )
    op.execute(
        subscription_plans.update()
        .where(subscription_plans.c.code == "duka_starter")
        .values(features={"featured_placement": False})
    )
