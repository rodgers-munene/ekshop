from fastapi import APIRouter, HTTPException, Depends, status
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import update, func

from app.dependencies.auth import get_current_active_user, require_seller
from app.dependencies.database import get_db
from app.schemas.shop import (
    ShopCreate,
    ShopRead,
    ShopUpdate,
    ShopPaymentMethodCreate,
    ShopPaymentMethodRead,
    ShopDashboardRead,
)
from app.models.shop import Shop, ShopPaymentMethod
from app.models.user import User
from app.models.commerce import Order, OrderGroup
from app.models.catalog import Product
from app.schemas.commerce import OrderRead
from app.schemas.catalog import ProductListResponse

router = APIRouter(prefix="/shops", tags=["shops"])


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
    current_user: User = Depends(get_current_active_user),
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

    offset = (page - 1) * limit
    total = db.query(func.count(Product.id)).filter(Product.shop_id == shop.id).scalar() or 0
    products = (
        db.query(Product)
        .filter(Product.shop_id == shop.id)
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
