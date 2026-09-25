"""add alert toggle columns to automation_settings"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "7a8678777331"
down_revision: Union[str, None] = "j1k2l3m4n5o6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("automation_settings", sa.Column("alert_gross_margin_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("automation_settings", sa.Column("alert_order_cancellation_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("automation_settings", sa.Column("alert_cart_abandonment_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("automation_settings", sa.Column("alert_on_time_delivery_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))


def downgrade() -> None:
    op.drop_column("automation_settings", "alert_on_time_delivery_enabled")
    op.drop_column("automation_settings", "alert_cart_abandonment_enabled")
    op.drop_column("automation_settings", "alert_order_cancellation_enabled")
    op.drop_column("automation_settings", "alert_gross_margin_enabled")
