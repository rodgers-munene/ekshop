"""make conversations general-purpose and add participants

The existing conversations table was created by the base schema with
buyer_id/shop_id/last_message_at. This migration adds order_id and
created_at, plus the conversation_participants join table.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "h7i8j9k0l1m3"
down_revision: Union[str, None] = "h7i8j9k0l1m4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("conversations")}

    if "order_id" not in existing_cols:
        op.add_column("conversations", sa.Column("order_id", sa.UUID(), nullable=True))
        op.create_index("ix_conversations_order_id", "conversations", ["order_id"])

    if "created_at" not in existing_cols:
        op.add_column("conversations", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    if "conversation_participants" not in inspector.get_table_names():
        op.create_table(
            "conversation_participants",
            sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=True),
            sa.Column("agent_id", sa.UUID(), sa.ForeignKey("delivery_agents.id", ondelete="CASCADE"), primary_key=True, nullable=True),
            sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "conversation_participants" in inspector.get_table_names():
        op.drop_table("conversation_participants")

    existing_cols = {c["name"] for c in inspector.get_columns("conversations")}
    if "created_at" in existing_cols:
        op.drop_column("conversations", "created_at")
    if "order_id" in existing_cols:
        op.drop_index("ix_conversations_order_id", "conversations")
        op.drop_column("conversations", "order_id")
