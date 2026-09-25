"""give the paid seller plans a 14-day trial and retire the Free Trial plan

A trial is now a period of free access to the plan the seller chose, so the
separate KES 0 "free_trial" plan (seeded in f5a6b7c8d9e0) is deactivated
rather than deleted, in case a subscription already references it.
"""
from typing import Sequence, Union
from alembic import op

revision: str = "c7e3f9a1d2b4"
down_revision: Union[str, None] = "b4d9e1a7c3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE subscription_plans SET trial_days = 14 WHERE code IN ('duka_starter', 'duka_premium')")
    op.execute("UPDATE subscription_plans SET is_active = false WHERE code = 'free_trial'")


def downgrade() -> None:
    op.execute("UPDATE subscription_plans SET is_active = true WHERE code = 'free_trial'")
    op.execute("UPDATE subscription_plans SET trial_days = 0 WHERE code = 'duka_premium'")
    op.execute("UPDATE subscription_plans SET trial_days = 30 WHERE code = 'duka_starter'")
