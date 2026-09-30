"""fulfillment: core model, jobs, assignments, append-only events, settlement

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-30 23:40:00.000000

Builds the PRD's spine: one Fulfillment per order, many DeliveryJobs beneath
it, so a retry or return is a *new* job rather than an overwrite.

Two things are enforced at the database level rather than only in Python:

1. delivery_job_events is INSERT-ONLY. A rule is installed that raises on
   UPDATE or DELETE, so a stray application-side mutation fails loudly instead
   of quietly corrupting the record of what happened to a customer's order.
   The rule is a safety net, not a substitute for the service layer; the
   migration owner is the app role so an operator can still drop it in an
   emergency.

2. delivery_jobs.attempt is unique per fulfillment, so two jobs can never
   claim to be the same attempt.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fulfillments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("payer", sa.String(20), nullable=False, server_default="customer"),
        sa.Column("payer_split_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("self_rider_name", sa.String(150), nullable=True),
        sa.Column("self_rider_phone", sa.String(20), nullable=True),
        sa.Column("quoted_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # One fulfillment per order in v1.
        sa.UniqueConstraint("order_id", name="uq_fulfillments_order_id"),
    )
    op.create_index("ix_fulfillments_order_id", "fulfillments", ["order_id"])
    op.create_index("ix_fulfillments_mode", "fulfillments", ["mode"])

    op.create_table(
        "delivery_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "fulfillment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("fulfillments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_reference", sa.String(64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("job_type", sa.String(20), nullable=False, server_default="forward"),
        sa.Column("status", sa.String(30), nullable=False, server_default="created"),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("partner_job_id", UUID(as_uuid=True), sa.ForeignKey("partner_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pickup_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("pickup_lng", sa.Numeric(9, 6), nullable=True),
        sa.Column("drop_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("drop_lng", sa.Numeric(9, 6), nullable=True),
        sa.Column("distance_km", sa.Numeric(10, 2), nullable=True),
        sa.Column("quoted_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        # OTP is stored hashed only; the plaintext is never persisted.
        sa.Column("otp_hash", sa.String(128), nullable=True),
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("otp_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(50), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("dispatch_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("at_pickup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pickup_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("in_transit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Two jobs can never claim to be the same attempt.
        sa.UniqueConstraint("fulfillment_id", "attempt", name="uq_delivery_job_attempt"),
        sa.UniqueConstraint("fulfillment_id", "job_type", name="uq_delivery_job_type_per_fulfillment"),
        sa.UniqueConstraint("external_reference", name="uq_delivery_jobs_external_reference"),
        sa.CheckConstraint("distance_km IS NULL OR distance_km >= 0", name="ck_delivery_job_distance"),
    )
    op.create_index("ix_delivery_jobs_fulfillment_id", "delivery_jobs", ["fulfillment_id"])
    op.create_index("ix_delivery_jobs_status", "delivery_jobs", ["status"])
    op.create_index("ix_delivery_jobs_agent_id", "delivery_jobs", ["agent_id"])

    op.create_table(
        "delivery_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("delivery_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("wave", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("payout_estimate", sa.Numeric(12, 2), nullable=True),
        sa.Column("distance_km", sa.Numeric(10, 2), nullable=True),
        sa.Column("offered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # Re-offering the same rider after a decline must be a new row.
        sa.UniqueConstraint("job_id", "agent_id", "wave", name="uq_delivery_assignment_attempt"),
    )
    op.create_index("ix_delivery_assignments_job_id", "delivery_assignments", ["job_id"])
    op.create_index("ix_delivery_assignments_agent_id", "delivery_assignments", ["agent_id"])

    op.create_table(
        "delivery_job_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("delivery_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("to_status", sa.String(30), nullable=True),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_role", sa.String(30), nullable=True),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_delivery_job_events_job_id", "delivery_job_events", ["job_id"])

    # --- append-only enforcement (PRD 7.2) -------------------------------------
    # An application bug that rewrites history should fail at the database, not
    # silently corrupt the record of what happened to a customer's order.
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
    op.execute(
        """
        CREATE TRIGGER trg_delivery_job_events_append_only
        BEFORE UPDATE OR DELETE ON delivery_job_events
        FOR EACH ROW EXECUTE FUNCTION ekshop_deny_job_event_mutation();
        """
    )

    # --- settlement -------------------------------------------------------------
    op.create_table(
        "job_settlements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("delivery_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fee_collected", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("rider_payout", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("incentive_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("payment_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("partner_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("waiting_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("contribution", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", name="uq_job_settlements_job_id"),
    )

    op.create_table(
        "fulfillment_settlements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "fulfillment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("fulfillments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("delivery_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fee_collected", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("rider_payout", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("incentive_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("payment_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("partner_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("waiting_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        # Denormalised so the margin calculator's Zone Summary is a plain SUM.
        sa.Column("contribution", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("margin_pct", sa.Numeric(6, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("fulfillment_id", name="uq_fulfillment_settlements_fulfillment_id"),
    )


def downgrade() -> None:
    op.drop_table("fulfillment_settlements")
    op.drop_table("job_settlements")
    op.execute("DROP TRIGGER IF EXISTS trg_delivery_job_events_append_only ON delivery_job_events;")
    op.execute("DROP FUNCTION IF EXISTS ekshop_deny_job_event_mutation();")
    op.drop_index("ix_delivery_job_events_job_id", table_name="delivery_job_events")
    op.drop_table("delivery_job_events")
    op.drop_index("ix_delivery_assignments_agent_id", table_name="delivery_assignments")
    op.drop_index("ix_delivery_assignments_job_id", table_name="delivery_assignments")
    op.drop_table("delivery_assignments")
    op.drop_index("ix_delivery_jobs_agent_id", table_name="delivery_jobs")
    op.drop_index("ix_delivery_jobs_status", table_name="delivery_jobs")
    op.drop_index("ix_delivery_jobs_fulfillment_id", table_name="delivery_jobs")
    op.drop_table("delivery_jobs")
    op.drop_index("ix_fulfillments_mode", table_name="fulfillments")
    op.drop_index("ix_fulfillments_order_id", table_name="fulfillments")
    op.drop_table("fulfillments")