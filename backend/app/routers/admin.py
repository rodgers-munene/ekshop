import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import Numeric, cast, func
from sqlalchemy.orm import Session, selectinload

from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.models.commerce import OrderGroup, OrderGroupStatus, Order, OrderStatus
from app.models.catalog import Product
from app.models.delivery import Delivery
from app.models.shop import Shop, ShopStatus
from app.models.user import User, UserRole, UserStatus
from app.models.analytics import HeroSlide, Promotion
from app.schemas.admin import (
    AdminStatsRead,
    AdminTrendPoint,
    HeroSlideCreate,
    HeroSlideRead,
    HeroSlideUpdate,
    OrderListResponse,
    PromotionCreate,
    PromotionRead,
    PromotionUpdate,
    ShopListResponse,
    UserListResponse,
)
from app.schemas.commerce import OrderRead
from app.schemas.shop import ShopRead
from app.schemas.user import UserRead
from app.services import storage

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Stats ────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStatsRead)
def get_stats(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_buyers = db.query(func.count(User.id)).filter(User.role == UserRole.buyer).scalar() or 0
    total_sellers = db.query(func.count(User.id)).filter(User.role == UserRole.seller).scalar() or 0
    new_users_7d = db.query(func.count(User.id)).filter(User.created_at >= seven_days_ago).scalar() or 0

    total_shops = db.query(func.count(Shop.id)).scalar() or 0
    shops_pending = db.query(func.count(Shop.id)).filter(Shop.status == ShopStatus.pending).scalar() or 0

    total_products = db.query(func.count(Product.id)).scalar() or 0

    paid_groups = db.query(OrderGroup).filter(OrderGroup.status == OrderGroupStatus.paid)
    total_orders = paid_groups.count()
    orders_7d = paid_groups.filter(OrderGroup.created_at >= seven_days_ago).count()

    revenue_total = sum((Decimal(g.total) for g in paid_groups.all()), Decimal("0"))
    revenue_7d = sum(
        (Decimal(g.total) for g in paid_groups.filter(OrderGroup.created_at >= seven_days_ago).all()),
        Decimal("0"),
    )

    return AdminStatsRead(
        total_users=total_users,
        total_buyers=total_buyers,
        total_sellers=total_sellers,
        new_users_7d=new_users_7d,
        total_shops=total_shops,
        shops_pending_verification=shops_pending,
        total_products=total_products,
        total_orders=total_orders,
        orders_7d=orders_7d,
        revenue_total=str(revenue_total),
        revenue_7d=str(revenue_7d),
    )


@router.get("/stats/trend", response_model=List[AdminTrendPoint])
def get_stats_trend(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    day_col = func.date_trunc("day", OrderGroup.created_at)

    rows = (
        db.query(
            day_col.label("day"),
            func.sum(cast(OrderGroup.total, Numeric)).label("revenue"),
            func.count(OrderGroup.id).label("orders"),
        )
        .filter(OrderGroup.status == OrderGroupStatus.paid, OrderGroup.created_at >= since)
        .group_by(day_col)
        .all()
    )
    by_day = {row.day.date(): row for row in rows}

    points: List[AdminTrendPoint] = []
    today = datetime.now(timezone.utc).date()
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        row = by_day.get(day)
        points.append(
            AdminTrendPoint(
                label=day.strftime("%d %b"),
                revenue=float(row.revenue) if row and row.revenue else 0.0,
                orders=int(row.orders) if row else 0,
            )
        )
    return points


# ── Deliveries ───────────────────────────────────────────────────────────────

@router.get("/orders/needs-delivery", response_model=OrderListResponse)
def list_orders_needing_delivery(
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = (
        db.query(Order)
        .outerjoin(Delivery, Delivery.order_id == Order.id)
        .filter(
            Order.status.in_([OrderStatus.confirmed, OrderStatus.processing]),
            Delivery.id.is_(None),
        )
    )
    total = query.count()
    skip = (page - 1) * limit
    results = query.order_by(Order.created_at.asc()).offset(skip).limit(limit).all()
    return OrderListResponse(total=total, page=page, limit=limit, results=results)


# ── Shops / sellers ──────────────────────────────────────────────────────────

@router.get("/shops", response_model=ShopListResponse)
def list_shops(
    status_filter: Optional[ShopStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(Shop)
    if status_filter:
        q = q.filter(Shop.status == status_filter)
    total = q.count()
    skip = (page - 1) * limit
    results = q.order_by(Shop.created_at.desc()).offset(skip).limit(limit).all()
    return ShopListResponse(total=total, page=page, limit=limit, results=results)


@router.patch("/shops/{shop_id}/verify", response_model=ShopRead)
def verify_shop(shop_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(404, "Shop not found")
    shop.is_verified = True
    shop.status = ShopStatus.active
    db.commit()
    db.refresh(shop)
    return shop


@router.patch("/shops/{shop_id}/suspend", response_model=ShopRead)
def suspend_shop(shop_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(404, "Shop not found")
    shop.status = ShopStatus.suspended
    db.commit()
    db.refresh(shop)
    return shop


@router.patch("/shops/{shop_id}/feature", response_model=ShopRead)
def toggle_shop_featured(shop_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if not shop:
        raise HTTPException(404, "Shop not found")
    shop.is_featured = not shop.is_featured
    db.commit()
    db.refresh(shop)
    return shop


# ── Users ────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=UserListResponse)
def list_users(
    role: Optional[UserRole] = None,
    status_filter: Optional[UserStatus] = Query(None, alias="status"),
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if status_filter:
        query = query.filter(User.status == status_filter)
    if q:
        like = f"%{q}%"
        query = query.filter((User.email.ilike(like)) | (User.first_name.ilike(like)) | (User.last_name.ilike(like)))
    total = query.count()
    skip = (page - 1) * limit
    results = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return UserListResponse(total=total, page=page, limit=limit, results=results)


@router.patch("/users/{user_id}/suspend", response_model=UserRead)
def suspend_user(user_id: uuid.UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(400, "You can't suspend your own account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.status = UserStatus.suspended
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/reactivate", response_model=UserRead)
def reactivate_user(user_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.status = UserStatus.active
    db.commit()
    db.refresh(user)
    return user


# ── Hero slides ──────────────────────────────────────────────────────────────

@router.get("/hero-slides", response_model=List[HeroSlideRead])
def list_hero_slides(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(HeroSlide).order_by(HeroSlide.sort_order).all()


@router.post("/hero-slides", response_model=HeroSlideRead, status_code=status.HTTP_201_CREATED)
def create_hero_slide(payload: HeroSlideCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    slide = HeroSlide(**payload.model_dump())
    db.add(slide)
    db.commit()
    db.refresh(slide)
    return slide


@router.post("/hero-slides/upload", response_model=HeroSlideRead, status_code=status.HTTP_201_CREATED)
def upload_hero_slide(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    link_url: Optional[str] = Form(None),
    sort_order: int = Form(0),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        url = storage.upload_hero_image(
            filename=file.filename or "image.jpg",
            content_type=file.content_type or "application/octet-stream",
            data=file.file.read(),
        )
    except storage.StorageError as e:
        raise HTTPException(status_code=502, detail=str(e))

    slide = HeroSlide(image_url=url, title=title, link_url=link_url, sort_order=sort_order)
    db.add(slide)
    db.commit()
    db.refresh(slide)
    return slide


@router.patch("/hero-slides/{slide_id}", response_model=HeroSlideRead)
def update_hero_slide(
    slide_id: uuid.UUID,
    payload: HeroSlideUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    slide = db.query(HeroSlide).filter(HeroSlide.id == slide_id).first()
    if not slide:
        raise HTTPException(404, "Hero slide not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(slide, field, value)
    db.commit()
    db.refresh(slide)
    return slide


@router.delete("/hero-slides/{slide_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hero_slide(slide_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    slide = db.query(HeroSlide).filter(HeroSlide.id == slide_id).first()
    if not slide:
        raise HTTPException(404, "Hero slide not found")
    storage.delete_hero_image(slide.image_url)
    db.delete(slide)
    db.commit()


# ── Curated deals ────────────────────────────────────────────────────────────

def _promotion_query(db: Session):
    return db.query(Promotion).options(
        selectinload(Promotion.product).selectinload(Product.images),
        selectinload(Promotion.product).selectinload(Product.variants),
        selectinload(Promotion.product).selectinload(Product.shop),
    )


@router.get("/deals", response_model=List[PromotionRead])
def list_deals(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return _promotion_query(db).order_by(Promotion.sort_order).all()


@router.post("/deals", response_model=PromotionRead, status_code=status.HTTP_201_CREATED)
def create_deal(payload: PromotionCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")
    deal = Promotion(**payload.model_dump())
    db.add(deal)
    db.commit()
    return _promotion_query(db).filter(Promotion.id == deal.id).first()


@router.patch("/deals/{deal_id}", response_model=PromotionRead)
def update_deal(
    deal_id: uuid.UUID,
    payload: PromotionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    deal = db.query(Promotion).filter(Promotion.id == deal_id).first()
    if not deal:
        raise HTTPException(404, "Deal not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(deal, field, value)
    db.commit()
    return _promotion_query(db).filter(Promotion.id == deal_id).first()


@router.delete("/deals/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deal(deal_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    deal = db.query(Promotion).filter(Promotion.id == deal_id).first()
    if not deal:
        raise HTTPException(404, "Deal not found")
    db.delete(deal)
    db.commit()
