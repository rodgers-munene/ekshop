"""store KYC documents as private keys, and split identity from equipment review

Two changes, both about not trusting the wrong thing:

1. `equipment_photo_url` becomes `equipment_photo_key`. KYC documents are
   national ID and licence scans; the old column name implied a URL, and every
   other upload in this codebase produces a *public* S3 URL. Storing a key
   instead means a view link is presigned on read and nothing is ever publicly
   reachable. A rename rather than add-and-drop, so any existing value survives.

2. Equipment review gets its own notes and timestamp. Approving a rider's ID
   used to also set `equipment_verified = true` in the same click, so a single
   action cleared both halves of the go-live gate and the admin could not tell
   which one they had actually judged.

`kyc_documents` keeps its JSONB shape but now holds `{type, key}`. Rows written
by the old code would hold `{type, url}`; the read path presigns `key` and falls
back to `url` when `key` is absent, so nothing that already exists breaks.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
"""

from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "delivery_agents",
        "equipment_photo_url",
        new_column_name="equipment_photo_key",
        existing_type=sa.String(500),
        existing_nullable=True,
    )
    op.add_column(
        "delivery_agents",
        sa.Column("equipment_review_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "delivery_agents",
        sa.Column("equipment_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("delivery_agents", "equipment_reviewed_at")
    op.drop_column("delivery_agents", "equipment_review_notes")
    op.alter_column(
        "delivery_agents",
        "equipment_photo_key",
        new_column_name="equipment_photo_url",
        existing_type=sa.String(500),
        existing_nullable=True,
    )