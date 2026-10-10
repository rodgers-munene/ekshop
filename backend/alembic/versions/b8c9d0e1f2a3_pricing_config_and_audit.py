"""fix(config): admin-editable pricing parameters and the pricing audit record

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-01 03:40:00.000000

Two of the four specification "BUILD NOW" items that were still missing
(18): admin-configurable parameters, and pricing versioning with an audit
record.

pricing_parameters
------------------
 15 requires every rate to be editable "without a code deployment". Storing them
as a name/value table means an admin change takes effect immediately and is
itself auditable, instead of living in a dataclass default that only a developer
can change. Seeded with the 5/6/8/A.7/A.8 MVP values so the engine and the
database agree from the first request.

pricing_calculations
-------------------
 17 requires every calculation to be stored with ~25 fields and states:
"Historical orders retain their original calculation -- never recalculate
historical economics with current rules." This is a separate append-only table
rather than more columns on the fulfillment, because one order may be priced
several times: a quote at checkout, a re-quote at dispatch, and again for each
retry.

The two distance legs, the distance source and the approximate flag are stored
so that  3.2 compliance is verifiable after the fact: a price built on
straight-line distance can be identified years later.

Append-only, like delivery_job_events, so the audit trail cannot be quietly
edited. It is RESTRICT rather than CASCADE for the same reason: an audit record
that vanishes with its parent is not an audit record. The escape hatch is
`SET LOCAL ekshop.allow_event_mutation = 'on'`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pricing_parameters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("value", sa.String(80), nullable=False),
        # 'money' | 'rate' | 'integer' | 'boolean' | 'json'. Stored so the admin
        # API can validate a change before saving it rather than after.
        sa.Column("value_type", sa.String(20), nullable=False, server_default="money"),
        sa.Column("description", sa.Text(), nullable=True),
        # Which specification section this comes from, so an admin can see why a
        # value is what it is without reading the document.
        sa.Column("spec_reference", sa.String(20), nullable=True),
        # Q23. The one decision that changes the economics rather than a rate.
        sa.Column("is_commercial_decision", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("updated_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_pricing_parameters_key"),
    )
    op.create_check_constraint(
        "ck_pricing_parameters_value_type",
        "pricing_parameters",
        "value_type IN ('money','rate','integer','boolean','json')",
    )

    # Seeded from the specification's MVP tables so a fresh database and the
    # engine's dataclass defaults cannot drift apart silently.
    seed = [
        ("base_fare", "80", "money", "Customer base fare", " 5", False),
        ("customer_distance_rate", "25", "money", "Per km, on merchant->customer", " 5", False),
        ("minimum_delivery_fare", "120", "money", "Floor for the customer price", " 5", False),
        ("rider_base_fare", "60", "money", "Rider base payout", " 6", False),
        ("rider_distance_rate", "15", "money", "Rider per km, on the FULL movement", " 6", False),
        ("minimum_rider_payout", "100", "money", "Floor for the rider payout", " 6", False),
        ("waiting_grace_minutes", "5", "integer", "Waiting before it is payable", " 6", False),
        ("waiting_rate_per_minute", "2", "money", "Rider pay per chargeable minute", " 6", False),
        ("manual_quote_above_kg", "20", "integer", "Above this weight, no formula exists", " 7", False),
        ("customer_surge_cap", "1.30", "rate", "The customer never sees more than this", " 8/D#1", False),
        ("max_customer_price", "500", "money", "Above this, surge becomes a rider incentive", "D#1", False),
        ("service_multiplier_standard", "1.00", "rate", "STANDARD service level", "A.7", False),
        ("service_multiplier_priority", "1.15", "rate", "PRIORITY service level", "A.7", False),
        ("service_multiplier_express", "1.30", "rate", "EXPRESS service level", "A.7", False),
        ("target_contribution", "0.15", "rate", "Margin rate a healthy delivery earns", " 12/A.8", True),
        # D#8: "seed with measured payment-processor rate". The 1.5% here is the
        # placeholder the questionnaire flags as unverified.
        ("payment_cost_rate", "0.015", "rate", "PLACEHOLDER - measure the real processor rate (D#8)", " 12/D#8", True),
        ("failure_probability", "0.08", "rate", "PLACEHOLDER - start from observed data per zone (D#8)", " 12/B.4", True),
        ("average_failure_cost", "250", "money", "PLACEHOLDER - start from observed data per zone (D#8)", " 12/B.4", True),
        # Q23. Defaults to off, i.e. the specification exactly as written, which
        # the questionnaire shows loses money under ~4 km.
        ("charge_rider_detour_to_customer", "false", "boolean",
         "Q23: charge the customer for the rider's trip to the merchant too", " 4/Q23", True),
    ]
    for key, value, value_type, description, spec, commercial in seed:
        op.execute(
            sa.text(
                "INSERT INTO pricing_parameters (id, key, value, value_type, description, "
                "spec_reference, is_commercial_decision, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :key, :value, :value_type, :description, "
                ":spec, :commercial, now(), now())"
            ).bindparams(
                key=key, value=value, value_type=value_type,
                description=description, spec=spec, commercial=commercial,
            )
        )

    op.create_table(
        "pricing_calculations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fulfillment_id", UUID(as_uuid=True), sa.ForeignKey("fulfillments.id", ondelete="RESTRICT"), nullable=True),
        #  17 versioning: the schedule used, e.g. DELIVERY_V1_2026_10. A later
        # schedule change creates a new version and never rewrites old rows.
        sa.Column("pricing_version", sa.String(40), nullable=False),
        # What triggered this calculation: quote, dispatch_requote, retry, manual.
        sa.Column("reason", sa.String(40), nullable=False, server_default="quote"),
        #  3.2 /  4 the two legs and their provenance.
        sa.Column("merchant_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("merchant_lng", sa.Numeric(9, 6), nullable=True),
        sa.Column("customer_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("customer_lng", sa.Numeric(9, 6), nullable=True),
        sa.Column("rider_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("rider_lng", sa.Numeric(9, 6), nullable=True),
        sa.Column("merchant_to_customer_km", sa.Numeric(10, 3), nullable=False),
        sa.Column("rider_to_merchant_km", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column("distance_source", sa.String(20), nullable=True),
        sa.Column("distance_is_approximate", sa.Boolean(), nullable=False, server_default="0"),
        #  3.1 /  7 order inputs
        sa.Column("basket_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("package_weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("service_level", sa.String(20), nullable=True),
        sa.Column("supply_ratio", sa.Numeric(8, 3), nullable=True),
        # The parameter values used, so the arithmetic can be re-derived later
        # even after the schedule changes.
        sa.Column("base_fare", sa.Numeric(12, 2), nullable=False),
        sa.Column("customer_distance_rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("customer_weight_multiplier", sa.Numeric(6, 4), nullable=False, server_default="1"),
        sa.Column("customer_surge_multiplier", sa.Numeric(6, 4), nullable=False, server_default="1"),
        sa.Column("customer_delivery_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("merchant_subsidy", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("ekshop_subsidy", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("customer_amount_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("rider_base_fare", sa.Numeric(12, 2), nullable=False),
        sa.Column("rider_distance_rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("rider_distance_payout", sa.Numeric(12, 2), nullable=False),
        sa.Column("waiting_payout", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("chargeable_wait_minutes", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("rider_total_payout", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("expected_exception_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("expected_delivery_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("expected_contribution", sa.Numeric(12, 2), nullable=False),
        sa.Column("contribution_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("delivery_basket_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("minimum_economic_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("pricing_status", sa.String(30), nullable=False),
        sa.Column("pricing_decision", sa.String(40), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("requires_manual_quote", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("order_id", "reason", "pricing_version", name="uq_pricing_calculation"),
    )
    op.create_index("ix_pricing_calculations_order_id", "pricing_calculations", ["order_id"])
    op.create_index("ix_pricing_calculations_fulfillment_id", "pricing_calculations", ["fulfillment_id"])
    op.create_index("ix_pricing_calculations_pricing_version", "pricing_calculations", ["pricing_version"])
    op.create_index(
        "ix_pricing_calculations_status_created_at", "pricing_calculations", ["pricing_status", "created_at"]
    )
    op.create_check_constraint(
        "ck_pricing_calculations_status", "pricing_calculations",
        "pricing_status IN ('HEALTHY','POSITIVE_LOW_MARGIN','LOSS_MAKING')",
    )

    #  17 audit rows are append-only, exactly like delivery_job_events.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ekshop_deny_pricing_calculation_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF current_setting('ekshop.allow_event_mutation', true) = 'on' THEN
                RETURN COALESCE(NEW, OLD);
            END IF;
            RAISE EXCEPTION
                'pricing_calculations is append-only; % is not permitted.  17 '
                'requires historical economics to be retained exactly as calculated.',
                TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_pricing_calculations_append_only
        BEFORE UPDATE OR DELETE ON pricing_calculations
        FOR EACH ROW EXECUTE FUNCTION ekshop_deny_pricing_calculation_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_pricing_calculations_append_only ON pricing_calculations;")
    op.execute("DROP FUNCTION IF EXISTS ekshop_deny_pricing_calculation_mutation();")
    op.drop_index("ix_pricing_calculations_status_created_at", table_name="pricing_calculations")
    op.drop_index("ix_pricing_calculations_pricing_version", table_name="pricing_calculations")
    op.drop_index("ix_pricing_calculations_fulfillment_id", table_name="pricing_calculations")
    op.drop_index("ix_pricing_calculations_order_id", table_name="pricing_calculations")
    op.drop_table("pricing_calculations")
    op.drop_table("pricing_parameters")