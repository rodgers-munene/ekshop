from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.models.analytics import HeroSlide
from app.schemas.admin import HeroSlideRead

router = APIRouter(tags=["hero"])


@router.get("/hero-slides", response_model=List[HeroSlideRead])
def list_active_hero_slides(db: Session = Depends(get_db)):
    return (
        db.query(HeroSlide)
        .filter(HeroSlide.is_active == True)
        .order_by(HeroSlide.sort_order)
        .all()
    )
