"""anchor the distance-band ladder so a farther band is never cheaper

The ladder inherited from the geo_region model was non-monotonic: countrywide
(210) undercut both same-region (360) and neighbouring-region (350), so a parcel
to Mandera priced below one to Nyeri. Those rates were never charged — geo_region
was never switched on — but they became the cost_based ladder for those bands in
e5a2c8d41b93, and would have gone live the moment the model was switched.

The values here are anchored to what buyers actually pay today. The median paid
cart is Ksh 200 of goods and Ksh 127 of delivery under the legacy cart-total
model, so same_county is set to 130: with no seller wards on file yet, every
local order resolves to that band, and holding it at ~127 keeps the switch to
cost_based roughly price-neutral for the three quarters of carts under Ksh 400.
The far bands rise, because the legacy model underpriced long hauls badly.

unknown_origin sits at the same-region rate: with a third of active sellers
missing a county we can't place the parcel, so it is priced as a regional trip
rather than as a penalty the buyer has no way to avoid.

Revision ID: a3f81c26d945
Revises: e5a2c8d41b93
Create Date: 2026-09-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a3f81c26d945"
down_revision = "e5a2c8d41b93"
branch_labels = None
depends_on = None


# Nearest to farthest. Monotonicity is the invariant: each entry must be >= the
# one above it, or a buyer can pay less to ship further.
_LADDER = {
    "same_ward_fee": "90.00",
    "same_subcounty_fee": "110.00",
    "same_county_fee": "130.00",
    "same_region_fee": "190.00",
    "adjacent_region_fee": "280.00",
    "different_region_fee": "400.00",
    "unknown_origin_fee": "190.00",
}

# What e5a2c8d41b93 and the model shipped with, for the downgrade.
_PREVIOUS_SERVER_DEFAULTS = {
    "same_ward_fee": "100.00",
    "same_subcounty_fee": "140.00",
    "same_county_fee": "200.00",
    "same_region_fee": "350.00",
    "adjacent_region_fee": "350.00",
    "different_region_fee": "600.00",
    "unknown_origin_fee": "400.00",
}


def upgrade() -> None:
    # Overwrites the band fees outright rather than only re-anchoring untouched
    # rows. Unlike the earlier migration there is no admin tuning to preserve
    # here: these columns have only ever held geo_region rates, which were never
    # charged, and the inherited ladder is actively wrong.
    op.execute(
        "UPDATE delivery_rate_settings SET "
        + ", ".join(f"{col} = '{val}'" for col, val in _LADDER.items())
    )

    for col, val in _LADDER.items():
        op.alter_column("delivery_rate_settings", col, server_default=val)


def downgrade() -> None:
    # Restores the previous server defaults but deliberately leaves existing
    # rows on the anchored ladder. Resurrecting a ladder where shipping further
    # cost less would be a downgrade in the literal sense.
    for col, val in _PREVIOUS_SERVER_DEFAULTS.items():
        op.alter_column("delivery_rate_settings", col, server_default=val)
