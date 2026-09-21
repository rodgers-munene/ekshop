"""make conversations.order_id nullable and add participants"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "h7i8j9k0l1m3"
down_revision: Union[str, None] = "h7i8j9k0l1m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("conversations", "order_id", existing_type=sa.UUID(), nullable=True)
    op.create_table(
        "conversation_participants",
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("agent_id", sa.UUID(), sa.ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("conversation_id", "user_id", "agent_id"),
    )


def downgrade() -> None:
    op.drop_table("conversation_participants")
    op.alter_column("conversations", "order_id", existing_type=sa.UUID(), nullable=False)
