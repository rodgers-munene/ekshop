"""fix(fulfillment): allow many forward jobs per fulfillment

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-01 00:50:00.000000

Drops `uq_delivery_job_type_per_fulfillment`, a UNIQUE(fulfillment_id, job_type)
constraint created in d4e5f6a7b8c9. It was wrong: the whole point of the
fulfillment model is that a retry is a *new* forward job under the same
fulfillment, so the constraint made the second attempt impossible to insert
(`UniqueViolation` on (fulfillment_id, 'forward')) and silently defeated the
PRD's retry flow.

`uq_delivery_job_attempt` -- UNIQUE(fulfillment_id, attempt) -- is the guarantee
that actually matters, and it stays: two jobs can never claim to be the same
attempt number.

Adds a composite index on (fulfillment_id, job_type) to replace the uniqueness
constraint's usefulness for lookups such as "the return leg for this order".

The model in app/models/fulfillment.py already reflects the corrected shape; it
never declared this constraint once the retry test failed.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_delivery_job_type_per_fulfillment",
        "delivery_jobs",
        type_="unique",
    )
    op.create_index(
        "ix_delivery_jobs_fulfillment_id_job_type",
        "delivery_jobs",
        ["fulfillment_id", "job_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_jobs_fulfillment_id_job_type", table_name="delivery_jobs")
    # Only safe if no fulfillment actually has two forward jobs. Restoring the
    # constraint on a database that contains retries will fail loudly, which is
    # the correct outcome: the old schema could not represent retries at all.
    op.create_unique_constraint(
        "uq_delivery_job_type_per_fulfillment",
        "delivery_jobs",
        ["fulfillment_id", "job_type"],
    )