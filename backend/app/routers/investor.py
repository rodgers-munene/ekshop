import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Numeric, cast, func
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.models.commerce import Order, OrderGroup, OrderGroupStatus, OrderStatus
from app.models.catalog import Product
from app.models.shop import Shop
from app.models.user import User, UserRole
from app.schemas.investor import (
    InvestorDailyRevenuePoint,
    InvestorDailyRevenueResponse,
    InvestorOverviewRead,
    InvestorTrendPoint,
    TopBuyerRead,
    TopSellerRead,
)

router = APIRouter(prefix="/investor", tags=["investor"])

LOSS_STATUSES = (OrderStatus.cancelled, OrderStatus.refunded)


@router.get("/overview", response_model=InvestorOverviewRead)
def get_overview(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    paid_groups = db.query(OrderGroup).filter(OrderGroup.status == OrderGroupStatus.paid)

    def revenue_since(since: datetime = None) -> Decimal:
        q = paid_groups
        if since is not None:
            q = q.filter(OrderGroup.created_at >= since)
        total = q.with_entities(func.sum(cast(OrderGroup.total, Numeric))).scalar()
        return Decimal(total) if total is not None else Decimal("0")

    revenue_total = revenue_since()
    revenue_30d = revenue_since(since_30d)
    revenue_7d = revenue_since(since_7d)

    total_orders = paid_groups.count()
    orders_30d = paid_groups.filter(OrderGroup.created_at >= since_30d).count()
    orders_7d = paid_groups.filter(OrderGroup.created_at >= since_7d).count()

    total_buyers = db.query(func.count(User.id)).filter(User.role == UserRole.buyer).scalar() or 0
    total_sellers = db.query(func.count(User.id)).filter(User.role == UserRole.seller).scalar() or 0
    total_shops = db.query(func.count(Shop.id)).scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0

    losses_row = (
        db.query(
            func.coalesce(func.sum(cast(Order.total, Numeric)), 0).label("total"),
            func.count(Order.id).label("count"),
        )
        .filter(Order.status.in_(LOSS_STATUSES))
        .one()
    )
    losses_total = Decimal(losses_row.total)
    losses_count = int(losses_row.count)

    status_rows = db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    order_status_counts = {status.value: count for status, count in status_rows}

    top_seller_rows = (
        db.query(
            Shop.name.label("shop_name"),
            func.sum(cast(Order.total, Numeric)).label("revenue"),
            func.count(Order.id).label("orders"),
        )
        .join(Shop, Shop.id == Order.shop_id)
        .join(OrderGroup, OrderGroup.id == Order.group_id)
        .filter(OrderGroup.status == OrderGroupStatus.paid)
        .group_by(Shop.id, Shop.name)
        .order_by(func.sum(cast(Order.total, Numeric)).desc())
        .limit(10)
        .all()
    )
    top_sellers = [
        TopSellerRead(shop_name=row.shop_name, revenue=str(row.revenue), orders=row.orders) for row in top_seller_rows
    ]

    top_buyer_rows = (
        db.query(
            User.first_name.label("first_name"),
            User.last_name.label("last_name"),
            func.sum(cast(OrderGroup.total, Numeric)).label("revenue"),
            func.count(OrderGroup.id).label("orders"),
        )
        .join(User, User.id == OrderGroup.buyer_id)
        .filter(OrderGroup.status == OrderGroupStatus.paid)
        .group_by(User.id, User.first_name, User.last_name)
        .order_by(func.sum(cast(OrderGroup.total, Numeric)).desc())
        .limit(10)
        .all()
    )
    top_buyers = [
        TopBuyerRead(name=f"{row.first_name} {row.last_name}", revenue=str(row.revenue), orders=row.orders)
        for row in top_buyer_rows
    ]

    year_rows = (
        db.query(func.extract("year", OrderGroup.created_at))
        .filter(OrderGroup.status == OrderGroupStatus.paid)
        .distinct()
        .all()
    )
    available_years = sorted({int(row[0]) for row in year_rows if row[0] is not None}, reverse=True)

    return InvestorOverviewRead(
        revenue_total=str(revenue_total),
        revenue_30d=str(revenue_30d),
        revenue_7d=str(revenue_7d),
        total_orders=total_orders,
        orders_30d=orders_30d,
        orders_7d=orders_7d,
        total_buyers=total_buyers,
        total_sellers=total_sellers,
        total_shops=total_shops,
        total_products=total_products,
        losses_total=str(losses_total),
        losses_count=losses_count,
        order_status_counts=order_status_counts,
        top_sellers=top_sellers,
        top_buyers=top_buyers,
        available_years=available_years,
    )


def _rolling_trend(db: Session, days: int) -> List[InvestorTrendPoint]:
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

    points: List[InvestorTrendPoint] = []
    today = datetime.now(timezone.utc).date()
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        row = by_day.get(day)
        points.append(
            InvestorTrendPoint(
                label=day.strftime("%d %b"),
                revenue=float(row.revenue) if row and row.revenue else 0.0,
                orders=int(row.orders) if row else 0,
            )
        )
    return points


def _monthly_daily_trend(db: Session, year: int, month: int) -> List[InvestorTrendPoint]:
    days_in_month = calendar.monthrange(year, month)[1]
    day_col = func.date_trunc("day", OrderGroup.created_at)

    rows = (
        db.query(
            day_col.label("day"),
            func.sum(cast(OrderGroup.total, Numeric)).label("revenue"),
            func.count(OrderGroup.id).label("orders"),
        )
        .filter(
            OrderGroup.status == OrderGroupStatus.paid,
            func.extract("year", OrderGroup.created_at) == year,
            func.extract("month", OrderGroup.created_at) == month,
        )
        .group_by(day_col)
        .all()
    )
    by_day = {row.day.date(): row for row in rows}

    points: List[InvestorTrendPoint] = []
    for d in range(1, days_in_month + 1):
        day = date(year, month, d)
        row = by_day.get(day)
        points.append(
            InvestorTrendPoint(
                label=day.strftime("%d %b"),
                revenue=float(row.revenue) if row and row.revenue else 0.0,
                orders=int(row.orders) if row else 0,
            )
        )
    return points


def _yearly_monthly_trend(db: Session, year: int) -> List[InvestorTrendPoint]:
    month_col = func.date_trunc("month", OrderGroup.created_at)

    rows = (
        db.query(
            month_col.label("month"),
            func.sum(cast(OrderGroup.total, Numeric)).label("revenue"),
            func.count(OrderGroup.id).label("orders"),
        )
        .filter(OrderGroup.status == OrderGroupStatus.paid, func.extract("year", OrderGroup.created_at) == year)
        .group_by(month_col)
        .all()
    )
    by_month = {row.month.date().month: row for row in rows}

    points: List[InvestorTrendPoint] = []
    for m in range(1, 13):
        row = by_month.get(m)
        points.append(
            InvestorTrendPoint(
                label=f"{calendar.month_abbr[m]} {year}",
                revenue=float(row.revenue) if row and row.revenue else 0.0,
                orders=int(row.orders) if row else 0,
            )
        )
    return points


@router.get("/trend", response_model=List[InvestorTrendPoint])
def get_trend(
    days: int = Query(30, ge=1, le=90),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    if month and not year:
        year = datetime.now(timezone.utc).year

    if year and month:
        return _monthly_daily_trend(db, year, month)
    if year:
        return _yearly_monthly_trend(db, year)
    return _rolling_trend(db, days)


@router.get("/daily-revenue", response_model=InvestorDailyRevenueResponse)
def get_daily_revenue(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if month and not year:
        year = datetime.now(timezone.utc).year

    day_col = func.date_trunc("day", OrderGroup.created_at)
    q = db.query(
        day_col.label("day"),
        func.sum(cast(OrderGroup.total, Numeric)).label("revenue"),
        func.count(OrderGroup.id).label("orders"),
    ).filter(OrderGroup.status == OrderGroupStatus.paid)

    if year:
        q = q.filter(func.extract("year", OrderGroup.created_at) == year)
    if month:
        q = q.filter(func.extract("month", OrderGroup.created_at) == month)

    q = q.group_by(day_col)
    total = q.count()
    rows = q.order_by(day_col.desc()).offset((page - 1) * limit).limit(limit).all()

    results = [
        InvestorDailyRevenuePoint(date=row.day.date().isoformat(), revenue=str(row.revenue), orders=int(row.orders))
        for row in rows
    ]
    return InvestorDailyRevenueResponse(total=total, page=page, limit=limit, results=results)
