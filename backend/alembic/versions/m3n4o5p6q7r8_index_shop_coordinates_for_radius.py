"""index shop coordinates so a radius search can skip the unpinned shops

The hyperlocal feed filters shops by a bounding box around the shopper and then
sorts by distance. Without an index that is a sequential scan of `shops` on every
"near me" page load.

`shops` already had `lat`/`lng`, added for the zone-pricing work, but nothing
indexed them -- the columns were only ever read one row at a time, when pricing a
delivery for an address that was already chosen. A radius search reads all of
them, which is a different access pattern and needs an index.

Partial, and that is the point at rollout: a shop with no pin is excluded from
every radius result by `within_radius` (we cannot honestly call it near), so
those rows have no business occupying space in the index. Launch-day most shops
are unpinned, so the index stays small while the query stays usable. The bbox
predicate is `lat BETWEEN ... AND ...` AND `lng BETWEEN ...`; a btree can range
over the leading `lat` column and the `lng` bounds are checked against the
already-narrowed set. That is enough: the box is the prefilter, the haversine term
in the query is what actually decides.

Revision ID: m3n4o5p6q7r8
Revises: k2l3m4n5o6p7
"""

from alembic import op

revision = "m3n4o5p6q7r8"
down_revision = "k2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_shops_lat_lng
            ON shops (lat, lng)
         WHERE lat IS NOT NULL AND lng IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_shops_lat_lng")
