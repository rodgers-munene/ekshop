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


class MerchantActivityMetrics(BaseModel):
    active_merchants_7d: int
    active_merchants_30d: int
    merchants_receiving_orders: int
    merchants_processing_orders: int
    merchants_zero_activity: int
    sellers_logged_in: int
    products_updated: int
    avg_transactions_per_merchant: float


class SalesDemandMetrics(BaseModel):
    total_orders: int
    gmv: str
    average_order_value: str
    new_customers: int
    repeat_customers: int
    customer_acquisition_rate: float
    cart_abandonment_rate: float
    order_cancellation_rate: float


class CustomerRetentionMetrics(BaseModel):
    new_customers: int
    returning_customers: int
    repeat_purchase_rate: float
    churn_rate: float
    retention_30d: float
    orders_per_customer: float
    avg_days_between_purchases: float
    customer_complaints: int


class OperationsDeliveryMetrics(BaseModel):
    orders_received: int
    orders_accepted: int
    orders_fulfilled: int
    orders_cancelled: int
    avg_dispatch_time_hours: float
    avg_delivery_time_hours: float
    on_time_delivery_rate: Optional[float]
    failed_deliveries: int
    rider_utilization: float
    delivery_revenue: str


class OrderNotificationRecipientCreate(BaseModel):
    email: str
    label: Optional[str] = None


class OrderNotificationRecipientUpdate(BaseModel):
    label: Optional[str] = None
    is_active: Optional[bool] = None


class OrderNotificationRecipientRead(BaseModel):
    id: uuid.UUID
    email: str
    label: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
