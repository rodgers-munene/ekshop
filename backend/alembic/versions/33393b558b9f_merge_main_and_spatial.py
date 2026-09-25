"""merge main and spatial

Revision ID: 33393b558b9f
Revises: c9e2a4f17b53, d8f2a6c4e1b9
Create Date: 2026-09-25 16:09:10.134643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33393b558b9f'
down_revision: Union[str, Sequence[str], None] = ('c9e2a4f17b53', 'd8f2a6c4e1b9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
