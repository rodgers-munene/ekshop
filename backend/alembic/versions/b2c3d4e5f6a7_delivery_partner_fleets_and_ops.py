"""delivery: partner fleets, cold chain, multi-stop, safety, fraud, SLA, loyalty

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-30 22:40:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- deliveries: photo proof, OTP, insurance -------------------------------
    op.add_column("deliveries", sa.Column("picked_photo_url", sa.String(500), nullable=True))
    op.add_column("deliveries", sa.Column("delivered_photo_url", sa.String(500), nullable=True))
    op.add_column("deliveries", sa.Column("otp_code", sa.String(6), nullable=True))
    op.add_column("deliveries", sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deliveries", sa.Column("otp_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deliveries", sa.Column("insurance_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("deliveries", sa.Column("insurance_value", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("deliveries", sa.Column("insurance_premium", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("deliveries", sa.Column("insurance_provider", sa.String(100), nullable=True))
    op.add_column("deliveries", sa.Column("insurance_policy_number", sa.String(100), nullable=True))
    op.add_column("deliveries", sa.Column("batch_id", UUID(as_uuid=True), nullable=True))

    # ---- multi-stop deliveries --------------------------------------------------
    op.create_table(
        "delivery_stops",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("address", JSONB(), nullable=False),
        sa.Column("contact_name", sa.String(100), nullable=False),
        sa.Column("contact_phone", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("estimated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("otp_code", sa.String(6), nullable=True),
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("otp_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("delivery_id", "sequence", name="uq_delivery_stop_sequence"),
    )

    # ---- batch dispatch ---------------------------------------------------------
    op.create_table(
        "delivery_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("pickup_lat", sa.Float(), nullable=True),
        sa.Column("pickup_lng", sa.Float(), nullable=True),
        sa.Column("pickup_address", sa.Text(), nullable=True),
        sa.Column("total_distance_km", sa.Float(), nullable=True),
        sa.Column("estimated_duration_min", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("picked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # deliveries.batch_id can only reference delivery_batches once it exists.
    op.create_foreign_key(
        "fk_deliveries_batch_id", "deliveries", "delivery_batches", ["batch_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_deliveries_batch_id", "deliveries", ["batch_id"])

    # ---- rider safety toolkit ---------------------------------------------------
    op.create_table(
        "safety_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("alert_metadata", JSONB(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_safety_alerts_agent_id", "safety_alerts", ["agent_id"])

    op.create_table(
        "emergency_contacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("contact_relationship", sa.String(50), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_emergency_contacts_agent_id", "emergency_contacts", ["agent_id"])

    op.create_table(
        "trip_shares",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("viewed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token", name="uq_trip_shares_token"),
    )
    op.create_index("ix_trip_shares_token", "trip_shares", ["token"])

    # ---- GPS fraud detection ----------------------------------------------------
    op.create_table(
        "gps_fraud_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fraud_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("speed_kmh", sa.Float(), nullable=True),
        sa.Column("heading", sa.Float(), nullable=True),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("expected_lat", sa.Float(), nullable=True),
        sa.Column("expected_lng", sa.Float(), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("time_delta_sec", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence", JSONB(), nullable=True),
        sa.Column("is_reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.String(50), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_gps_fraud_alerts_agent_id", "gps_fraud_alerts", ["agent_id"])

    # ---- SLA, dispatch audit, zones ---------------------------------------------
    op.create_table(
        "sla_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("max_dispatch_time_min", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_pickup_time_min", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("max_delivery_time_min", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("max_total_time_min", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_sla_configs_name"),
    )

    op.create_table(
        "sla_breaches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("breach_type", sa.String(50), nullable=False),
        sa.Column("expected_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("breach_minutes", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("is_alerted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sla_breaches_delivery_id", "sla_breaches", ["delivery_id"])

    op.create_table(
        "dispatcher_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("dispatcher_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("previous_agent_id", UUID(as_uuid=True), nullable=True),
        sa.Column("details", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "zone_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("boundary", JSONB(), nullable=False),
        sa.Column("center_lat", sa.Float(), nullable=True),
        sa.Column("center_lng", sa.Float(), nullable=True),
        sa.Column("radius_km", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "agent_zone_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_id", UUID(as_uuid=True), sa.ForeignKey("zone_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("assigned_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("agent_id", "zone_id", name="uq_agent_zone_assignment"),
    )

    # ---- cold chain / vehicle requirements -------------------------------------
    # vehicle_type is a native_enum=False String on delivery_agents, so the two
    # new refrigerated values need no schema change; the constraints live here.
    op.create_table(
        "vehicle_requirements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("required_vehicle_type", sa.String(30), nullable=False),
        sa.Column("temperature_requirement", sa.String(20), nullable=False, server_default="ambient"),
        sa.Column("min_capacity_kg", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_capacity_liters", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requires_license", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("license_type", sa.String(50), nullable=True),
        sa.Column("special_features", JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_vehicle_requirements_name"),
    )

    # ---- rider loyalty / quests -------------------------------------------------
    op.add_column("delivery_agents", sa.Column("tier", sa.String(20), nullable=False, server_default="bronze"))
    op.add_column("delivery_agents", sa.Column("loyalty_points", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("delivery_agents", sa.Column("lifetime_deliveries", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("delivery_agents", sa.Column("lifetime_earnings", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("delivery_agents", sa.Column("current_streak_days", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("delivery_agents", sa.Column("longest_streak_days", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("delivery_agents", sa.Column("last_active_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("delivery_agents", sa.Column("total_distance_km", sa.Float(), nullable=False, server_default="0"))

    op.create_table(
        "quests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quest_type", sa.String(40), nullable=False),
        sa.Column("target_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("reward_type", sa.String(30), nullable=False),
        sa.Column("reward_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("reward_badge", sa.String(100), nullable=True),
        sa.Column("tier_requirement", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recurrence_period", sa.String(20), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "quest_progress",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quest_id", UUID(as_uuid=True), sa.ForeignKey("quests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("current_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("agent_id", "quest_id", name="uq_quest_progress_agent_quest"),
    )

    # ---- insurance claims -------------------------------------------------------
    op.create_table(
        "insurance_claims",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claimant_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="filed"),
        sa.Column("claimed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("approved_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence", JSONB(), nullable=True),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_insurance_claims_delivery_id", "insurance_claims", ["delivery_id"])

    # ---- partner fleets (3PL) ---------------------------------------------------
    op.create_table(
        "partner_fleets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(150), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("api_base_url", sa.String(500), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("webhook_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("auth_header_name", sa.String(100), nullable=False, server_default="Authorization"),
        sa.Column("auth_header_prefix", sa.String(20), nullable=False, server_default="Bearer"),
        sa.Column("supports_webhooks", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("base_pickup_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("per_km_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("per_kg_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("coverage_counties", JSONB(), nullable=True),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_pickup_minutes", sa.Float(), nullable=True),
        sa.Column("avg_delivery_minutes", sa.Float(), nullable=True),
        sa.Column("total_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_partner_fleets_name"),
        sa.UniqueConstraint("slug", name="uq_partner_fleets_slug"),
    )

    op.create_table(
        "partner_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("partner_id", UUID(as_uuid=True), sa.ForeignKey("partner_fleets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_reference", sa.String(150), nullable=True),
        sa.Column("partner_job_id", sa.String(150), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("fulfillment_mode", sa.String(20), nullable=False, server_default="same_city"),
        sa.Column("pickup_address", JSONB(), nullable=False),
        sa.Column("pickup_lat", sa.Float(), nullable=True),
        sa.Column("pickup_lng", sa.Float(), nullable=True),
        sa.Column("drop_address", JSONB(), nullable=False),
        sa.Column("drop_lat", sa.Float(), nullable=True),
        sa.Column("drop_lng", sa.Float(), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("weight_kg", sa.Numeric(10, 2), nullable=True),
        sa.Column("quoted_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("partner_reported_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("driver_name", sa.String(150), nullable=True),
        sa.Column("driver_phone", sa.String(20), nullable=True),
        sa.Column("vehicle_plate", sa.String(50), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("partner_raw_response", JSONB(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("in_transit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("external_reference", name="uq_partner_jobs_external_reference"),
    )
    op.create_index("ix_partner_jobs_partner_id", "partner_jobs", ["partner_id"])
    op.create_index("ix_partner_jobs_partner_status", "partner_jobs", ["partner_id", "status"])
    op.create_index("ix_partner_jobs_delivery_id", "partner_jobs", ["delivery_id"])
    op.create_index("ix_partner_jobs_partner_job_id", "partner_jobs", ["partner_job_id"])

    op.create_table(
        "partner_webhook_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("partner_id", UUID(as_uuid=True), sa.ForeignKey("partner_fleets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("partner_job_id", sa.String(150), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("partner_event_id", sa.String(150), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("partner_id", "partner_event_id", name="uq_partner_webhook_event"),
    )
    op.create_index("ix_partner_webhook_events_partner_id", "partner_webhook_events", ["partner_id"])
    op.create_index("ix_partner_webhook_events_job_id", "partner_webhook_events", ["partner_job_id"])


def downgrade() -> None:
    op.drop_table("partner_webhook_events")
    op.drop_table("partner_jobs")
    op.drop_table("partner_fleets")
    op.drop_index("ix_insurance_claims_delivery_id", table_name="insurance_claims")
    op.drop_table("insurance_claims")
    op.drop_table("quest_progress")
    op.drop_table("quests")
    for column in (
        "tier", "loyalty_points", "lifetime_deliveries", "lifetime_earnings",
        "current_streak_days", "longest_streak_days", "last_active_date", "total_distance_km",
    ):
        op.drop_column("delivery_agents", column)
    op.drop_table("vehicle_requirements")
    op.drop_table("agent_zone_assignments")
    op.drop_table("zone_configs")
    op.drop_table("dispatcher_logs")
    op.drop_index("ix_sla_breaches_delivery_id", table_name="sla_breaches")
    op.drop_table("sla_breaches")
    op.drop_table("sla_configs")
    op.drop_index("ix_gps_fraud_alerts_agent_id", table_name="gps_fraud_alerts")
    op.drop_table("gps_fraud_alerts")
    op.drop_index("ix_trip_shares_token", table_name="trip_shares")
    op.drop_table("trip_shares")
    op.drop_index("ix_emergency_contacts_agent_id", table_name="emergency_contacts")
    op.drop_table("emergency_contacts")
    op.drop_index("ix_safety_alerts_agent_id", table_name="safety_alerts")
    op.drop_table("safety_alerts")
    # Unhook deliveries.batch_id before dropping the table it points at.
    op.drop_index("ix_deliveries_batch_id", table_name="deliveries")
    op.drop_constraint("fk_deliveries_batch_id", "deliveries", type_="foreignkey")
    op.drop_column("deliveries", "batch_id")
    op.drop_table("delivery_batches")
    op.drop_table("delivery_stops")
    for column in (
        "insurance_enabled", "insurance_value", "insurance_premium",
        "insurance_provider", "insurance_policy_number",
        "otp_code", "otp_expires_at", "otp_verified_at",
        "picked_photo_url", "delivered_photo_url",
    ):
        op.drop_column("deliveries", column)