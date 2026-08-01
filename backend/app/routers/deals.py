from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.dependencies.database import get_db
from app.models.analytics import Promotion
from app.models.catalog import Product, ProductStatus
from app.schemas.admin import PromotionRead
from app.services.catalog import with_active_shop

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("/", response_model=List[PromotionRead])
def list_active_deals(limit: int = Query(8, le=20), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    query = with_active_shop(
        db.query(Promotion)
        .join(Product, Promotion.product_id == Product.id)
        .filter(
            Promotion.is_active == True,
            Product.status == ProductStatus.active,
            or_(Promotion.starts_at.is_(None), Promotion.starts_at <= now),
            or_(Promotion.ends_at.is_(None), Promotion.ends_at >= now),
        )
    )
    return (
        query.options(
            selectinload(Promotion.product).selectinload(Product.images),
            selectinload(Promotion.product).selectinload(Product.variants),
            selectinload(Promotion.product).selectinload(Product.shop),
        )
        .order_by(Promotion.sort_order)
        .limit(limit)
        .all()
    )
