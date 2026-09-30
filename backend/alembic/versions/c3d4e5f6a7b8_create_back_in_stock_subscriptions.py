"""catalog: back-in-stock subscriptions (table was missing from migrations)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-30 23:05:00.000000

The BackInStockSubscription model was committed in e57ce75 but never had a
migration, so /products/{id}/back-in-stock 500'd with
'relation "back_in_stock_subscriptions" does not exist' in any deployed
database. This creates the table and also fixes two model bugs:

  * user_id was NOT NULL while the guest subscribe endpoint omits it, so a
    guest subscription raised a not-null violation on insert. It is now
    nullable, with a CHECK that a row still carries a recipient.
  * UNIQUE(user_id, product_id, variant_id) never fires when variant_id IS
    NULL (Postgres treats NULLs as distinct), so repeat subscriptions to the
    same product were silently allowed. Replaced with partial unique indexes
    over COALESCE(variant_id, '-') for both guest and logged-in rows.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "back_in_stock_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", UUID(as_uuid=True), sa.ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("is_notified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "user_id IS NOT NULL OR email IS NOT NULL",
            name="ck_back_in_stock_has_recipient",
        ),
    )
    # Partial unique indexes: dedupe works even when variant_id is NULL.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_back_in_stock_user_product
        ON back_in_stock_subscriptions
            (product_id, COALESCE(variant_id, '-'::uuid), user_id)
        WHERE user_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_back_in_stock_email_product
        ON back_in_stock_subscriptions
            (product_id, COALESCE(variant_id, '-'::uuid), email)
        WHERE user_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("uq_back_in_stock_email_product", table_name="back_in_stock_subscriptions")
    op.drop_index("uq_back_in_stock_user_product", table_name="back_in_stock_subscriptions")
    op.drop_table("back_in_stock_subscriptions")