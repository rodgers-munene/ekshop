"""add session_started_at to refresh_tokens"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k2l3m4n5o6p7"
down_revision: Union[str, None] = "7a8678777331"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Admin sessions are capped from the moment of login, and rotation issues a
    # new row every time, so the original login time has to be carried on the
    # row itself. Existing sessions (already logged in) get the migration time:
    # the most a live admin loses is one extra hour before re-authenticating.
    op.add_column(
        "refresh_tokens",
        sa.Column(
            "session_started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("refresh_tokens", "session_started_at")
