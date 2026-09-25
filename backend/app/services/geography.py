"""County lookups shared by the endpoints that accept a county from a client.

The `counties` table is seeded with Kenya's 47 counties by the
`f4a29b7c1e05_add_geography_ward_level` migration, so it -- not a hardcoded
list -- is the source of truth for what a valid county is.
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.geography import County, SubCounty, Ward
import uuid


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


def normalize_name(value: Optional[str]) -> str:
    """Collapse whitespace and casefold for consistent comparisons."""
    return func.lower(func.regexp_replace(func.coalesce(value, ""), r"\s+", "", "g"))


def resolve_geo_ids(
    db: Session,
    county: Optional[str] = None,
    subcounty: Optional[str] = None,
    ward: Optional[str] = None,
) -> tuple[Optional[uuid.UUID], Optional[uuid.UUID], Optional[uuid.UUID]]:
    """Resolve IEBC/administrative name strings into the matching DB row ids.

    Names are matched case-insensitively with whitespace collapsed so that
    geojson names like "KABARNET" or "Runyenjes  Sub County" find the
    corresponding DB rows.  Any level can be omitted -- the returned ids will
    simply be ``None``.
    """
    if ward and subcounty and county:
        ward_row = (
            db.query(Ward.id, SubCounty.id, County.id)
            .join(SubCounty, SubCounty.id == Ward.subcounty_id)
            .join(County, County.id == SubCounty.county_id)
            .filter(
                normalize_name(Ward.name) == normalize_name(ward),
                normalize_name(SubCounty.name) == normalize_name(subcounty),
                normalize_name(County.name) == normalize_name(county),
            )
            .first()
        )
        if ward_row:
            return ward_row[2], ward_row[1], ward_row[0]
    if subcounty and county:
        sub_row = (
            db.query(SubCounty.id, County.id)
            .join(County, County.id == SubCounty.county_id)
            .filter(
                normalize_name(SubCounty.name) == normalize_name(subcounty),
                normalize_name(County.name) == normalize_name(county),
            )
            .first()
        )
        if sub_row:
            return sub_row[1], sub_row[0], None
    if county:
        county_row = (
            db.query(County.id)
            .filter(normalize_name(County.name) == normalize_name(county))
            .first()
        )
        if county_row:
            return county_row[0], None, None
    return None, None, None
