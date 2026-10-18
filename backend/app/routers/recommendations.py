import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.dependencies.database import get_db
from app.models.commerce import UserAddress
from app.models.user import User, UserStatus
from app.schemas.catalog import ProductRead
from app.schemas.recommendations import UserEventCreate
from app.services import recommendations as rec_service
from app.services.distance import GeoPoint

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _resolve_buyer_location(
    db: Session,
    user: Optional[User],
    county_override: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> tuple[Optional[str], Optional[GeoPoint]]:
    """Work out what we know about where this buyer is.

    Returns the county plus, when we have it, a coordinate. Coordinates beat a
    county name for proximity but do not replace it: a buyer can be browsing from
    Mombasa while their saved delivery address is in Nyeri, and the county is
    still the better signal for what they can actually receive. Hence both, and
    both optional -- an anonymous visitor with no location simply gets plain
    trending, which is the behaviour that existed before any of this.
    """
    if lat is not None and lng is not None:
        origin = GeoPoint(float(lat), float(lng))
    else:
        origin = None

    if county_override:
        return county_override, origin
    if not user:
        return None, origin

    address = (
        db.query(UserAddress)
        .filter(UserAddress.user_id == user.id)
        .order_by(UserAddress.is_default.desc(), UserAddress.created_at.desc())
        .first()
    )
    if not address:
        return None, origin
    if origin is None and address.lat is not None and address.lng is not None:
        origin = GeoPoint(float(address.lat), float(address.lng))
    return address.county, origin


def _get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = decode_access_token(auth.split(" ", 1)[1])
        user_id = payload.get("sub")
        if not user_id or payload.get("type") != "access":
            return None
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        return user if user and user.status == UserStatus.active else None
    except Exception:
        return None


@router.post("/events", status_code=204)
def log_event(
    payload: UserEventCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_get_optional_user),
):
    rec_service.log_event(
        db=db,
        session_id=payload.session_id,
        event_type=payload.event_type,
        user_id=current_user.id if current_user else None,
        product_id=payload.product_id,
        category_id=payload.category_id,
        query=payload.query,
        meta=payload.meta,
    )


@router.get("", response_model=List[ProductRead])
def get_recommendations(
    limit: int = Query(20, ge=1, le=50),
    county: Optional[str] = Query(None, description="Override the buyer's saved county for geo-ranking"),
    lat: Optional[float] = Query(None, ge=-90, le=90, description="Buyer's latitude, for proximity ranking"),
    lng: Optional[float] = Query(None, ge=-180, le=180, description="Buyer's longitude, for proximity ranking"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_get_optional_user),
):
    user_id = current_user.id if current_user else None
    buyer_county, origin = _resolve_buyer_location(db, current_user, county, lat, lng)
    return rec_service.get_recommendations(
        db=db, user_id=user_id, limit=limit, buyer_county=buyer_county, origin=origin
    )


@router.get("/trending", response_model=List[ProductRead])
def get_trending(
    limit: int = Query(20, ge=1, le=50),
    county: Optional[str] = Query(None, description="Override the buyer's saved county for geo-ranking"),
    lat: Optional[float] = Query(None, ge=-90, le=90, description="Buyer's latitude, for proximity ranking"),
    lng: Optional[float] = Query(None, ge=-180, le=180, description="Buyer's longitude, for proximity ranking"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_get_optional_user),
):
    buyer_county, origin = _resolve_buyer_location(db, current_user, county, lat, lng)
    return rec_service.get_trending(
        db=db, limit=limit, buyer_county=buyer_county, origin=origin
    )
