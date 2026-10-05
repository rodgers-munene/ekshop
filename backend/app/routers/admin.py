import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import Numeric, cast, func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.payment import Payment, PaymentStatus

from app.core.config import settings
from app.dependencies.auth import require_admin
from app.dependencies.database import get_db
from app.models.commerce import (
    OrderGroup,
    OrderGroupStatus,
    Order,
    OrderItem,
    OrderStatus,
)
from app.models.catalog import Product, Category
from app.services.fraud import FraudDetectionService, evaluate_order_fraud, get_high_risk_orders
from app.models.delivery import Delivery, DeliveryStatus
from app.models.order_notifications import OrderNotificationRecipient
from app.models.shop import Shop, ShopStatus
from app.models.user import User, UserRole, UserStatus
from app.models.analytics import HeroSlide, Promotion
from app.schemas.admin import (
    AdminEmailStatus,
    AdminEmailTestRequest,
    AdminEmailTestResult,
    AdminOverviewPeriodMetrics,
    AdminOverviewRead,
    AdminOverviewTotals,
    AdminProductListResponse,
    AdminProductRow,
    AdminStatsRead,
    AdminTrendPoint,
    PayerActivity,
    PayerActivityRead,
    ChurnOutreachRequest,
    ChurnOutreachResult,
    CartAbandonmentMetrics,
    CustomerRecoveryRow,
    CustomerRetentionMetrics,
    EcommerceMetrics,
    AcquisitionMetrics,
    BehaviorMetrics,
    HeroSlideCreate,
    HeroSlideRead,
    HeroSlideUpdate,
    MerchantActivityMetrics,
    MarginLeakageMetrics,
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
from app.schemas.shop import ShopRead
from app.schemas.user import UserRead
from app.schemas.automation import AutomationSettingsRead, AutomationSettingsUpdate
from app.services import storage
from app.services import email as email_service
from app.services import dashboard_metrics, reports
from app.services import automation as automation_service
from app.services.dashboard_metrics import (
    get_cart_abandonment_metrics,
    get_margin_leakage_metrics,
    get_operations_delivery_metrics,
    get_sales_demand_metrics,
)
import html
import logging

logger = logging.getLogger(__name__)

PERIOD_PATTERN = "^(today|yesterday|week|month|custom)$"

# Longest custom window allowed. A year keeps a single query bounded; an
# unbounded range on an analytics endpoint is how one admin click becomes a
# sequential scan over the whole order table.
MAX_CUSTOM_DAYS = 366


def _resolve_window(
    period: Optional[str],
    days: int,
    date_from: Optional[date],
    date_to: Optional[date],
) -> tuple[datetime, datetime, str]:
    """Resolve the requested window to `[since, until)` plus the label to report.

    An explicit `date_from`/`date_to` pair wins over the `period` preset, so a
    saved link to a specific range keeps working even if the presets change.
    Both bounds are inclusive as dates: asking for 1st to 3rd returns the whole of
    the 3rd, not up to midnight on it.
    """
    if date_from is not None or date_to is not None:
        if date_from is not None and date_to is not None:
            start_date, end_date = date_from, date_to
        elif date_from is not None:
            # Only a start: treat `days` as the span forwards from it.
            start_date, end_date = date_from, date_from + timedelta(days=days - 1)
        else:
            # Only an end: treat `days` as the span back from it.
            start_date, end_date = date_to - timedelta(days=days - 1), date_to
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        span = (end_date - start_date).days + 1
        if span > MAX_CUSTOM_DAYS:
            raise HTTPException(
                status_code=422,
                detail=f"Date range too wide: {span} days. The maximum is {MAX_CUSTOM_DAYS}.",
            )
        since = datetime.combine(start_date, time.min, tzinfo=EAT)
        until = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=EAT)
        return since, until, f"{start_date.isoformat()} to {end_date.isoformat()}"
    since, until = _period_bounds(period, days)
    return since, until, period or "days"


def custom_range_params():
    """Query parameters for a custom date range.

    A function so every endpoint takes the same pair with the same names and
    validation, rather than twenty-two endpoints each inventing their own.
    """
    return (
        Query(None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."),
        Query(None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."),
    )


# ── Money basis ──────────────────────────────────────────────────────────────
#
# Everything below counts MONEY THAT ARRIVED, not orders that were typed.
#
# The dashboard used to filter on `OrderGroup.created_at`, which is when the
# order was placed. For M-Pesa that is simply a different question: an STK push
# can sit pending, be retried, or resolve through a delayed callback hours later.
# So "what happened yesterday" was answered with orders *placed* yesterday,
# which excluded money that landed yesterday from an order placed on Tuesday,
# and included orders placed yesterday that have not been paid yet. The
# `payments` table has been recording `paid_at`, `user_id` and `provider_ref`
# the whole time; nothing read it.
#
# `paid_at` was itself never assigned by any code path until now, so it is
# backfilled from `created_at` by migration c9d0e1f2a3b4. The coalesce keeps
# this correct for rows written before that migration and for any provider that
# succeeds without a timestamp.


def money_instant():
    """When a payment's money actually landed."""
    return func.coalesce(Payment.paid_at, Payment.created_at)


def _successful_payments(db: Session, start: datetime, end: datetime):
    return db.query(Payment).filter(
        Payment.status == PaymentStatus.success,
        money_instant() >= start,
        money_instant() < end,
    )


def _refunds_between(db: Session, start: datetime, end: datetime) -> Decimal:
    refunded = (
        db.query(func.coalesce(func.sum(cast(Payment.amount, Numeric)), 0))
        .filter(
            Payment.status == PaymentStatus.refunded,
            money_instant() >= start,
            money_instant() < end,
        )
        .scalar()
    )
    return Decimal(refunded or 0).quantize(Decimal("0.01"))


def _paid_money_between(db: Session, start: datetime, end: datetime) -> dict:
    """The money figures for a window, on the basis of payments received.

    Deliberately two different aggregations, because they answer different
    questions and conflating them is what made the old figures untrustworthy:

    - `cash_received` sums payment rows, so it is real cash movement.
    - `gmv` and `total_transacted` sum *distinct order groups* that have a
      successful payment in the window. A retried STK push can leave more than
      one successful row against the same order (each provider_ref is unique,
      but the refs differ), and summing per row would inflate the basket figures
      and make GMV exceed what was actually taken.

    Refunds are reported rather than silently netted off, because a refund is
    the answer to "are we winning or losing".
    """
    cash_received = (
        db.query(func.coalesce(func.sum(cast(Payment.amount, Numeric)), 0))
        .select_from(Payment)
        .filter(
            Payment.status == PaymentStatus.success,
            money_instant() >= start,
            money_instant() < end,
        )
        .scalar()
    )
    cash_total = Decimal(cash_received or 0).quantize(Decimal("0.01"))

    # Distinct order groups behind those payments.
    paid_groups = (
        db.query(Payment.order_group_id.label("order_group_id"))
        .filter(
            Payment.status == PaymentStatus.success,
            money_instant() >= start,
            money_instant() < end,
        )
        .distinct()
        .subquery()
    )

    transacted, orders = (
        db.query(
            func.coalesce(func.sum(cast(OrderGroup.total, Numeric)), 0),
            func.count(OrderGroup.id),
        )
        .join(paid_groups, paid_groups.c.order_group_id == OrderGroup.id)
        .one()
    )
    total_transacted = Decimal(transacted or 0).quantize(Decimal("0.01"))

    gmv = (
        db.query(func.coalesce(func.sum(cast(OrderItem.line_total, Numeric)), 0))
        .select_from(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(paid_groups, paid_groups.c.order_group_id == Order.group_id)
        .scalar()
    )
    gmv_total = Decimal(gmv or 0).quantize(Decimal("0.01"))

    return {
        "gmv": gmv_total,
        "total_transacted": total_transacted,
        "orders": orders,
        "cash_received": cash_total,
        "refunds": _refunds_between(db, start, end),
        "revenue": _commission(gmv_total),
    }


router = APIRouter(prefix="/admin", tags=["admin"])


# ── Stats ────────────────────────────────────────────────────────────────────

# Month/year boundaries are Kenyan calendar boundaries, not UTC ones — an
# order placed at 01:00 EAT on the 1st belongs to the new month. Kenya is a
# fixed UTC+3 with no DST, so a fixed offset is exact (see services/mpesa.py).
EAT = timezone(timedelta(hours=3), "EAT")


def _commission(gmv: Decimal) -> Optional[str]:
    """Platform revenue: commission on goods value.

    Returns None when no rate is configured. The dashboard used to show a
    hardcoded 10% here, which meant the number looked measured but was invented --
    and it appeared beside a "GMV" figure that was really the basket total, so
    the two told different stories.
    """
    rate = settings.PLATFORM_COMMISSION_RATE
    if rate is None:
        return None
    return str((gmv * Decimal(rate)).quantize(Decimal("0.01")))


def _period_figures(db: Session, start: datetime, end: datetime) -> PeriodFigures:
    money = _paid_money_between(db, start, end)
    revenue = money["revenue"]
    aov = (
        (money["total_transacted"] / money["orders"]).quantize(Decimal("0.01"))
        if money["orders"]
        else Decimal("0.00")
    )

    new_users = (
        db.query(func.count(User.id)).filter(User.created_at >= start, User.created_at < end).scalar() or 0
    )
    new_shops = (
        db.query(func.count(Shop.id)).filter(Shop.created_at >= start, Shop.created_at < end).scalar() or 0
    )

    return PeriodFigures(
        gmv=str(money["gmv"]),
        total_transacted=str(money["total_transacted"]),
        revenue=revenue,
        commission_rate_configured=settings.PLATFORM_COMMISSION_RATE is not None,
        orders=money["orders"],
        average_order_value=str(aov),
        new_users=new_users,
        new_shops=new_shops,
        cash_received=str(money["cash_received"]),
        refunds=str(money["refunds"]),
        basis="payments",
        basis_note=None,
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

    # Counted as **order groups** (baskets) behind a successful payment, on the
    # same basis as every money figure below and as the orders list, so a basket
    # count, a money figure and a list length cannot disagree. A group holds one
    # order per shop, so a shop order count is a different number.
    #
    # This used to filter on `OrderGroup.status == paid` with `created_at`, which
    # counts orders *placed* recently even if they were never paid.
    paid_group_ids = (
        db.query(Payment.order_group_id.label("gid"))
        .filter(
            Payment.status == PaymentStatus.success,
            money_instant() <= datetime.now(timezone.utc),
        )
        .distinct()
        .subquery()
    )
    total_orders = (
        db.query(func.count(OrderGroup.id))
        .join(paid_group_ids, paid_group_ids.c.gid == OrderGroup.id)
        .scalar()
        or 0
    )
    orders_7d = (
        db.query(func.count(OrderGroup.id))
        .join(paid_group_ids, paid_group_ids.c.gid == OrderGroup.id)
        .filter(
            func.timezone("Africa/Nairobi", money_instant()) >= seven_days_ago
        )
        .scalar()
        or 0
    )

    lifetime = _paid_money_between(
        db, datetime(1970, 1, 1, tzinfo=timezone.utc), datetime.now(timezone.utc)
    )
    last_7 = _paid_money_between(db, seven_days_ago, datetime.now(timezone.utc))

    # Yesterday, as a complete calendar day in EAT rather than "the last 24
    # hours", so it can be compared like-for-like against a day in the trend.
    yesterday_end = datetime.now(EAT).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = yesterday_end - timedelta(days=1)
    yesterday = _paid_money_between(db, yesterday_start, yesterday_end)

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
        gmv_total=str(lifetime["gmv"]),
        total_transacted_total=str(lifetime["total_transacted"]),
        gmv_7d=str(last_7["gmv"]),
        total_transacted_7d=str(last_7["total_transacted"]),
        revenue_total=lifetime["revenue"],
        revenue_7d=last_7["revenue"],
        commission_rate_configured=settings.PLATFORM_COMMISSION_RATE is not None,
        orders_yesterday=yesterday["orders"],
        gmv_yesterday=str(yesterday["gmv"]),
        total_transacted_yesterday=str(yesterday["total_transacted"]),
        cash_received_yesterday=str(yesterday["cash_received"]),
        refunds_yesterday=str(yesterday["refunds"]),
        cash_received_total=str(lifetime["cash_received"]),
        refunds_total=str(lifetime["refunds"]),
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
        gmv=figs.gmv,
        total_transacted=figs.total_transacted,
        revenue=figs.revenue,
        commission_rate_configured=figs.commission_rate_configured,
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
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, label = _resolve_window(period, days, date_from, date_to)
    prev_since, prev_until = _previous_bounds(since, until)

    metrics = _overview_period(db, since, until)
    previous = _overview_period(db, prev_since, prev_until)

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_buyers = db.query(func.count(User.id)).filter(User.role == UserRole.buyer).scalar() or 0
    total_sellers = db.query(func.count(User.id)).filter(User.role == UserRole.seller).scalar() or 0
    total_shops = db.query(func.count(Shop.id)).scalar() or 0
    shops_pending = db.query(func.count(Shop.id)).filter(Shop.status == ShopStatus.pending).scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0

    # Lifetime totals on the same basis as the period figures, so the header and
    # the period panel cannot disagree about what "GMV" means.
    lifetime = _paid_money_between(
        db, datetime(1970, 1, 1, tzinfo=timezone.utc), datetime.now(timezone.utc)
    )
    total_orders = lifetime["orders"]

    return AdminOverviewRead(
        period=label,
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
            gmv_total=str(lifetime["gmv"]),
            total_transacted_total=str(lifetime["total_transacted"]),
            revenue_total=lifetime["revenue"],
            commission_rate_configured=settings.PLATFORM_COMMISSION_RATE is not None,
            cash_received_total=str(lifetime["cash_received"]),
            refunds_total=str(lifetime["refunds"]),
        ),
        trend=_trend_points(db, 14),
    )


# ── Analytics ────────────────────────────────────────────────────────────────


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
    """Daily paid figures, bucketed by the day the money arrived.

    Bucketing on `OrderGroup.created_at` put a day on the chart for orders that
    were placed that day but never paid, and left out orders that were placed
    earlier and paid that day. So the line could rise on a day with no takings.
    These points come off the payments table, on the same basis as the header
    cards, and each order group is counted once.

    GMV is aggregated from line items in its own query because it cannot be
    derived from `OrderGroup.total` -- that figure includes delivery and tax.
    Both series are returned so the chart can plot them as separate lines rather
    than showing one bar relabelled twice.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days - 1)
    instant = money_instant()

    # Bucket explicitly in EAT. `date_trunc` on a timestamptz truncates in the
    # *session* timezone, so on a UTC-configured server every day would be
    # shifted three hours and the 00:00-03:00 band would land on the wrong day.
    day_col = func.date_trunc("day", func.timezone("Africa/Nairobi", instant))

    # Distinct (payment day, order group) pairs. Deduplicated per pair so a
    # retried push that left two successful rows against one order still counts
    # that basket once.
    paid_pairs = (
        db.query(
            day_col.label("day"),
            Payment.order_group_id.label("gid"),
        )
        .filter(
            Payment.status == PaymentStatus.success,
            instant >= since,
        )
        .distinct()
        .subquery()
    )

    rows = (
        db.query(
            paid_pairs.c.day.label("day"),
            func.count(OrderGroup.id).label("orders"),
            func.sum(cast(OrderGroup.total, Numeric)).label("transacted"),
        )
        .select_from(paid_pairs)
        .join(OrderGroup, OrderGroup.id == paid_pairs.c.gid)
        .group_by(paid_pairs.c.day)
        .all()
    )
    by_day = {row.day.date(): row for row in rows}

    gmv_rows = (
        db.query(
            paid_pairs.c.day.label("day"),
            func.sum(cast(OrderItem.line_total, Numeric)).label("gmv"),
        )
        .select_from(paid_pairs)
        .join(Order, Order.group_id == paid_pairs.c.gid)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .group_by(paid_pairs.c.day)
        .all()
    )
    gmv_by_day = {row.day.date(): row.gmv for row in gmv_rows}

    points: List[AdminTrendPoint] = []
    today = datetime.now(timezone.utc).date()
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        row = by_day.get(day)
        transacted = float(row.transacted) if row and row.transacted else 0.0
        gmv = float(gmv_by_day.get(day) or 0.0)
        points.append(
            AdminTrendPoint(
                label=day.strftime("%d %b"),
                # Kept for existing consumers of this endpoint.
                revenue=transacted,
                gmv=gmv,
                total_transacted=transacted,
                revenue_earned=(
                    _commission(Decimal(str(gmv))) if gmv else None
                ),
                commission_rate_configured=settings.PLATFORM_COMMISSION_RATE is not None,
                orders=int(row.orders) if row else 0,
            )
        )
    return points


@router.get("/stats/payers", response_model=PayerActivityRead)
def get_payer_activity(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(7, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Who paid, when, how much, and via which provider reference.

    Answers "what happened yesterday" at the level of an individual transaction
    rather than a total, which no other endpoint could do.
    """
    since, until, label = _resolve_window(period, days, date_from, date_to)

    total = (
        db.query(func.coalesce(func.sum(cast(Payment.amount, Numeric)), 0))
        .filter(
            Payment.status == PaymentStatus.success,
            money_instant() >= since,
            money_instant() < until,
        )
        .scalar()
    )
    payment_count, payer_count = (
        db.query(func.count(Payment.id), func.count(func.distinct(Payment.user_id)))
        .filter(
            Payment.status == PaymentStatus.success,
            money_instant() >= since,
            money_instant() < until,
        )
        .one()
    )

    rows = (
        db.query(
            Payment,
            User.first_name,
            User.last_name,
            User.email,
        )
        .join(User, User.id == Payment.user_id)
        .filter(
            Payment.status == PaymentStatus.success,
            money_instant() >= since,
            money_instant() < until,
        )
        .order_by(money_instant().desc())
        .limit(limit)
        .all()
    )

    return PayerActivityRead(
        period=label,
        start=since,
        end=until,
        total_cash_received=str(Decimal(total or 0).quantize(Decimal("0.01"))),
        payment_count=int(payment_count or 0),
        payer_count=int(payer_count or 0),
        results=[
            PayerActivity(
                payment_id=str(payment.id),
                order_group_id=str(payment.order_group_id),
                user_id=str(payment.user_id),
                first_name=first_name or "",
                last_name=last_name or "",
                email=email or "",
                provider=payment.provider,
                provider_ref=payment.provider_ref,
                channel=payment.channel,
                amount=str(Decimal(payment.amount or "0").quantize(Decimal("0.01"))),
                # Resolved in Python because the row object is already loaded;
                # `money_instant()` is a SQL expression and would serialise the
                # expression text into the response.
                paid_at=payment.paid_at or payment.created_at,
            )
            for payment, first_name, last_name, email in rows
        ],
    )


@router.get("/metrics/merchants", response_model=MerchantActivityMetrics)
def get_merchant_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(7, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_merchant_activity_metrics(db, since, until)


@router.get("/metrics/sales", response_model=SalesDemandMetrics)
def get_sales_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_sales_demand_metrics(db, since, until)


@router.get("/metrics/retention", response_model=CustomerRetentionMetrics)
def get_retention_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_customer_retention_metrics(db, since, until)


@router.get("/metrics/operations", response_model=OperationsDeliveryMetrics)
def get_operations_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_operations_delivery_metrics(db, since, until)


@router.get("/metrics/cart", response_model=CartAbandonmentMetrics)
def get_cart_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_cart_abandonment_metrics(db, since, until)


@router.get("/metrics/merchant-master-health", response_model=List[MerchantMasterHealth])
def get_merchant_master_health(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_merchant_master_health(db, since, until)


@router.get("/metrics/order-control-tower", response_model=List[OrderControlTowerRow])
def get_order_control_tower(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_order_control_tower(db, since, until)


@router.get("/metrics/customer-recovery", response_model=List[CustomerRecoveryRow])
def get_customer_recovery(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_customer_recovery_engine(db, since, until)


@router.get("/metrics/supply-demand", response_model=List[SupplyDemandRow])
def get_supply_demand(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_supply_demand_matrix(db, since, until)


@router.get("/metrics/margin-leakage", response_model=MarginLeakageMetrics)
def get_margin_leakage(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_margin_leakage_metrics(db, since, until)


@router.get("/reports/margin-leakage.csv")
def export_margin_leakage_csv(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    metrics = dashboard_metrics.get_margin_leakage_metrics(db, since, until)
    def cell(value, suffix: str = "") -> str:
        """Unset rates export as an empty cell, never as 0.00 -- a zero would
        read as 'this cost nothing'."""
        return f"{value:.2f}{suffix}" if isinstance(value, (int, float)) else ""

    lines = [
        "label,gmv,platform_commission,mpesa_fees,net_profit,gross_margin_pct,aov",
    ]
    for point in metrics.get("trend", []):
        lines.append(
            f"{point['label']},{cell(point['gmv'])},{cell(point['platform_commission'])},"
            f"{cell(point['mpesa_fees'])},{cell(point['net_profit'])},"
            f"{cell(point['gross_margin_pct'])},{cell(point['aov'])}"
        )
    csv_content = "\n".join(lines) + "\n"
    return Response(content=csv_content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=margin-leakage.csv"})


@router.get("/reports/margin-leakage.pdf")
def export_margin_leakage_pdf(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, label = _resolve_window(period, days, date_from, date_to)
    summary = reports.build_trading_summary(db, since, until, label)
    try:
        pdf_bytes = reports.render_pdf(summary)
    except ImportError:
        # fpdf2 is optional. Only its absence is caught here -- a genuine layout
        # or arithmetic error used to be swallowed by a bare `except Exception`,
        # which returned an HTML file and made a broken PDF look like a working
        # export with a different format.
        return Response(
            content=reports.render_html(summary),
            media_type="text/html",
            headers={"Content-Disposition": "attachment; filename=trading-report.html"},
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=trading-report.pdf"},
    )


@router.get("/reports/trading-report.html")
def export_trading_report_html(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, label = _resolve_window(period, days, date_from, date_to)
    return Response(
        content=reports.render_html(reports.build_trading_summary(db, since, until, label)),
        media_type="text/html",
        headers={"Content-Disposition": "attachment; filename=trading-report.html"},
    )


@router.get("/reports/yesterday")
def yesterday_report(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """The standing question: what happened yesterday.

    Yesterday as a complete EAT calendar day, so it matches a point on the
    trend and can be quoted verbatim without anyone having to guess whether the
    figure covers 24 hours or midnight-to-midnight.
    """
    yesterday = datetime.now(EAT).date() - timedelta(days=1)
    start, end, label = reports.daily_window(yesterday)
    summary = reports.build_trading_summary(db, start, end, label)
    return {
        "period": label,
        "verdict": summary.verdict,
        "cash_received": str(summary.cash_received),
        "refunds": str(summary.refunds),
        "net_cash": str(summary.net_cash),
        "gmv": str(summary.gmv),
        "total_transacted": str(summary.total_transacted),
        "orders": summary.orders,
        "payments": summary.payments,
        "payers": summary.payers,
        "new_customers": summary.new_customers,
        "average_order_value": str(summary.average_order_value),
        "platform_revenue": (
            str(summary.platform_revenue)
            if summary.platform_revenue is not None
            else None
        ),
        "commission_rate_configured": summary.commission_rate is not None,
        "mpesa_fees": (
            str(summary.mpesa_fees) if summary.mpesa_fees is not None else None
        ),
        "server_costs": (
            str(summary.server_costs) if summary.server_costs is not None else None
        ),
        "net": str(summary.net) if summary.net is not None else None,
        "net_note": summary.net_note.strip() or None,
        "html_url": f"/admin/reports/trading-report.html?date_from={yesterday.isoformat()}&date_to={yesterday.isoformat()}",
    }


@router.post("/alerts/check-thresholds")
def check_admin_thresholds(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since = datetime.now(timezone.utc) - timedelta(days=1)
    now = datetime.now(timezone.utc)
    alerts = []

    automation = automation_service.get_or_create_automation_settings(db)
    min_margin = automation.alert_min_gross_margin_pct
    max_cancel = automation.alert_max_order_cancellation_rate
    max_abandon = automation.alert_max_cart_abandonment_rate
    min_delivery = automation.alert_min_on_time_delivery_rate

    margin = get_margin_leakage_metrics(db, since)
    margin_pct = float(margin.get("gross_margin_pct", 100))
    if automation.alert_gross_margin_enabled and margin_pct < min_margin:
        alerts.append({
            "level": "high",
            "metric": "gross_margin_pct",
            "message": f"Gross margin dropped to {margin_pct:.2f}% (threshold {min_margin}%)",
        })

    sales = get_sales_demand_metrics(db, since, now)
    cancellation_rate = float(sales.get("order_cancellation_rate", 0))
    if automation.alert_order_cancellation_enabled and cancellation_rate > max_cancel:
        alerts.append({
            "level": "medium",
            "metric": "order_cancellation_rate",
            "message": f"Order cancellation rate is {cancellation_rate:.2f}% (threshold {max_cancel}%)",
        })

    cart = get_cart_abandonment_metrics(db, since, now)
    abandonment_rate = float(cart.get("cart_abandonment_rate", 0))
    if automation.alert_cart_abandonment_enabled and abandonment_rate > max_abandon:
        alerts.append({
            "level": "medium",
            "metric": "cart_abandonment_rate",
            "message": f"Cart abandonment rate is {abandonment_rate:.2f}% (threshold {max_abandon}%)",
        })

    ops = get_operations_delivery_metrics(db, since, now)
    on_time = ops.get("on_time_delivery_rate")
    if automation.alert_on_time_delivery_enabled and on_time is not None and float(on_time) < min_delivery:
        alerts.append({
            "level": "high",
            "metric": "on_time_delivery_rate",
            "message": f"On-time delivery rate is {float(on_time):.2f}% (threshold {min_delivery}%)",
        })

    return {"alerts": alerts, "checked_at": datetime.now(timezone.utc).isoformat(), "margin_pct": margin_pct}


@router.get("/automation/settings", response_model=AutomationSettingsRead)
def get_automation_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return automation_service.get_or_create_automation_settings(db)


@router.put("/automation/settings", response_model=AutomationSettingsRead)
def update_automation_settings(
    payload: AutomationSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    settings = automation_service.get_or_create_automation_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/metrics/priority-acquisition", response_model=List[PriorityAcquisitionRow])
def get_priority_acquisition(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_priority_acquisition(db, since, until)


# NOTE: /metrics/real-time deliberately does NOT live here. It used to, and it
# reported active_sessions by counting UserEvent rows -- a behavioural analytics
# table written only for purchases and product views -- so it read zero with the
# site open. It now reads the in-memory presence registry and lives in
# app/routers/presence.py. Two routes on one path would be ambiguous.


@router.get("/metrics/acquisition", response_model=AcquisitionMetrics)
def get_acquisition_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_acquisition_metrics(db, since, until)


@router.get("/metrics/behavior", response_model=BehaviorMetrics)
def get_behavior_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
    return dashboard_metrics.get_behavior_metrics(db, since, until)


@router.get("/metrics/ecommerce", response_model=EcommerceMetrics)
def get_ecommerce_metrics(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    days: int = Query(30, ge=1, le=365),
    date_from: Optional[date] = Query(
        None, description="Inclusive start date, YYYY-MM-DD. Overrides `period`."
    ),
    date_to: Optional[date] = Query(
        None, description="Inclusive end date, YYYY-MM-DD. Overrides `period`."
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until, _label = _resolve_window(period, days, date_from, date_to)
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
    # Orders with no delivery row yet, PLUS those whose delivery is still
    # pending (auto-dispatch tried on payment but no rider accepted). Orders a
    # rider already claimed (assigned+) stop being listed here.
    query = (
        db.query(Order)
        .outerjoin(Delivery, Delivery.order_id == Order.id)
        .filter(
            Order.status.in_([OrderStatus.confirmed, OrderStatus.processing]),
            or_(
                Delivery.id.is_(None),
                Delivery.status == DeliveryStatus.pending,
            ),
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


@router.get("/metrics/top-merchants")
def get_top_merchants_insight(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, 30)
    return dashboard_metrics.get_top_merchants_insight(db, since, until)


@router.get("/metrics/churn-risks")
def get_churn_risks_insight(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, 30)
    return dashboard_metrics.get_churn_risks_insight(db, since, until)


@router.post("/churn/outreach", response_model=ChurnOutreachResult)
def send_churn_outreach(
    payload: ChurnOutreachRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Email selected churn-risk customers a win-back message.

    Email rather than SMS: there is no SMS provider configured anywhere in this
    service, so a "text these customers" button could only have been a dead end.
    `User.phone` exists, but nothing can send to it.

    Two guards, both because an admin screen is a stale snapshot:

    - The batch is capped, so this cannot become an accidental mass send.
    - Every id is re-checked against the churn query at send time. Someone who
      ordered this morning must not be told they have been away, even if they
      were on the list when the admin looked at it.
    """
    if len(payload.user_ids) > 100:
        raise HTTPException(
            status_code=422,
            detail="At most 100 recipients per batch. Send in batches instead.",
        )

    # Re-derive the at-risk set now, not from whatever the client sent.
    since, _until = _period_bounds("month", 30)
    at_risk = {
        row["user_id"]: row
        for row in dashboard_metrics.get_churn_risks_insight(db, since, None)
    }

    results: List[dict] = []
    sent = failed = skipped = 0

    for user_id in payload.user_ids:
        row = at_risk.get(user_id)
        if row is None:
            skipped += 1
            results.append(
                {
                    "user_id": user_id,
                    "status": "skipped",
                    "reason": "not in churn risk at send time (ordered recently, or not contactable)",
                }
            )
            continue

        if payload.dry_run:
            results.append(
                {
                    "user_id": user_id,
                    "email": row["email"],
                    "status": "would_send",
                    "risk": row["risk"],
                    "days_idle": row["days_idle"],
                }
            )
            continue

        # Escape the admin-supplied text before it goes anywhere near an email
        # body, so a name or an ampersand cannot break the markup.
        safe_subject = html.escape(payload.subject)
        safe_body = html.escape(payload.body).replace("\n", "<br>")
        message = f"""
            <p>Hi {html.escape(row['first_name'])},</p>
            <p>{safe_body}</p>
            <p>
              <a href="{settings.FRONTEND_URL}/products"
                 style="background:#111;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none">
                Browse what's new
              </a>
            </p>
            <p style="color:#666;font-size:12px">
              You last ordered from us on {row['last_order_at']}.
            </p>
        """
        try:
            email_service.send_notification_email(
                to=row["email"], title=safe_subject, body=message
            )
        except Exception as exc:
            failed += 1
            # Reported per recipient: a 20-recipient batch where 3 bounced must
            # not read as a total failure, nor as a total success.
            logger.error("Churn outreach to %s failed: %s", row["email"], exc)
            results.append(
                {
                    "user_id": user_id,
                    "email": row["email"],
                    "status": "failed",
                    "error": str(exc)[:200],
                }
            )
            continue

        sent += 1
        results.append(
            {
                "user_id": user_id,
                "email": row["email"],
                "status": "sent",
                "risk": row["risk"],
            }
        )

    if payload.dry_run:
        return ChurnOutreachResult(
            attempted=len(payload.user_ids),
            sent=0,
            failed=0,
            skipped_not_at_risk=skipped,
            results=results,
        )

    return ChurnOutreachResult(
        attempted=len(payload.user_ids),
        sent=sent,
        failed=failed,
        skipped_not_at_risk=skipped,
        results=results,
    )


# ── Bulk actions / CSV import-export ────────────────────────────────────────────

import csv
import io
from fastapi.responses import StreamingResponse


@router.get(
    "/orders/export",
    response_class=StreamingResponse,
    summary="Export orders as CSV",
)
def export_orders_csv(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, 30)
    query = (
        db.query(OrderGroup)
        .options(
            selectinload(OrderGroup.buyer),
            selectinload(OrderGroup.orders).selectinload(Order.items),
            selectinload(OrderGroup.orders).selectinload(Order.shop),
        )
        .filter(OrderGroup.status == OrderGroupStatus.paid)
    )
    if period is not None:
        query = query.filter(OrderGroup.created_at >= since, OrderGroup.created_at < until)
    if status:
        query = query.filter(OrderGroup.status == status)

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Order Group ID", "Short ID", "Date", "Buyer Name", "Buyer Email",
            "Buyer Phone", "Total", "Tax", "Delivery Fee", "Status",
            "Shop Count", "Item Count", "Delivery County", "Delivery Town"
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for g in query.order_by(OrderGroup.created_at.desc()).yield_per(100):
            address = g.delivery_address or {}
            writer.writerow([
                str(g.id),
                str(g.id)[:8],
                g.created_at.isoformat(),
                f"{g.buyer.first_name} {g.buyer.last_name}",
                g.buyer.email,
                g.buyer.phone or "",
                g.total,
                g.tax_amount,
                g.delivery_fee,
                g.status.value if hasattr(g.status, "value") else str(g.status),
                len({o.shop_id for o in g.orders}),
                sum(len(o.items) for o in g.orders),
                address.get("county", ""),
                address.get("town", ""),
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=orders_export_{datetime.now().strftime('%Y%m%d')}.csv"},
    )


@router.get(
    "/products/export",
    response_class=StreamingResponse,
    summary="Export products as CSV",
)
def export_products_csv(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(Product).options(selectinload(Product.shop))
    if status:
        q = q.filter(Product.status == status)

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Product ID", "Name", "Slug", "SKU", "Price", "Stock",
            "Status", "Shop", "Shop Slug", "Category", "Created At"
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for p in q.order_by(Product.created_at.desc()).yield_per(100):
            writer.writerow([
                str(p.id),
                p.name,
                p.slug,
                p.sku or "",
                p.price,
                p.stock_qty,
                p.status.value if hasattr(p.status, "value") else str(p.status),
                p.shop.name if p.shop else "",
                p.shop.slug if p.shop else "",
                p.category.name if p.category else "",
                p.created_at.isoformat(),
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=products_export_{datetime.now().strftime('%Y%m%d')}.csv"},
    )


@router.post(
    "/orders/bulk-status",
    response_model=dict,
    summary="Bulk update order statuses",
)
def bulk_update_order_status(
    order_ids: list[uuid.UUID],
    new_status: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    from app.models.commerce import OrderGroupStatus
    try:
        target_status = OrderGroupStatus(new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    updated = db.query(OrderGroup).filter(
        OrderGroup.id.in_(order_ids)
    ).update({OrderGroup.status: target_status}, synchronize_session=False)
    db.commit()
    return {"updated": updated}


@router.post(
    "/products/import",
    response_model=dict,
    summary="Import products from CSV (admin)",
)
async def import_products_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be CSV")

    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    required = {"name", "slug", "price", "shop_id", "category_id"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise HTTPException(status_code=400, detail=f"CSV must contain columns: {', '.join(required)}")

    created = 0
    errors = []
    for i, row in enumerate(reader, start=2):
        try:
            shop = db.query(Shop).filter(Shop.id == row["shop_id"]).first()
            if not shop:
                errors.append(f"Row {i}: Shop {row['shop_id']} not found")
                continue

            category = db.query(Category).filter(Category.id == row["category_id"]).first()
            if not category:
                errors.append(f"Row {i}: Category {row['category_id']} not found")
                continue

            # Check if slug already exists for this shop
            existing = db.query(Product).filter(
                Product.slug == row["slug"],
                Product.shop_id == shop.id,
            ).first()
            if existing:
                errors.append(f"Row {i}: Product with slug '{row['slug']}' already exists for this shop")
                continue

            product = Product(
                shop_id=shop.id,
                category_id=category.id,
                name=row["name"],
                slug=row["slug"],
                description=row.get("description", ""),
                price=row["price"],
                compare_price=row.get("compare_price") or None,
                sku=row.get("sku") or None,
                stock_qty=int(row.get("stock_qty", 0)),
                status=row.get("status", "draft"),
            )
            db.add(product)
            created += 1
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")

    db.commit()
    return {"created": created, "errors": errors}


# ── Fraud detection ────────────────────────────────────────────────────────────

@router.get(
    "/fraud/high-risk",
    response_model=list[dict],
    summary="Get orders flagged as high fraud risk",
)
def list_high_risk_orders(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return get_high_risk_orders(db, limit=limit)


@router.get(
    "/fraud/evaluate/{order_group_id}",
    response_model=dict,
    summary="Evaluate a specific order for fraud risk",
)
def evaluate_order_fraud_risk(
    order_group_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return evaluate_order_fraud(db, order_group_id)


@router.get(
    "/fraud/stats",
    response_model=dict,
    summary="Get fraud detection statistics",
)
def get_fraud_stats(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, 30)
    
    # Get recent paid orders
    orders = db.query(OrderGroup).filter(
        OrderGroup.status == "paid",
        OrderGroup.created_at >= since,
        OrderGroup.created_at < until,
    ).all()
    
    stats = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for og in orders:
        evaluation = FraudDetectionService(db).evaluate_order(og)
        stats[evaluation["risk_level"]] += 1
    
    return {
        "period": period or "last_30_days",
        "total_evaluated": len(orders),
        "risk_distribution": stats,
        "review_required": stats["high"] + stats["critical"],
    }
