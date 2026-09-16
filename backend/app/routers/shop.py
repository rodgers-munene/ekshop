from fastapi import APIRouter, HTTPException, Depends, status, Query
import uuid
from math import radians, cos, sin, asin, sqrt
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import update, func, case, literal_column

from app.dependencies.auth import (
    get_current_active_user,
    get_current_user_allow_unpaid_seller,
    require_seller,
)
from app.dependencies.database import get_db
from app.schemas.shop import (
    ShopCreate,
    ShopRead,
    ShopUpdate,
    ShopPaymentMethodCreate,
    ShopPaymentMethodRead,
    ShopDashboardRead,
)
from app.models.shop import Shop, ShopPaymentMethod, ShopStatus
from app.models.user import User
from app.models.commerce import Order, OrderGroup
from app.models.catalog import Product
from app.schemas.commerce import OrderRead
from app.schemas.catalog import ProductListResponse, ProductStatus, ShopSummary, ShopListResponse

router = APIRouter(prefix="/shops", tags=["shops"])


@router.get(
    "/",
    response_model=ShopListResponse,
    status_code=status.HTTP_200_OK,
    summary="List shops",
)
def list_shops(
    featured: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(6, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Shop).filter(Shop.status == ShopStatus.active)
    if featured:
        q = q.filter(Shop.is_featured == True)
    total = q.count()
    skip = (page - 1) * limit
    results = q.order_by(Shop.rating_avg.desc()).offset(skip).limit(limit).all()
    return ShopListResponse(total=total, page=page, limit=limit, results=results)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    c = 2 * asin(sqrt(a))
    return round(r * c, 2)


@router.get(
    "/nearby",
    response_model=List[dict],
    status_code=status.HTTP_200_OK,
    summary="List active shops near a lat/lng within a radius",
)
def nearby_shops(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(20, gt=0, le=200),
    db: Session = Depends(get_db),
):
    shops = (
        db.query(
            Shop.id,
            Shop.name,
            Shop.slug,
            Shop.is_verified,
            Shop.rating_avg,
            Shop.rating_count,
            Shop.lat,
            Shop.lng,
        )
        .filter(Shop.status == ShopStatus.active)
        .filter(Shop.lat.is_not(None), Shop.lng.is_not(None))
        .all()
    )

    results = []
    for shop in shops:
        distance = _haversine_km(lat, lng, float(shop.lat), float(shop.lng))
        if distance <= radius_km:
            results.append(
                {
                    "id": str(shop.id),
                    "name": shop.name,
                    "slug": shop.slug,
                    "is_verified": shop.is_verified,
                    "rating_avg": shop.rating_avg,
                    "rating_count": shop.rating_count,
                    "lat": shop.lat,
                    "lng": shop.lng,
                    "distance_km": distance,
                }
            )

    results.sort(key=lambda item: item["distance_km"])
    return results


@router.post(
    "/",
    response_model=ShopRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shop",
)
def create_shop(
    payload: ShopCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    existing = db.query(Shop).filter(Shop.seller_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="You already have a shop")

    shop = Shop(**payload.model_dump(), seller_id=current_user.id)
    db.add(shop)
    db.commit()
    db.refresh(shop)

    return shop


@router.get(
    "/me",
    response_model=ShopRead,
    status_code=status.HTTP_200_OK,
    summary="Get my shop",
)
def get_my_shop(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_allow_unpaid_seller),
):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()

    if not shop:
        raise HTTPException(status_code=404, detail="You don't have a shop yet")

    return shop


@router.get(
    "/{slug}/products",
    response_model=ProductListResponse,
    summary="Get all products for a shop",
)
def get_shop_products(
    slug: str,
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    shop = db.query(Shop).filter(Shop.slug == slug).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    if shop.status != ShopStatus.active:
        return ProductListResponse(total=0, page=page, limit=limit, results=[])

    offset = (page - 1) * limit
    total = db.query(func.count(Product.id)).filter(
        Product.shop_id == shop.id, Product.status == ProductStatus.active
    ).scalar() or 0
    products = (
        db.query(Product)
        .filter(Product.shop_id == shop.id, Product.status == ProductStatus.active)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ProductListResponse(total=total, page=page, limit=limit, results=products)


@router.get(
    "/{slug}",
    response_model=ShopRead,
    status_code=status.HTTP_200_OK,
    summary="Get shop by slug",
)
def get_shop(slug: str, db: Session = Depends(get_db)):
    shop = db.query(Shop).filter(Shop.slug == slug).first()

    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    return shop


@router.patch(
    "/me",
    response_model=ShopRead,
    summary="Update my shop",
)
def update_shop(
    payload: ShopUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()

    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    update_stmt = (
        update(Shop)
        .where(Shop.seller_id == current_user.id)
        .values(**payload.model_dump(exclude_unset=True))
    )

    db.execute(update_stmt)
    db.commit()
    db.refresh(shop)

    return shop


@router.post(
    "/me/payment-methods",
    response_model=ShopPaymentMethodRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a payment method to my shop",
)
def create_payment_method(
    payload: ShopPaymentMethodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()

    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    payment_method = ShopPaymentMethod(**payload.model_dump(), shop_id=shop.id)
    db.add(payment_method)
    db.commit()
    db.refresh(payment_method)

    return payment_method


@router.get(
    "/me/orders",
    response_model=list[OrderRead],
    summary="Get orders placed in my shop",
)
def get_shop_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller),
):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    return (
        db.query(Order)
        .filter(Order.shop_id == shop.id)
        .order_by(Order.created_at.desc())
        .all()
    )


@router.get(
    "/me/orders/{order_id}",
    response_model=OrderRead,
    summary="Get one order in my shop",
)
def get_shop_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller),
):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    order = db.query(Order).filter(Order.id == order_id, Order.shop_id == shop.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


@router.get(
    "/me/dashboard",
    response_model=ShopDashboardRead,
    status_code=status.HTTP_200_OK,
    summary="Get my shop dashboard stats",
)
def get_shop_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()

    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    total_products = db.query(func.count(Product.id)).filter(
        Product.shop_id == shop.id
    ).scalar() or 0

    total_orders = db.query(func.count(Order.id)).filter(
        Order.shop_id == shop.id
    ).scalar() or 0

    return ShopDashboardRead(
        total_sales=shop.total_sales,
        rating_avg=shop.rating_avg,
        rating_count=shop.rating_count,
        total_products=total_products,
        total_orders=total_orders,
    )
