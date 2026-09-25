"""add trial_days to subscription_plans and seed Duka Starter trial"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h7i8j9k0l1m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("subscription_plans")}

    if "trial_days" not in existing_cols:
        op.add_column("subscription_plans", sa.Column("trial_days", sa.Integer(), server_default="0", nullable=False))

    if "duka_starter" in {row[1] for row in bind.execute(sa.text("SELECT id, code FROM subscription_plans WHERE code = 'duka_starter'")).fetchall()}:
        bind.execute(sa.text("UPDATE subscription_plans SET trial_days = 30 WHERE code = 'duka_starter'"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("subscription_plans")}
    if "trial_days" in existing_cols:
        op.drop_column("subscription_plans", "trial_days")
