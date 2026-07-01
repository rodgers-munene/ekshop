import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.dependencies.database import get_db
from app.models.user import User, UserStatus
from app.schemas.catalog import ProductRead
from app.schemas.recommendations import UserEventCreate
from app.services import recommendations as rec_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


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
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_get_optional_user),
):
    user_id = current_user.id if current_user else None
    return rec_service.get_recommendations(db=db, user_id=user_id, limit=limit)


@router.get("/trending", response_model=List[ProductRead])
def get_trending(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return rec_service.get_trending(db=db, limit=limit)
