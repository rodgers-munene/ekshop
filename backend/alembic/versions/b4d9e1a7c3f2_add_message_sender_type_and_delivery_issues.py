"""add messages.sender_type and the delivery_issues table

The messages table predates h7i8j9k0l1m2, which skipped it because it
already existed, so sender_type was never added. delivery_issues backs the
rider "report an issue" endpoint but had no migration.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b4d9e1a7c3f2"
down_revision: Union[str, None] = "7a8678777331"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if "sender_type" not in {c["name"] for c in inspector.get_columns("messages")}:
        op.add_column("messages", sa.Column("sender_type", sa.String(20), nullable=True))
        # Existing messages were all sent by users, so derive the role from the sender.
        op.execute(
            """
            UPDATE messages m
            SET sender_type = CASE u.role WHEN 'buyer' THEN 'customer' ELSE u.role END
            FROM users u
            WHERE m.sender_id = u.id
            """
        )
        op.execute("UPDATE messages SET sender_type = 'customer' WHERE sender_type IS NULL")
        op.alter_column("messages", "sender_type", nullable=False)

    if "delivery_issues" not in inspector.get_table_names():
        op.create_table(
            "delivery_issues",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("delivery_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("reason", sa.String(100), nullable=False),
            sa.Column("notes", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["delivery_id"], ["deliveries.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_delivery_issues_delivery_id", "delivery_issues", ["delivery_id"])


def downgrade() -> None:
    op.drop_index("ix_delivery_issues_delivery_id", table_name="delivery_issues")
    op.drop_table("delivery_issues")
    op.drop_column("messages", "sender_type")
