"""County lookups shared by the endpoints that accept a county from a client.

The `counties` table is seeded with Kenya's 47 counties by the
`f4a29b7c1e05_add_geography_ward_level` migration, so it -- not a hardcoded
list -- is the source of truth for what a valid county is.
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.geography import County


def resolve_county_name(db: Session, value: Optional[str]) -> Optional[str]:
    """Return the canonically-cased county name, or raise ValueError.

    Matching is case-insensitive and ignores surrounding whitespace so that
    "nairobi " and "NAIROBI" both store as "Nairobi", which keeps county-keyed
    lookups (delivery pricing, recommendations) from silently missing.
    """
    if value is None:
        return None

    cleaned = " ".join(value.split())
    county = (
        db.query(County)
        .filter(func.lower(County.name) == cleaned.lower())
        .first()
    )
    if not county:
        raise ValueError("Select a valid county")

    return county.name
