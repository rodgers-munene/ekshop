"""add order_notification_recipients table

Revision ID: d3f8a1c92e47
Revises: c7d1e8f4a3b6
Create Date: 2026-09-02 00:00:00.000000

"""
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d3f8a1c92e47"
down_revision = "c7d1e8f4a3b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_notification_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("order_notification_recipients")
