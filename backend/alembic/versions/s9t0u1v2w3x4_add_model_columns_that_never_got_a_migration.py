"""add the model columns that never got a migration

Revision ID: s9t0u1v2w3x4
Revises: m3n4o5p6q7r8
Create Date: 2026-10-18

Three columns exist on the models and in no migration at all. They were added
with feature work that was tested against SQLite, where pytest builds the schema
straight from the models, so nothing ever noticed that a database created by
alembic does not have them. Against PostgreSQL the symptom is a 500 on any
query that selects the whole row:

  * ``users.fcm_token`` -- every authenticated request, because reading a user
    loads every column. This is what blanked the new Market Expansion tab: the
    study itself needs no database, but the live coverage joined beside it runs
    through the admin session, which reads ``users``.
  * ``shops.is_platform_owned`` -- the hybrid 1P/3P flag, read by the sellers
    screen and the coverage query's shop listing.
  * ``orders.source`` -- whether an order was first-party or marketplace, read
    by order reporting.

Adding them here also closes the gap for any database created before the
columns existed. ``is_platform_owned`` and ``source`` are backfilled with the
value the application would have written anyway: not platform-owned, and
marketplace.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s9t0u1v2w3x4"
down_revision: Union[str, None] = "m3n4o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("fcm_token", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "shops",
        sa.Column(
            "is_platform_owned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "source",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'marketplace'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "source")
    op.drop_column("shops", "is_platform_owned")
    op.drop_column("users", "fcm_token")
