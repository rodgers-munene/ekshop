"""fix(fulfillment): make append-only deletion RESTRICT, add an ops escape hatch

Revision ID: f7a7b8c9d0e1f
Revises: f6a7b8c9d0e1
Create Date: 2026-10-01 01:05:00.000000

`d4e5f6a7b8c9` installed a trigger that raises on any UPDATE or DELETE of
`delivery_job_events`, and gave that table `ON DELETE CASCADE` from
`delivery_jobs`. Those two choices contradict each other: deleting a delivery
job cascades to its events, the trigger fires, and the whole statement fails.
The practical effect was that *no* job or fulfillment that had any history
could ever be deleted, and the error the operator saw blamed the trigger rather
than telling them the deletion was never allowed.

This revision:

1. Changes `delivery_job_events.job_id` to ON DELETE RESTRICT, so the schema
   states the real rule -- a job with a recorded history is not deletable --
   and Postgres reports it as a foreign key error naming the constraint.

2. Gives the trigger function an explicit escape hatch:
       SET LOCAL ekshop.allow_event_mutation = 'on';
   Anything that legitimately must erase history (a GDPR erasure request, an
   ops purge of test data) can set it for the transaction. It defaults to off,
   so the append-only guarantee still holds by default and an application bug
   cannot set it.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f7a7b8c9d0e1f"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "delivery_job_events_job_id_fkey",
        "delivery_job_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "delivery_job_events_job_id_fkey",
        "delivery_job_events",
        "delivery_jobs",
        ["job_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION ekshop_deny_job_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF current_setting('ekshop.allow_event_mutation', true) = 'on' THEN
                RETURN COALESCE(NEW, OLD);
            END IF;
            RAISE EXCEPTION
                'delivery_job_events is append-only; % is not permitted. '
                'Create a new event or a new delivery job instead. To erase '
                'history deliberately, run: SET LOCAL ekshop.allow_event_mutation = ''on'';',
                TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ekshop_deny_job_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'delivery_job_events is append-only; % is not permitted. '
                'Create a new event or a new delivery job instead.',
                TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.drop_constraint(
        "delivery_job_events_job_id_fkey",
        "delivery_job_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "delivery_job_events_job_id_fkey",
        "delivery_job_events",
        "delivery_jobs",
        ["job_id"],
        ["id"],
        ondelete="CASCADE",
    )