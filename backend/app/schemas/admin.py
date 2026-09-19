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


class PeriodFigures(BaseModel):
    revenue: str
    orders: int
    average_order_value: str
    new_users: int
    new_shops: int


class PeriodToDateMetrics(BaseModel):
    """A to-date window (month or year) alongside the same span of the
    previous month/year, so the dashboard can show a like-for-like change."""
    start: datetime
    current: PeriodFigures
    previous: PeriodFigures


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
    mtd: PeriodToDateMetrics
    ytd: PeriodToDateMetrics


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


class CartAbandonedProduct(BaseModel):
    product_id: Optional[uuid.UUID] = None
    name: str
    slug: Optional[str]
    units: int
    at_risk_revenue: str


class TopPurchasedProduct(BaseModel):
    product_id: Optional[uuid.UUID] = None
    name: str
    slug: Optional[str]
    units: int
    revenue: str


class CartAbandonmentMetrics(BaseModel):
    """Real cart-funnel metrics computed from persisted carts and paid orders:
    how many carts were touched in the window, how many converted to a paid
    order, which products sit abandoned in carts, and which were bought most."""
    carts_touched: int
    converted_carts: int
    abandoned_carts: int
    cart_abandonment_rate: float
    abandoned_units: int
    at_risk_revenue: str
    abandoned_products: List[CartAbandonedProduct] = []
    top_products: List[TopPurchasedProduct] = []


class MerchantMasterHealth(BaseModel):
    merchant: str
    location: str
    category: str
    stage: str
    activity: int
    catalogue: int
    demand: int
    reliability: int
    growth: int
    health: int
    health_tier: str
    last_login: Optional[datetime]
    orders_30d: int
    dispatch_hrs: float
    cancel_pct: float
    response_min: int
    next_action: str
    owner: str


class OrderControlTowerRow(BaseModel):
    order_id: str
    received: datetime
    merchant: str
    customer: str
    ack_time: Optional[datetime]
    accepted: bool
    ready_time: Optional[datetime]
    rider_assigned: Optional[str]
    pickup_time: Optional[datetime]
    delivered_time: Optional[datetime]
    dispatch_hrs: float
    delivery_hrs: float
    status: str
    exception_owner: str


class CustomerRecoveryRow(BaseModel):
    customer: str
    segment: str
    last_activity: Optional[datetime]
    cart_value: str
    issue_trigger: str
    contact_date: Optional[datetime]
    channel: str
    response: str
    recovered_order: bool
    next_action: str


class SupplyDemandRow(BaseModel):
    category_area: str
    searches_views: int
    cart_adds: int
    orders: int
    active_shops: int
    products_live: int
    demand_score: int
    supply_score: int
    gap: int
    action: str


class PriorityAcquisitionRow(BaseModel):
    prospect: str
    category: str
    area: str
    demand_evidence: str
    reliability_potential: str
    strategic_value: str
    priority_score: int
    reason: str


class AdminOverviewPeriodMetrics(BaseModel):
    revenue: str
    orders: int
    average_order_value: str
    new_users: int
    new_buyers: int
    new_sellers: int
    new_shops: int
    new_products: int
    cart_abandonment_rate: float


class AdminOverviewTotals(BaseModel):
    total_users: int
    total_buyers: int
    total_sellers: int
    total_shops: int
    shops_pending_verification: int
    total_products: int
    total_orders: int
    revenue_total: str


class AdminOverviewRead(BaseModel):
    period: str
    start: datetime
    metrics: AdminOverviewPeriodMetrics
    previous: AdminOverviewPeriodMetrics
    totals: AdminOverviewTotals
    trend: List[AdminTrendPoint]


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


class AdminEmailTestRequest(BaseModel):
    to: str


class AdminEmailTestResult(BaseModel):
    success: bool
    detail: str


class AdminEmailStatus(BaseModel):
    """Why order/subs emails do or don't go out: whether Resend is configured,
    whether the configured From domain is verified (Resend rejects mail on
    unverified domains), and how many active recipients exist."""
    resend_configured: bool
    from_address: str
    from_domain: str
    verified_domains: List[str]
    from_domain_verified: bool
    domains_error: Optional[str] = None
    active_recipient_count: int


class RecentOrderRow(BaseModel):
    id: str
    short_id: str
    created_at: datetime
    buyer_name: str
    total: str
    item_count: int
    shop_count: int


class RecentOrderListResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[RecentOrderRow]


class AdminProductRow(BaseModel):
    id: uuid.UUID
    name: str
    price: str
    status: str
    shop_name: Optional[str] = None
    created_at: datetime


class AdminProductListResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[AdminProductRow]
