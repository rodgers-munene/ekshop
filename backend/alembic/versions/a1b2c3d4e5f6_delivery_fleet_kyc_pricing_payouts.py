"""delivery fleet: KYC, ping offers, pricing rules, wallet ledger

Revision ID: a1b2c3d4e5f6
Revises: 7a8678777331
Create Date: 2026-09-29 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7a8678777331"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── delivery_agents: KYC, vehicle, and wallet ──────────────────────────
    op.add_column("delivery_agents", sa.Column("vehicle_type", sa.String(20), nullable=True))
    op.add_column("delivery_agents", sa.Column("national_id_number", sa.String(50), nullable=True))
    op.add_column("delivery_agents", sa.Column("license_number", sa.String(50), nullable=True))
    op.add_column("delivery_agents", sa.Column("kyc_status", sa.String(20), nullable=False, server_default="pending_review"))
    op.add_column("delivery_agents", sa.Column("kyc_documents", JSONB(), nullable=True))
    op.add_column("delivery_agents", sa.Column("equipment_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("delivery_agents", sa.Column("equipment_photo_url", sa.String(500), nullable=True))
    op.add_column("delivery_agents", sa.Column("kyc_submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("delivery_agents", sa.Column("kyc_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("delivery_agents", sa.Column("kyc_review_notes", sa.Text(), nullable=True))
    op.add_column("delivery_agents", sa.Column("wallet_balance", sa.Numeric(14, 2), nullable=False, server_default="0.00"))

    # ── delivery_offers: the sequential ping queue ─────────────────────────
    op.create_table(
        "delivery_offers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("queue_position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_offers_agent_status", "delivery_offers", ["agent_id", "status"])
    op.create_index("ix_offers_delivery_status", "delivery_offers", ["delivery_id", "status"])

    # ── delivery_pricing_rules: metered distance/time + surge pricing ──────
    op.create_table(
        "delivery_pricing_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("vehicle_type", sa.String(20), nullable=False, unique=True),
        sa.Column("base_fare", sa.Numeric(10, 2), nullable=False),
        sa.Column("per_km_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("per_minute_rate", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("rain_multiplier", sa.Numeric(4, 2), nullable=False, server_default="1.00"),
        sa.Column("peak_hours_multiplier", sa.Numeric(4, 2), nullable=False, server_default="1.00"),
        sa.Column("supply_demand_multiplier", sa.Numeric(4, 2), nullable=False, server_default="1.00"),
        sa.Column("max_surge_cap", sa.Numeric(4, 2), nullable=False, server_default="2.00"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # ── delivery_ledger_entries: rider earnings + B2C payout trail ─────────
    op.create_table(
        "delivery_ledger_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("delivery_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("delivery_id", UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entry_type", sa.String(20), nullable=False),  # earning | b2c_payout | reversal | adjustment
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),  # signed: +credit, -debit
        sa.Column("balance_after", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),    # M-Pesa OriginatorConversationID / receipt
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ledger_agent", "delivery_ledger_entries", ["agent_id", "created_at"])
    op.create_index("ix_ledger_delivery", "delivery_ledger_entries", ["delivery_id"])

    # ── seed default pricing rules for the three launch vehicle classes ────
    op.execute(
        """
        INSERT INTO delivery_pricing_rules
            (id, vehicle_type, base_fare, per_km_rate, per_minute_rate,
             rain_multiplier, peak_hours_multiplier, supply_demand_multiplier,
             max_surge_cap, currency, is_active)
        VALUES
            ('00000000-0000-0000-0000-000000000001', 'bicycle',    50.00, 15.00, 1.00, 1.30, 1.20, 1.00, 2.00, 'KES', true),
            ('00000000-0000-0000-0000-000000000002', 'motorcycle', 100.00, 35.00, 2.50, 1.50, 1.40, 1.00, 2.00, 'KES', true),
            ('00000000-0000-0000-0000-000000000003', 'pickup_van', 250.00, 60.00, 4.00, 1.50, 1.40, 1.00, 2.00, 'KES', true)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_ledger_delivery", table_name="delivery_ledger_entries")
    op.drop_index("ix_ledger_agent", table_name="delivery_ledger_entries")
    op.drop_table("delivery_ledger_entries")
    op.drop_table("delivery_pricing_rules")
    op.drop_index("ix_offers_delivery_status", table_name="delivery_offers")
    op.drop_index("ix_offers_agent_status", table_name="delivery_offers")
    op.drop_table("delivery_offers")

    op.drop_column("delivery_agents", "wallet_balance")
    op.drop_column("delivery_agents", "kyc_review_notes")
    op.drop_column("delivery_agents", "kyc_reviewed_at")
    op.drop_column("delivery_agents", "kyc_submitted_at")
    op.drop_column("delivery_agents", "equipment_photo_url")
    op.drop_column("delivery_agents", "equipment_verified")
    op.drop_column("delivery_agents", "kyc_documents")
    op.drop_column("delivery_agents", "kyc_status")
    op.drop_column("delivery_agents", "license_number")
    op.drop_column("delivery_agents", "national_id_number")
    op.drop_column("delivery_agents", "vehicle_type")