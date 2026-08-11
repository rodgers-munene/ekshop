from typing import Dict, List
from pydantic import BaseModel


class TopSellerRead(BaseModel):
    shop_name: str
    revenue: str
    orders: int


class TopBuyerRead(BaseModel):
    name: str
    revenue: str
    orders: int


class InvestorOverviewRead(BaseModel):
    revenue_total: str
    revenue_30d: str
    revenue_7d: str
    total_orders: int
    orders_30d: int
    orders_7d: int
    total_buyers: int
    total_sellers: int
    total_shops: int
    total_products: int
    losses_total: str
    losses_count: int
    order_status_counts: Dict[str, int]
    top_sellers: List[TopSellerRead]
    top_buyers: List[TopBuyerRead]
    available_years: List[int]


class InvestorTrendPoint(BaseModel):
    label: str
    revenue: float
    orders: int


class InvestorDailyRevenuePoint(BaseModel):
    date: str
    revenue: str
    orders: int


class InvestorDailyRevenueResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[InvestorDailyRevenuePoint]
