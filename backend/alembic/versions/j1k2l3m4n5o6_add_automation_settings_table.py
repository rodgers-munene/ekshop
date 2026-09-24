"""add automation_settings table"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "j1k2l3m4n5o6"
down_revision: Union[str, None] = "i9j0k1l2m3n5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "automation_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("webhook_url", sa.String(512), nullable=True),
        sa.Column("webhook_secret", sa.String(255), nullable=True),
        sa.Column("alert_min_gross_margin_pct", sa.Float, nullable=False, server_default="90.0"),
        sa.Column("alert_max_mpesa_latency_seconds", sa.Float, nullable=False, server_default="2.0"),
        sa.Column("alert_max_hosting_cost_per_order", sa.Float, nullable=False, server_default="20.0"),
        sa.Column("alert_max_order_cancellation_rate", sa.Float, nullable=False, server_default="10.0"),
        sa.Column("alert_min_on_time_delivery_rate", sa.Float, nullable=False, server_default="80.0"),
        sa.Column("alert_max_cart_abandonment_rate", sa.Float, nullable=False, server_default="70.0"),
        sa.Column("daily_admin_report_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("daily_admin_report_email", sa.String(255), nullable=True),
        sa.Column("weekly_insight_digest_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("weekly_insight_digest_email", sa.String(255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("automation_settings")
