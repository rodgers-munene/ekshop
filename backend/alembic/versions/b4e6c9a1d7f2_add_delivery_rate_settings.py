"""add delivery_rate_settings table

Revision ID: b4e6c9a1d7f2
Revises: 9f2d4a6c1b8e
Create Date: 2026-08-03 00:00:00.000000

"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b4e6c9a1d7f2"
down_revision = "9f2d4a6c1b8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_rate_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("same_county_fee", sa.String(20), nullable=False, server_default="200.00"),
        sa.Column("same_region_fee", sa.String(20), nullable=False, server_default="350.00"),
        sa.Column("different_region_fee", sa.String(20), nullable=False, server_default="600.00"),
        sa.Column("unknown_origin_fee", sa.String(20), nullable=False, server_default="400.00"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    delivery_rate_settings = sa.table(
        "delivery_rate_settings",
        sa.column("id", postgresql.UUID(as_uuid=True)),
    )
    op.bulk_insert(delivery_rate_settings, [{"id": str(uuid.uuid4())}])


def downgrade() -> None:
    op.drop_table("delivery_rate_settings")
