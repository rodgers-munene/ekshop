"""seed free trial seller subscription plan

Revision ID: f5a6b7c8d9e0
Revises: f4a29b7c1e05
Create Date: 2026-09-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import uuid

# revision identifiers, used by Alembic.
revision = "f5a6b7c8d9e0"
down_revision = "f4a29b7c1e05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    subscription_plans = sa.table(
        "subscription_plans",
        sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("code", sa.String),
        sa.column("price_monthly", sa.String),
        sa.column("price_yearly", sa.String),
        sa.column("max_products", sa.Integer),
        sa.column("commission_rate", sa.String),
        sa.column("features", JSONB),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        subscription_plans,
        [
            {
                "id": uuid.uuid4(),
                "name": "Free Trial",
                "code": "free_trial",
                "price_monthly": "0.00",
                "price_yearly": "0.00",
                "max_products": 20,
                "commission_rate": "10.00",
                "features": {"featured_placement": False, "pos_access": False},
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        subscription_plans.delete().where(subscription_plans.c.code == "free_trial")
    )
