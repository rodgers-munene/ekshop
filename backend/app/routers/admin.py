import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import Numeric, cast, func
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.models.commerce import (
    Cart,
    CartItem,
    OrderGroup,
    OrderGroupStatus,
    Order,
    OrderItem,
    OrderStatus,
)
from app.models.catalog import Product
from app.models.delivery import Delivery
from app.models.order_notifications import OrderNotificationRecipient
from app.models.shop import Shop, ShopStatus
from app.models.user import User, UserRole, UserStatus
from app.models.analytics import HeroSlide, Promotion
from app.schemas.admin import (
    AdminEmailStatus,
    AdminEmailTestRequest,
    AdminEmailTestResult,
    AdminOverviewRead,
    AdminProductListResponse,
    AdminProductRow,
    AdminStatsRead,
    AdminTrendPoint,
    CartAbandonmentMetrics,
    CustomerRecoveryRow,
    CustomerRetentionMetrics,
    MarginLeakageMetrics,
    MarginLeakageTrendPoint,
    MerchantMasterHealth,
    OperationsDeliveryMetrics,
    OrderControlTowerRow,
    OrderListResponse,
    OrderNotificationRecipientCreate,
    OrderNotificationRecipientRead,
    OrderNotificationRecipientUpdate,
    PeriodFigures,
    PeriodToDateMetrics,
    PriorityAcquisitionRow,
    PromotionCreate,
    PromotionRead,
    PromotionUpdate,
    RecentOrderListResponse,
    RecentOrderRow,
    SalesDemandMetrics,
    ShopListResponse,
    SupplyDemandRow,
    UserListResponse,
)
from app.schemas.commerce import OrderRead
from app.schemas.shop import ShopRead
from app.schemas.user import UserRead
from app.services import storage
from app.services import email as email_service
from app.services import dashboard_metrics

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Stats ────────────────────────────────────────────────────────────────────

# Month/year boundaries are Kenyan calendar boundaries, not UTC ones — an
# order placed at 01:00 EAT on the 1st belongs to the new month. Kenya is a
# fixed UTC+3 with no DST, so a fixed offset is exact (see services/mpesa.py).
EAT = timezone(timedelta(hours=3), "EAT")


def _period_figures(db: Session, start: datetime, end: datetime) -> PeriodFigures:
    revenue, orders = (
        db.query(
            func.coalesce(func.sum(cast(OrderGroup.total, Numeric)), 0),
            func.count(OrderGroup.id),
        )
        .filter(
            OrderGroup.status == OrderGroupStatus.paid,
            OrderGroup.created_at >= start,
            OrderGroup.created_at < end,
        )
        .one()
    )
    revenue = Decimal(revenue).quantize(Decimal("0.01"))
    aov = (revenue / orders).quantize(Decimal("0.01")) if orders else Decimal("0.00")

    new_users = (
        db.query(func.count(User.id)).filter(User.created_at >= start, User.created_at < end).scalar() or 0
    )
    new_shops = (
        db.query(func.count(Shop.id)).filter(Shop.created_at >= start, Shop.created_at < end).scalar() or 0
    )

    return PeriodFigures(
        revenue=str(revenue),
        orders=orders,
        average_order_value=str(aov),
        new_users=new_users,
        new_shops=new_shops,
    )


def _period_to_date(db: Session, start: datetime, previous_start: datetime, now: datetime) -> PeriodToDateMetrics:
    # Compare against the same elapsed span of the previous period, capped at
    # that period's end — so MTD on 31 March compares against all of February
    # rather than spilling into March.
    previous_end = min(previous_start + (now - start), start)
    return PeriodToDateMetrics(
        start=start,
        current=_period_figures(db, start, now),
        previous=_period_figures(db, previous_start, previous_end),
    )


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

    now = datetime.now(EAT)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_start = (month_start - timedelta(days=1)).replace(day=1)
    year_start = month_start.replace(month=1)
    previous_year_start = year_start.replace(year=year_start.year - 1)

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
        mtd=_period_to_date(db, month_start, previous_month_start, now),
        ytd=_period_to_date(db, year_start, previous_year_start, now),
    )


@router.get("/stats/trend", response_model=List[AdminTrendPoint])
def get_stats_trend(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return _trend_points(db, days)


def _overview_period(db: Session, since: datetime, until: datetime) -> AdminOverviewPeriodMetrics:
    figs = _period_figures(db, since, until)
    new_buyers = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.buyer, User.created_at >= since, User.created_at < until)
        .scalar() or 0
    )
    new_sellers = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.seller, User.created_at >= since, User.created_at < until)
        .scalar() or 0
    )
    new_products = (
        db.query(func.count(Product.id))
        .filter(Product.created_at >= since, Product.created_at < until)
        .scalar() or 0
    )
    sales = dashboard_metrics.get_sales_demand_metrics(db, since, until)
    return AdminOverviewPeriodMetrics(
        revenue=figs.revenue,
        orders=figs.orders,
        average_order_value=figs.average_order_value,
        new_users=figs.new_users,
        new_buyers=new_buyers,
        new_sellers=new_sellers,
        new_shops=figs.new_shops,
        new_products=new_products,
        cart_abandonment_rate=sales["cart_abandonment_rate"],
    )


@router.get("/stats/overview", response_model=AdminOverviewRead)
def get_stats_overview(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(14, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    prev_since, prev_until = _previous_bounds(since, until)

    metrics = _overview_period(db, since, until)
    previous = _overview_period(db, prev_since, prev_until)

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_buyers = db.query(func.count(User.id)).filter(User.role == UserRole.buyer).scalar() or 0
    total_sellers = db.query(func.count(User.id)).filter(User.role == UserRole.seller).scalar() or 0
    total_shops = db.query(func.count(Shop.id)).scalar() or 0
    shops_pending = db.query(func.count(Shop.id)).filter(Shop.status == ShopStatus.pending).scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0

    paid_groups = db.query(OrderGroup).filter(OrderGroup.status == OrderGroupStatus.paid)
    total_orders = paid_groups.count()
    revenue_total = sum((Decimal(g.total) for g in paid_groups.all()), Decimal("0"))

    return AdminOverviewRead(
        period=period or "days",
        start=since,
        metrics=metrics,
        previous=previous,
        totals=AdminOverviewTotals(
            total_users=total_users,
            total_buyers=total_buyers,
            total_sellers=total_sellers,
            total_shops=total_shops,
            shops_pending_verification=shops_pending,
            total_products=total_products,
            total_orders=total_orders,
            revenue_total=str(revenue_total),
        ),
        trend=_trend_points(db, 14),
    )


# ── Analytics ────────────────────────────────────────────────────────────────

PERIOD_PATTERN = "^(today|yesterday|week|month)$"


def _period_bounds(period: Optional[str], days: int) -> tuple[datetime, datetime]:
    """Map a filter preset to a closed-open window [since, until) in Kenyan time."""
    now = datetime.now(EAT)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period is None:
        return now - timedelta(days=days), now
    if period == "today":
        return today_start, now
    if period == "yesterday":
        return today_start - timedelta(days=1), today_start
    if period == "week":
        return now - timedelta(days=7), now
    return now - timedelta(days=30), now


def _previous_bounds(since: datetime, until: datetime) -> tuple[datetime, datetime]:
    """The like-for-like period immediately before [since, until)."""
    span = until - since
    return since - span, since


def _trend_points(db: Session, days: int) -> List[AdminTrendPoint]:
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


@router.get("/metrics/merchants", response_model=MerchantActivityMetrics)
def get_merchant_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_merchant_activity_metrics(db, since, until)


@router.get("/metrics/sales", response_model=SalesDemandMetrics)
def get_sales_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_sales_demand_metrics(db, since, until)


@router.get("/metrics/retention", response_model=CustomerRetentionMetrics)
def get_retention_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_customer_retention_metrics(db, since, until)


@router.get("/metrics/operations", response_model=OperationsDeliveryMetrics)
def get_operations_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_operations_delivery_metrics(db, since, until)


@router.get("/metrics/cart", response_model=CartAbandonmentMetrics)
def get_cart_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_cart_abandonment_metrics(db, since, until)


@router.get("/metrics/merchant-master-health", response_model=List[MerchantMasterHealth])
def get_merchant_master_health(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_merchant_master_health(db, since, until)


@router.get("/metrics/order-control-tower", response_model=List[OrderControlTowerRow])
def get_order_control_tower(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_order_control_tower(db, since, until)


@router.get("/metrics/customer-recovery", response_model=List[CustomerRecoveryRow])
def get_customer_recovery(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_customer_recovery_engine(db, since, until)


@router.get("/metrics/supply-demand", response_model=List[SupplyDemandRow])
def get_supply_demand(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_supply_demand_matrix(db, since, until)


@router.get("/metrics/margin-leakage", response_model=MarginLeakageMetrics)
def get_margin_leakage(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_margin_leakage_metrics(db, since, until)


@router.get("/reports/margin-leakage.csv")
def export_margin_leakage_csv(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    metrics = dashboard_metrics.get_margin_leakage_metrics(db, since, until)
    lines = [
        "label,gmv,platform_commission,mpesa_fees,net_profit,gross_margin_pct,aov",
    ]
    for point in metrics.get("trend", []):
        lines.append(
            f"{point['label']},{point['gmv']:.2f},{point['platform_commission']:.2f},{point['mpesa_fees']:.2f},{point['net_profit']:.2f},{point['gross_margin_pct']:.2f},{point['aov']:.2f}"
        )
    csv_content = "\n".join(lines) + "\n"
    return Response(content=csv_content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=margin-leakage.csv"})


@router.get("/reports/margin-leakage.pdf")
def export_margin_leakage_pdf(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    metrics = dashboard_metrics.get_margin_leakage_metrics(db, since, until)
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 8, "Ekshop Kenya - Margin Leakage Report", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Period: {metrics.get('period')} | Orders: {metrics.get('orders')} | AOV: KES {metrics.get('average_order_value')}", ln=True)
        pdf.ln(2)
        pdf.cell(0, 6, f"GMV: KES {metrics.get('gmv')} | Platform commission: KES {metrics.get('platform_commission')} | M-Pesa fees: KES {metrics.get('mpesa_fees')} | Net profit: KES {metrics.get('net_profit')} | Gross margin: {metrics.get('gross_margin_pct')}%", ln=True)
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(40, 8, "Day", border=1)
        pdf.cell(35, 8, "GMV", border=1, align="R")
        pdf.cell(35, 8, "Commission", border=1, align="R")
        pdf.cell(35, 8, "M-Pesa", border=1, align="R")
        pdf.cell(35, 8, "Net profit", border=1, align="R")
        pdf.cell(0, 8, "Margin %", border=1, align="R", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for point in metrics.get("trend", []):
            pdf.cell(40, 8, str(point.get("label", "")), border=1)
            pdf.cell(35, 8, f"KES {point.get('gmv', 0):.2f}", border=1, align="R")
            pdf.cell(35, 8, f"KES {point.get('platform_commission', 0):.2f}", border=1, align="R")
            pdf.cell(35, 8, f"KES {point.get('mpesa_fees', 0):.2f}", border=1, align="R")
            pdf.cell(35, 8, f"KES {point.get('net_profit', 0):.2f}", border=1, align="R")
            pdf.cell(0, 8, f"{point.get('gross_margin_pct', 0):.2f}%", border=1, align="R", ln=True)
        pdf_bytes = bytes(pdf.output())
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=margin-leakage.pdf"})
    except Exception:
        html = f"""
        <html>
          <head><title>Ekshop Margin Leakage Report</title></head>
          <body>
            <h1>Ekshop Kenya - Margin Leakage Report</h1>
            <p>Period: {metrics.get('period')} | Orders: {metrics.get('orders')} | AOV: KES {metrics.get('average_order_value')}</p>
            <p>GMV: KES {metrics.get('gmv')} | Platform commission: KES {metrics.get('platform_commission')} | M-Pesa fees: KES {metrics.get('mpesa_fees')} | Net profit: KES {metrics.get('net_profit')} | Gross margin: {metrics.get('gross_margin_pct')}%</p>
            <table border="1" cellpadding="4" cellspacing="0">
              <tr><th>Day</th><th>GMV</th><th>Commission</th><th>M-Pesa</th><th>Net profit</th><th>Margin %</th></tr>
              {"".join(f"<tr><td>{p.get('label','')}</td><td>KES {p.get('gmv',0):.2f}</td><td>KES {p.get('platform_commission',0):.2f}</td><td>KES {p.get('mpesa_fees',0):.2f}</td><td>KES {p.get('net_profit',0):.2f}</td><td>{p.get('gross_margin_pct',0):.2f}%</td></tr>" for p in metrics.get('trend', []))}
            </table>
          </body>
        </html>
        """
        return Response(content=html, media_type="text/html", headers={"Content-Disposition": "attachment; filename=margin-leakage.html"})


@router.post("/alerts/check-thresholds")
def check_admin_thresholds(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since = datetime.now(timezone.utc) - timedelta(days=1)
    metrics = get_margin_leakage_metrics(db, since)
    alerts = []
    margin_pct = float(metrics.get("gross_margin_pct", 100))
    if margin_pct < settings.ALERT_MIN_GROSS_MARGIN_PCT:
        alerts.append({
            "level": "high",
            "metric": "gross_margin_pct",
            "message": f"Gross margin dropped to {margin_pct:.2f}% (threshold {settings.ALERT_MIN_GROSS_MARGIN_PCT}%)",
        })
    return {"alerts": alerts, "checked_at": datetime.now(timezone.utc).isoformat(), "margin_pct": margin_pct}


@router.get("/metrics/priority-acquisition", response_model=List[PriorityAcquisitionRow])
def get_priority_acquisition(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_priority_acquisition(db, since, until)


@router.get("/metrics/real-time", response_model=RealTimeMetrics)
def get_real_time_metrics(
    minutes: int = Query(15, ge=1, le=60),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return dashboard_metrics.get_real_time_metrics(db, since)


@router.get("/metrics/acquisition", response_model=AcquisitionMetrics)
def get_acquisition_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_acquisition_metrics(db, since, until)


@router.get("/metrics/behavior", response_model=BehaviorMetrics)
def get_behavior_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_behavior_metrics(db, since, until)


@router.get("/metrics/ecommerce", response_model=EcommerceMetrics)
def get_ecommerce_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, days)
    return dashboard_metrics.get_ecommerce_metrics(db, since, until)


# ── Drill-down lists (click a stat card, see the rows behind it) ─────────────

@router.get("/orders", response_model=RecentOrderListResponse)
def list_recent_orders(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, 30)
    query = (
        db.query(OrderGroup)
        .options(
            selectinload(OrderGroup.buyer),
            selectinload(OrderGroup.orders).selectinload(Order.items),
        )
        .filter(OrderGroup.status == OrderGroupStatus.paid)
    )
    if period is not None:
        query = query.filter(OrderGroup.created_at >= since, OrderGroup.created_at < until)
    total = query.count()
    skip = (page - 1) * limit
    rows = query.order_by(OrderGroup.created_at.desc()).offset(skip).limit(limit).all()
    results = [
        RecentOrderRow(
            id=str(g.id),
            short_id=str(g.id)[:8],
            created_at=g.created_at,
            buyer_name=f"{g.buyer.first_name} {g.buyer.last_name}",
            total=g.total,
            item_count=sum(len(o.items) for o in g.orders),
            shop_count=len({o.shop_id for o in g.orders}),
        )
        for g in rows
    ]
    return RecentOrderListResponse(total=total, page=page, limit=limit, results=results)


@router.get("/products", response_model=AdminProductListResponse)
def list_admin_products(
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(Product).options(selectinload(Product.shop))
    total = q.count()
    skip = (page - 1) * limit
    rows = q.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()
    return AdminProductListResponse(
        total=total,
        page=page,
        limit=limit,
        results=[
            AdminProductRow(
                id=p.id,
                name=p.name,
                price=p.price,
                status=p.status.value if hasattr(p.status, "value") else str(p.status),
                shop_name=p.shop.name if p.shop else None,
                created_at=p.created_at,
            )
            for p in rows
        ],
    )


# ── Email delivery health ────────────────────────────────────────────────────

def _from_domain(address: str) -> str:
    at = address.rfind("@")
    if at == -1:
        return ""
    return address[at + 1:].strip().rstrip(">").strip()


@router.get("/email/status", response_model=AdminEmailStatus)
def get_email_status(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    from_domain = _from_domain(settings.EMAIL_FROM)
    verified: list = []
    domains_error: Optional[str] = None
    try:
        verified = sorted(
            d["name"]
            for d in email_service.resend_sending_domains()
            if d.get("status") == "verified"
        )
    except Exception as e:
        domains_error = str(e)

    active_recipients = (
        db.query(func.count(OrderNotificationRecipient.id))
        .filter(OrderNotificationRecipient.is_active.is_(True))
        .scalar()
        or 0
    )

    return AdminEmailStatus(
        resend_configured=bool(settings.RESEND_API_KEY),
        from_address=settings.EMAIL_FROM,
        from_domain=from_domain,
        verified_domains=verified,
        from_domain_verified=bool(from_domain) and from_domain in verified,
        domains_error=domains_error,
        active_recipient_count=active_recipients,
    )


@router.post("/email/test", response_model=AdminEmailTestResult)
def send_admin_test_email(
    payload: AdminEmailTestRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    try:
        email_service.send_test_email(payload.to)
    except Exception as e:
        logger.warning("Admin email test to %s failed: %s", payload.to, e)
        return AdminEmailTestResult(success=False, detail=str(e))
    return AdminEmailTestResult(
        success=True,
        detail=f"Test email sent to {payload.to}. If it doesn't arrive, check spam and Resend's delivery log.",
    )


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


# ── Order notification recipients ───────────────────────────────────────────

@router.get("/order-notification-recipients", response_model=List[OrderNotificationRecipientRead])
def list_order_notification_recipients(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return (
        db.query(OrderNotificationRecipient)
        .order_by(OrderNotificationRecipient.created_at.desc())
        .all()
    )


@router.post(
    "/order-notification-recipients",
    response_model=OrderNotificationRecipientRead,
    status_code=status.HTTP_201_CREATED,
)
def create_order_notification_recipient(
    payload: OrderNotificationRecipientCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = (
        db.query(OrderNotificationRecipient)
        .filter(OrderNotificationRecipient.email == payload.email)
        .first()
    )
    if existing:
        raise HTTPException(400, "This email is already a recipient")
    recipient = OrderNotificationRecipient(**payload.model_dump())
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    return recipient


@router.patch("/order-notification-recipients/{recipient_id}", response_model=OrderNotificationRecipientRead)
def update_order_notification_recipient(
    recipient_id: uuid.UUID,
    payload: OrderNotificationRecipientUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    recipient = db.query(OrderNotificationRecipient).filter(OrderNotificationRecipient.id == recipient_id).first()
    if not recipient:
        raise HTTPException(404, "Recipient not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(recipient, field, value)
    db.commit()
    db.refresh(recipient)
    return recipient


@router.delete("/order-notification-recipients/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order_notification_recipient(
    recipient_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    recipient = db.query(OrderNotificationRecipient).filter(OrderNotificationRecipient.id == recipient_id).first()
    if not recipient:
        raise HTTPException(404, "Recipient not found")
    db.delete(recipient)
    db.commit()


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
