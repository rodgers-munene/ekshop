"""fix messaging: nullable conversation columns, participant ids, agent senders

h7i8j9k0l1m3 gave conversation_participants a composite primary key over
(conversation_id, user_id, agent_id), which makes all three NOT NULL, so no
participant row (a user OR an agent) could ever be inserted. It also left
conversations.buyer_id/shop_id/last_message_at NOT NULL and kept the
one-conversation-per-buyer-and-shop constraint, which block the new
admin/agent/order conversations.

This revision:
- relaxes those conversation columns and swaps the buyer/shop unique
  constraint for partial unique indexes (one shop chat per buyer and shop,
  one chat per order);
- gives participants a surrogate id, with exactly one of user_id/agent_id set;
- adds messages.sender_agent_id, since messages.sender_id points at users;
- backfills participants for the buyer-seller chats that already exist, so
  they stay visible to both sides.

Revision ID: d8f2a6c4e1b9
Revises: c7e3f9a1d2b4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d8f2a6c4e1b9"
down_revision: Union[str, None] = "c7e3f9a1d2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("conversations", "buyer_id", nullable=True)
    op.alter_column("conversations", "shop_id", nullable=True)
    op.alter_column("conversations", "last_message_at", nullable=True)
    op.execute("ALTER TABLE conversations DROP CONSTRAINT IF EXISTS uq_conversation_buyer_shop")
    op.create_index(
        "uq_conversations_buyer_shop",
        "conversations",
        ["buyer_id", "shop_id"],
        unique=True,
        postgresql_where=sa.text("order_id IS NULL AND buyer_id IS NOT NULL AND shop_id IS NOT NULL"),
    )
    op.create_index(
        "uq_conversations_order",
        "conversations",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("order_id IS NOT NULL"),
    )

    op.drop_constraint("conversation_participants_pkey", "conversation_participants", type_="primary")
    op.add_column(
        "conversation_participants",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    )
    op.create_primary_key("conversation_participants_pkey", "conversation_participants", ["id"])
    op.alter_column("conversation_participants", "user_id", nullable=True)
    op.alter_column("conversation_participants", "agent_id", nullable=True)
    op.create_check_constraint(
        "ck_conversation_participants_one_actor",
        "conversation_participants",
        "(user_id IS NULL) <> (agent_id IS NULL)",
    )
    op.create_index(
        "uq_conversation_participants_user",
        "conversation_participants",
        ["conversation_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_conversation_participants_agent",
        "conversation_participants",
        ["conversation_id", "agent_id"],
        unique=True,
        postgresql_where=sa.text("agent_id IS NOT NULL"),
    )

    op.add_column(
        "messages",
        sa.Column(
            "sender_agent_id",
            sa.UUID(),
            sa.ForeignKey("delivery_agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Existing buyer-seller chats predate participants; add both sides.
    op.execute(
        """
        INSERT INTO conversation_participants (conversation_id, user_id, joined_at)
        SELECT c.id, c.buyer_id, COALESCE(c.last_message_at, c.created_at)
        FROM conversations c
        WHERE c.order_id IS NULL AND c.buyer_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO conversation_participants (conversation_id, user_id, joined_at)
        SELECT c.id, s.seller_id, COALESCE(c.last_message_at, c.created_at)
        FROM conversations c JOIN shops s ON s.id = c.shop_id
        WHERE c.order_id IS NULL AND s.seller_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Lossy: the old schema cannot hold agent messages, agent participants or
    # conversations without a buyer and shop, so those are removed.
    op.execute("DELETE FROM messages WHERE sender_agent_id IS NOT NULL")
    op.drop_column("messages", "sender_agent_id")

    op.execute("DELETE FROM conversation_participants")
    op.drop_index("uq_conversation_participants_agent", table_name="conversation_participants")
    op.drop_index("uq_conversation_participants_user", table_name="conversation_participants")
    op.drop_constraint("ck_conversation_participants_one_actor", "conversation_participants", type_="check")
    op.drop_constraint("conversation_participants_pkey", "conversation_participants", type_="primary")
    op.drop_column("conversation_participants", "id")
    op.alter_column("conversation_participants", "user_id", nullable=False)
    op.alter_column("conversation_participants", "agent_id", nullable=False)
    op.create_primary_key(
        "conversation_participants_pkey",
        "conversation_participants",
        ["conversation_id", "user_id", "agent_id"],
    )

    op.drop_index("uq_conversations_order", table_name="conversations")
    op.drop_index("uq_conversations_buyer_shop", table_name="conversations")
    op.execute("DELETE FROM conversations WHERE buyer_id IS NULL OR shop_id IS NULL OR order_id IS NOT NULL")
    op.execute("UPDATE conversations SET last_message_at = created_at WHERE last_message_at IS NULL")
    op.create_unique_constraint("uq_conversation_buyer_shop", "conversations", ["buyer_id", "shop_id"])
    op.alter_column("conversations", "last_message_at", nullable=False)
    op.alter_column("conversations", "shop_id", nullable=False)
    op.alter_column("conversations", "buyer_id", nullable=False)
