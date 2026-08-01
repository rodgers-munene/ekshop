import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.schemas.user import UserRead
from app.schemas.shop import ShopRead
from app.schemas.commerce import OrderRead
from app.schemas.catalog import ProductRead


class HeroSlideCreate(BaseModel):
    image_url: str
    title: Optional[str] = None
    link_url: Optional[str] = None
    sort_order: int = 0


class HeroSlideUpdate(BaseModel):
    image_url: Optional[str] = None
    title: Optional[str] = None
    link_url: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class HeroSlideRead(BaseModel):
    id: uuid.UUID
    image_url: str
    title: Optional[str]
    link_url: Optional[str]
    sort_order: Optional[int] = 0
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PromotionCreate(BaseModel):
    product_id: uuid.UUID
    label: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    sort_order: int = 0


class PromotionUpdate(BaseModel):
    label: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class PromotionRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    label: Optional[str]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    sort_order: Optional[int] = 0
    is_active: bool
    created_at: datetime
    product: Optional[ProductRead] = None

    model_config = {"from_attributes": True}


class AdminStatsRead(BaseModel):
    total_users: int
    total_buyers: int
    total_sellers: int
    new_users_7d: int
    total_shops: int
    shops_pending_verification: int
    total_products: int
    total_orders: int
    orders_7d: int
    revenue_total: str
    revenue_7d: str


class AdminTrendPoint(BaseModel):
    label: str
    revenue: float
    orders: int


class UserListResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[UserRead]


class ShopListResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[ShopRead]


class OrderListResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[OrderRead]
