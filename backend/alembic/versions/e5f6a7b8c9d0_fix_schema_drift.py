"""fix(drift): create 4 unmigrated tables and 18 unmigrated columns

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-01 00:15:00.000000

An audit comparing every mapped model's columns against the live database found
schema drift from already-shipped features. The model code was committed but the
matching Alembic revisions were not, so these tables/columns do not exist in any
deployed database. Any code path touching them raises
`UndefinedColumn`/`UndefinedTable` at runtime.

Missing tables:
    tax_configs        - Kenconfig for the VAT engine (commit 0c8e2ee)
    return_requests    - returns/RMA (commit 012a7d8)
    return_items
    delivery_issues    - rider-reported delivery problems

Missing columns:
    orders.tax_amount, order_groups.tax_amount, order_items.tax_amount/tax_rate
    order_groups.{scheduled_at, delivery_instructions, call_on_arrival,
                  leave_at_door, require_signature}
    user_addresses.{delivery_instructions, call_on_arrival, leave_at_door,
                    require_signature}
    shops.{prep_time_minutes, max_prep_time_minutes}
    products.reserved_qty, product_variants.reserved_qty
    messages.sender_type

Every NOT NULL column is added as nullable with a server default, backfilled,
and only then tightened. That keeps the revision correct on a populated
production database, not just on the empty local one. Money columns follow the
existing VARCHAR(20) convention used by orders.subtotal/total.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_bool_flags(table: str, columns: Sequence[str]) -> None:
    for col in columns:
        op.add_column(
            table,
            sa.Column(col, sa.Boolean(), nullable=True, server_default=sa.false()),
        )
        op.alter_column(table, col, nullable=False, server_default=sa.false())


def upgrade() -> None:
    # --- tax: orders / order_groups / order_items ---------------------------
    for table in ("orders", "order_groups", "order_items"):
        op.add_column(
            table,
            sa.Column("tax_amount", sa.String(20), nullable=True, server_default="0.00"),
        )
        op.alter_column(table, "tax_amount", nullable=False, server_default="0.00")
        op.create_check_constraint(
            f"ck_{table}_tax_amount_non_negative", table, "tax_amount::numeric >= 0"
        )

    op.add_column(
        "order_items",
        sa.Column("tax_rate", sa.Float(), nullable=True, server_default="0.0"),
    )
    op.alter_column("order_items", "tax_rate", nullable=False, server_default="0.0")
    op.create_check_constraint(
        "ck_order_items_tax_rate_range", "order_items", "tax_rate >= 0 AND tax_rate <= 1"
    )

    # --- scheduled delivery + delivery instructions on the order group -------
    op.add_column("order_groups", sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("order_groups", sa.Column("delivery_instructions", sa.Text(), nullable=True))
    _add_bool_flags(
        "order_groups",
        ["call_on_arrival", "leave_at_door", "require_signature"],
    )

    # --- the same preferences on a saved buyer address -----------------------
    op.add_column("user_addresses", sa.Column("delivery_instructions", sa.Text(), nullable=True))
    _add_bool_flags(
        "user_addresses",
        ["call_on_arrival", "leave_at_door", "require_signature"],
    )

    # --- prep time (commit 3b11d67) -----------------------------------------
    op.add_column(
        "shops",
        sa.Column("prep_time_minutes", sa.Integer(), nullable=True, server_default="30"),
    )
    op.alter_column(
        "shops", "prep_time_minutes", nullable=False, server_default="30"
    )
    op.add_column(
        "shops",
        sa.Column("max_prep_time_minutes", sa.Integer(), nullable=True, server_default="60"),
    )
    op.alter_column(
        "shops", "max_prep_time_minutes", nullable=False, server_default="60"
    )
    op.create_check_constraint("ck_shops_prep_time_positive", "shops", "prep_time_minutes > 0")
    op.create_check_constraint(
        "ck_shops_max_prep_time_positive", "shops", "max_prep_time_minutes > 0"
    )

    # --- inventory reservations (commit c7f4170) ----------------------------
    for table in ("products", "product_variants"):
        op.add_column(
            table,
            sa.Column("reserved_qty", sa.Integer(), nullable=True, server_default="0"),
        )
        op.alter_column(table, "reserved_qty", nullable=False, server_default="0")
        op.create_check_constraint(f"ck_{table}_reserved_qty_non_negative", table, "reserved_qty >= 0")

    # --- messages.sender_type (commit 41411e0) ------------------------------
    # Added nullable first: existing rows must be backfilled from the sender's
    # user role before the column can be made NOT NULL. `users.role` uses
    # 'buyer'/'rider' where the message vocabulary uses 'customer'/'agent'.
    op.add_column("messages", sa.Column("sender_type", sa.String(30), nullable=True))
    op.execute(
        """
        UPDATE messages AS m
        SET sender_type = CASE u.role::text
            WHEN 'buyer'    THEN 'customer'
            WHEN 'customer' THEN 'customer'
            WHEN 'seller'   THEN 'seller'
            WHEN 'agent'    THEN 'agent'
            WHEN 'rider'    THEN 'agent'
            WHEN 'admin'    THEN 'admin'
            ELSE 'admin'
        END
        FROM users AS u
        WHERE u.id = m.sender_id
        """
    )
    # Messages with no sender are system messages; 'admin' is the system actor.
    op.execute("UPDATE messages SET sender_type = 'admin' WHERE sender_type IS NULL")
    op.alter_column("messages", "sender_type", nullable=False)
    op.create_check_constraint(
        "ck_messages_sender_type",
        "messages",
        "sender_type IN ('customer', 'seller', 'agent', 'admin')",
    )
    op.create_index("ix_messages_conversation_id_created_at", "messages", ["conversation_id", "created_at"])

    # --- tax_configs (commit 0c8e2ee) ---------------------------------------
    op.create_table(
        "tax_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("tax_type", sa.String(30), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("applies_to_shipping", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("country", sa.String(2), nullable=False, server_default="KE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_tax_configs_name"),
        sa.UniqueConstraint("tax_type", "country", name="uq_tax_config_type_country"),
    )

    # --- returns / RMA (commit 012a7d8) -------------------------------------
    op.create_table(
        "return_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("buyer_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="requested"),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("reason_detail", sa.Text(), nullable=True),
        sa.Column("refund_amount", sa.String(20), nullable=False, server_default="0.00"),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_return_requests_order_id", "return_requests", ["order_id"])
    op.create_index("ix_return_requests_buyer_id", "return_requests", ["buyer_id"])
    op.create_index("ix_return_requests_shop_id", "return_requests", ["shop_id"])
    op.create_index("ix_return_requests_status", "return_requests", ["status"])

    op.create_table(
        "return_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "return_request_id",
            UUID(as_uuid=True),
            sa.ForeignKey("return_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("order_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("refund_amount", sa.String(20), nullable=False, server_default="0.00"),
        sa.Column("condition", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_return_items_return_request_id", "return_items", ["return_request_id"])
    op.create_index("ix_return_items_order_item_id", "return_items", ["order_item_id"])
    op.create_check_constraint("ck_return_items_quantity_positive", "return_items", "quantity > 0")

    # --- delivery_issues -----------------------------------------------------
    op.create_table(
        "delivery_issues",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "delivery_id",
            UUID(as_uuid=True),
            sa.ForeignKey("deliveries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # Postgres does not index FK columns; without this a cascade delete from
    # `deliveries` has to scan the whole table.
    op.create_index("ix_delivery_issues_delivery_id", "delivery_issues", ["delivery_id"])


def downgrade() -> None:
    op.drop_index("ix_delivery_issues_delivery_id", table_name="delivery_issues")
    op.drop_table("delivery_issues")

    op.drop_index("ix_return_items_order_item_id", table_name="return_items")
    op.drop_index("ix_return_items_return_request_id", table_name="return_items")
    op.drop_table("return_items")

    op.drop_index("ix_return_requests_status", table_name="return_requests")
    op.drop_index("ix_return_requests_shop_id", table_name="return_requests")
    op.drop_index("ix_return_requests_buyer_id", table_name="return_requests")
    op.drop_index("ix_return_requests_order_id", table_name="return_requests")
    op.drop_table("return_requests")

    op.drop_table("tax_configs")

    op.drop_index("ix_messages_conversation_id_created_at", table_name="messages")
    op.drop_constraint("ck_messages_sender_type", "messages", type_="check")
    op.drop_column("messages", "sender_type")

    for table in ("products", "product_variants"):
        op.drop_constraint(f"ck_{table}_reserved_qty_non_negative", table, type_="check")
        op.drop_column(table, "reserved_qty")

    op.drop_constraint("ck_shops_max_prep_time_positive", "shops", type_="check")
    op.drop_constraint("ck_shops_prep_time_positive", "shops", type_="check")
    op.drop_column("shops", "max_prep_time_minutes")
    op.drop_column("shops", "prep_time_minutes")

    for col in ("call_on_arrival", "leave_at_door", "require_signature"):
        op.drop_column("user_addresses", col)
    op.drop_column("user_addresses", "delivery_instructions")

    for col in ("call_on_arrival", "leave_at_door", "require_signature"):
        op.drop_column("order_groups", col)
    op.drop_column("order_groups", "delivery_instructions")
    op.drop_column("order_groups", "scheduled_at")

    op.drop_constraint("ck_order_items_tax_rate_range", "order_items", type_="check")
    op.drop_column("order_items", "tax_rate")
    for table in ("orders", "order_groups", "order_items"):
        op.drop_constraint(f"ck_{table}_tax_amount_non_negative", table, type_="check")
        op.drop_column(table, "tax_amount")