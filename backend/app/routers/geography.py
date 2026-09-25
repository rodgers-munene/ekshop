import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.models.geography import County, SubCounty, Ward
from app.schemas.geography import CountyRead, SubCountyRead, WardRead, ReverseGeocodeRead, GeoSearchResult
from app.services import spatial
from app.services.geography import resolve_geo_ids

router = APIRouter(prefix="/geography", tags=["geography"])


@router.get("/counties", response_model=List[CountyRead])
def list_counties(db: Session = Depends(get_db)):
    return db.query(County).order_by(County.name).all()


@router.get("/counties/{county_name}/subcounties", response_model=List[SubCountyRead])
def list_subcounties(county_name: str, db: Session = Depends(get_db)):
    county = db.query(County).filter(County.name == county_name).first()
    if not county:
        raise HTTPException(404, "County not found")
    return (
        db.query(SubCounty)
        .filter(SubCounty.county_id == county.id)
        .order_by(SubCounty.name)
        .all()
    )


@router.get("/subcounties/{subcounty_id}/wards", response_model=List[WardRead])
def list_wards(subcounty_id: uuid.UUID, db: Session = Depends(get_db)):
    subcounty = db.query(SubCounty).filter(SubCounty.id == subcounty_id).first()
    if not subcounty:
        raise HTTPException(404, "Subcounty not found")
    return db.query(Ward).filter(Ward.subcounty_id == subcounty_id).order_by(Ward.name).all()


@router.get("/reverse-geocode", response_model=ReverseGeocodeRead)
def reverse_geocode(lat: float = Query(..., ge=-90, le=90), lng: float = Query(..., ge=-180, le=180), db: Session = Depends(get_db)):
    """Resolve a (lat, lng) into the administrative chain (county → … → sublocation)."""
    place = spatial.reverse_geocode(lat, lng)
    if not place:
        raise HTTPException(404, detail="Location is outside Kenya")

    county_id, subcounty_id, ward_id = resolve_geo_ids(db, place["county"], place["subcounty"], place["ward"])

    detail = next((x for x in (place.get("sublocation"), place.get("location")) if x), None)
    parts = [detail] if detail else []
    parts.extend([place["ward"], place["subcounty"], place["county"]])
    address_hint = ", ".join(p for p in parts if p)

    return ReverseGeocodeRead(
        lat=lat,
        lng=lng,
        county=place["county"],
        subcounty=place["subcounty"],
        ward=place["ward"],
        location=place.get("location"),
        sublocation=place.get("sublocation"),
        address_hint=address_hint,
        county_id=county_id,
        subcounty_id=subcounty_id,
        ward_id=ward_id,
    )


@router.get("/search", response_model=List[GeoSearchResult])
def search_places(q: str = Query(..., min_length=2), limit: int = Query(8, ge=1, le=20)):
    """Search wards, locations and sublocations by (partial) name."""
    return spatial.search(q, limit=limit)
