"""feat(pricing): add the specification's pricing inputs and reshape two models

Revision ID: a7b8c9d0e1f2
Revises: f7a7b8c9d0e1f
Create Date: 2026-10-01 02:20:00.000000

Brings the schema in line with `ekshop_technical_specification.md` (v1.0 MVP).
None of this builds the pricing engine -- it is the plumbing the engine needs,
and it is required regardless of how the open pricing questions are answered.

Adds
-----
orders
  package_weight_kg        §3.1, §7  -- drives the weight multiplier
  service_level            §3.1, §9  -- STANDARD / PRIORITY / EXPRESS
  delivery_price_locked    §14       -- price must not drift after checkout

shops
  delivery_subsidy_enabled, delivery_subsidy_amount,
  free_delivery_threshold, maximum_delivery_subsidy,
  weekly_subsidy_budget    §10.1, §10.2, B.1

delivery_jobs
  merchant_to_customer_km  §4       -- the leg the customer is priced on
  rider_to_merchant_km     §4       -- the rider's trip to collect
  distance_source          §3.2     -- how the figures were obtained
  distance_is_approximate  §3.2     -- true if straight-line was used
  estimated_duration_seconds         -- feeds the §14 SLA and §13 batching test

Changes
-------
delivery_jobs.distance_km is replaced by the two legs above. §4 requires them
separately: the customer is priced on merchant->customer while the rider is paid
for the whole movement. One column cannot express both, and keeping a single
number is how a rider who travelled to the merchant ends up underpaid.

fulfillments.payer and payer_split_pct are replaced by explicit amounts:
merchant_subsidy, ekshop_subsidy, delivery_price_gross, customer_payment. §10
and B.1 define a three-way split -- customer pays the remainder after the
merchant and Ekshop subsidies -- which a single payer enum plus a percentage
cannot represent. Contribution is always computed on the gross price, never on
what the customer hands over.

Both replacements backfill from the old columns where a value exists, so no
fulfillment loses its pricing data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f7a7b8c9d0e1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── orders: pricing inputs (§3.1, §9, §14) ────────────────────────────────
    op.add_column("orders", sa.Column("package_weight_kg", sa.Numeric(8, 3), nullable=True))
    op.add_column(
        "orders",
        sa.Column("service_level", sa.String(20), nullable=False, server_default="standard"),
    )
    op.add_column(
        "orders",
        sa.Column("delivery_price_locked", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_orders_package_weight_non_negative", "orders", "package_weight_kg IS NULL OR package_weight_kg >= 0"
    )
    op.create_check_constraint(
        "ck_orders_service_level", "orders", "service_level IN ('standard','priority','express')"
    )

    # ── shops: merchant subsidy configuration (§10.1) ────────────────────────
    op.add_column(
        "shops",
        sa.Column("delivery_subsidy_enabled", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "shops",
        sa.Column("delivery_subsidy_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column("shops", sa.Column("free_delivery_threshold", sa.Numeric(12, 2), nullable=True))
    op.add_column("shops", sa.Column("maximum_delivery_subsidy", sa.Numeric(12, 2), nullable=True))
    op.add_column("shops", sa.Column("weekly_subsidy_budget", sa.Numeric(12, 2), nullable=True))
    op.create_check_constraint(
        "ck_shops_subsidy_amount_non_negative", "shops", "delivery_subsidy_amount >= 0"
    )

    # ── delivery_jobs: split the distance into its two legs (§4, §3.2) ───────
    # Backfill the merchant->customer leg from the old single column, so existing
    # jobs keep a usable figure. rider_to_merchant_km stays NULL because the old
    # value never captured it -- it must be measured, not guessed.
    op.add_column("delivery_jobs", sa.Column("merchant_to_customer_km", sa.Numeric(10, 2), nullable=True))
    op.add_column("delivery_jobs", sa.Column("rider_to_merchant_km", sa.Numeric(10, 2), nullable=True))
    op.add_column("delivery_jobs", sa.Column("distance_source", sa.String(20), nullable=True))
    op.add_column(
        "delivery_jobs",
        sa.Column("distance_is_approximate", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.add_column(
        "delivery_jobs", sa.Column("estimated_duration_seconds", sa.Integer(), nullable=True)
    )
    op.execute(
        """
        UPDATE delivery_jobs
        SET merchant_to_customer_km = distance_km,
            distance_source = 'straight_line',
            distance_is_approximate = TRUE
        WHERE distance_km IS NOT NULL
        """
    )
    # Every pre-existing distance came from the Haversine helper, so they are all
    # straight-line and must be treated as approximate until re-measured.
    op.drop_column("delivery_jobs", "distance_km")

    # ── fulfillments: three-way subsidy split (§10, B.1) ─────────────────────
    op.add_column(
        "fulfillments",
        sa.Column("merchant_subsidy", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "fulfillments",
        sa.Column("ekshop_subsidy", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column("fulfillments", sa.Column("delivery_price_gross", sa.Numeric(12, 2), nullable=True))
    op.add_column("fulfillments", sa.Column("customer_payment", sa.Numeric(12, 2), nullable=True))

    # Carry the old quote across, and translate the two-way split so no pricing
    # data is lost: a 'split' fulfillment becomes an explicit customer share as
    # `customer_payment`, with the remainder recorded as a merchant subsidy.
    op.execute(
        """
        UPDATE fulfillments
        SET delivery_price_gross = quoted_fee,
            customer_payment = quoted_fee,
            ekshop_subsidy = 0,
            merchant_subsidy = 0
        WHERE quoted_fee IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE fulfillments
        SET merchant_subsidy = COALESCE(
                ROUND(quoted_fee * (100 - payer_split_pct) / 100, 2), 0),
            customer_payment = GREATEST(
                COALESCE(ROUND(quoted_fee * payer_split_pct / 100, 2), quoted_fee), 0)
        WHERE payer = 'split' AND payer_split_pct IS NOT NULL AND quoted_fee IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE fulfillments
        SET merchant_subsidy = COALESCE(quoted_fee, 0)
        WHERE payer = 'merchant' AND quoted_fee IS NOT NULL
          AND (payer_split_pct IS NULL)
        """
    )
    # The original migration created `payer` as a bare VARCHAR, while the model
    # declared an Enum, so no CHECK constraint was ever created in the database.
    # Drop it only if it happens to exist -- `drop_constraint` has no IF EXISTS
    # and would abort the whole revision on a database where it is absent.
    op.execute("ALTER TABLE fulfillments DROP CONSTRAINT IF EXISTS fulfillments_payer_check")
    op.drop_column("fulfillments", "payer_split_pct")
    op.drop_column("fulfillments", "payer")

    op.create_check_constraint(
        "ck_fulfillments_subsidies_non_negative", "fulfillments",
        "merchant_subsidy >= 0 AND ekshop_subsidy >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_fulfillments_subsidies_non_negative", "fulfillments", type_="check")

    op.add_column(
        "fulfillments",
        sa.Column("payer", sa.String(20), nullable=False, server_default="customer"),
    )
    op.add_column("fulfillments", sa.Column("payer_split_pct", sa.Numeric(5, 2), nullable=True))
    op.execute(
        """
        UPDATE fulfillments
        SET payer = CASE
                WHEN merchant_subsidy > 0 AND ekshop_subsidy = 0 THEN 'merchant'
                WHEN merchant_subsidy > 0 THEN 'split'
                ELSE 'customer'
            END,
            payer_split_pct = CASE
                WHEN COALESCE(merchant_subsidy, 0) + COALESCE(ekshop_subsidy, 0) > 0
                THEN ROUND(
                    100 * COALESCE(customer_payment, 0)
                    / NULLIF(COALESCE(delivery_price_gross, 0), 0), 2)
            END
        """
    )
    op.create_check_constraint(
        "fulfillments_payer_check", "fulfillments",
        "payer IN ('customer','merchant','split')",
    )
    op.drop_column("fulfillments", "customer_payment")
    op.drop_column("fulfillments", "delivery_price_gross")
    op.drop_column("fulfillments", "ekshop_subsidy")
    op.drop_column("fulfillments", "merchant_subsidy")

    op.add_column("delivery_jobs", sa.Column("distance_km", sa.Numeric(10, 2), nullable=True))
    op.execute(
        """
        UPDATE delivery_jobs
        SET distance_km = COALESCE(merchant_to_customer_km, 0)
                         + COALESCE(rider_to_merchant_km, 0)
        """
    )
    op.drop_column("delivery_jobs", "estimated_duration_seconds")
    op.drop_column("delivery_jobs", "distance_is_approximate")
    op.drop_column("delivery_jobs", "distance_source")
    op.drop_column("delivery_jobs", "rider_to_merchant_km")
    op.drop_column("delivery_jobs", "merchant_to_customer_km")

    op.drop_constraint("ck_shops_subsidy_amount_non_negative", "shops", type_="check")
    op.drop_column("shops", "weekly_subsidy_budget")
    op.drop_column("shops", "maximum_delivery_subsidy")
    op.drop_column("shops", "free_delivery_threshold")
    op.drop_column("shops", "delivery_subsidy_amount")
    op.drop_column("shops", "delivery_subsidy_enabled")

    op.drop_constraint("ck_orders_service_level", "orders", type_="check")
    op.drop_constraint("ck_orders_package_weight_non_negative", "orders", type_="check")
    op.drop_column("orders", "delivery_price_locked")
    op.drop_column("orders", "service_level")
    op.drop_column("orders", "package_weight_kg")