"""replace the cart-total delivery fee with distance/weight cost-based pricing

Adds the distance-band, weight and bound columns the cost_based model needs, and
swaps the two-state use_geo_pricing boolean for a three-state pricing_model.

Nothing changes at checkout on deploy: existing rows are backfilled to whichever
model they were already charging. Switching to cost_based is a deliberate act on
the admin Delivery Rates page.

Revision ID: e5a2c8d41b93
Revises: d1e4b7c9f2a5
Create Date: 2026-09-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5a2c8d41b93"
down_revision = "d1e4b7c9f2a5"
branch_labels = None
depends_on = None


# What the geo_region model shipped with. Rows still holding exactly these keep
# their meaning but are re-anchored to the cost_based ladder below; rows an admin
# has since edited are left alone.
_UNTOUCHED_GEO_DEFAULTS = {
    "same_county_fee": "200.00",
    "same_region_fee": "350.00",
    "different_region_fee": "600.00",
    "unknown_origin_fee": "400.00",
}

_NEW_ANCHORED_DEFAULTS = {
    "same_county_fee": "180.00",
    "same_region_fee": "250.00",
    "different_region_fee": "470.00",
    "unknown_origin_fee": "200.00",
}


def upgrade() -> None:
    op.add_column("delivery_rate_settings", sa.Column("same_ward_fee", sa.String(20), nullable=False, server_default="100.00"))
    op.add_column("delivery_rate_settings", sa.Column("same_subcounty_fee", sa.String(20), nullable=False, server_default="140.00"))
    op.add_column("delivery_rate_settings", sa.Column("adjacent_region_fee", sa.String(20), nullable=False, server_default="350.00"))
    op.add_column("delivery_rate_settings", sa.Column("weight_allowance_kg", sa.String(20), nullable=False, server_default="10"))
    op.add_column("delivery_rate_settings", sa.Column("per_kg_fee", sa.String(20), nullable=False, server_default="12.00"))
    op.add_column("delivery_rate_settings", sa.Column("max_weight_surcharge", sa.String(20), nullable=False, server_default="600.00"))
    op.add_column("delivery_rate_settings", sa.Column("min_delivery_fee", sa.String(20), nullable=False, server_default="60.00"))
    op.add_column("delivery_rate_settings", sa.Column("max_delivery_fee", sa.String(20), nullable=False, server_default="800.00"))
    op.add_column("delivery_rate_settings", sa.Column("pricing_model", sa.String(20), nullable=False, server_default="cart_total"))

    # Preserve whatever each row was charging before this migration ran.
    op.execute(
        "UPDATE delivery_rate_settings "
        "SET pricing_model = CASE WHEN use_geo_pricing THEN 'geo_region' ELSE 'cart_total' END"
    )

    # Re-anchor only the rows that never had their geo rates customised, so an
    # admin's tuning survives but a stock install lands on the new ladder.
    where_untouched = " AND ".join(f"{col} = '{val}'" for col, val in _UNTOUCHED_GEO_DEFAULTS.items())
    set_new = ", ".join(f"{col} = '{val}'" for col, val in _NEW_ANCHORED_DEFAULTS.items())
    op.execute(f"UPDATE delivery_rate_settings SET {set_new} WHERE {where_untouched}")

    op.drop_column("delivery_rate_settings", "use_geo_pricing")


def downgrade() -> None:
    op.add_column("delivery_rate_settings", sa.Column("use_geo_pricing", sa.Boolean(), nullable=False, server_default=sa.false()))
    # cost_based has no pre-migration equivalent; fall back to the legacy model
    # rather than silently charging the never-enabled geo rates.
    op.execute("UPDATE delivery_rate_settings SET use_geo_pricing = (pricing_model = 'geo_region')")

    op.drop_column("delivery_rate_settings", "pricing_model")
    op.drop_column("delivery_rate_settings", "max_delivery_fee")
    op.drop_column("delivery_rate_settings", "min_delivery_fee")
    op.drop_column("delivery_rate_settings", "max_weight_surcharge")
    op.drop_column("delivery_rate_settings", "per_kg_fee")
    op.drop_column("delivery_rate_settings", "weight_allowance_kg")
    op.drop_column("delivery_rate_settings", "adjacent_region_fee")
    op.drop_column("delivery_rate_settings", "same_subcounty_fee")
    op.drop_column("delivery_rate_settings", "same_ward_fee")
