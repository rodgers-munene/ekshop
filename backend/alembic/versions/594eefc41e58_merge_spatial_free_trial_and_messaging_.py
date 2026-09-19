"""merge spatial, free-trial, and messaging branches

Revision ID: 594eefc41e58
Revises: e2f7a9c4b6d8, f5a6b7c8d9e0, h7i8j9k0l1m2
Create Date: 2026-09-19 21:11:18.257941

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '594eefc41e58'
down_revision: Union[str, Sequence[str], None] = ('e2f7a9c4b6d8', 'f5a6b7c8d9e0', 'h7i8j9k0l1m2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
