"""add authorization_code to subscriptions"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "i9j0k1l2m3n5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("authorization_code", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("subscriptions", "authorization_code")
