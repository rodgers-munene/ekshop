"""Aggregation queries backing the admin analytics dashboard.

Each function accepts a `since` cutoff and returns period-scoped counts using
data that already exists in the schema (orders, deliveries, user events, issue
reports). Metrics that would need new subsystems (rider accept/reject flow,
delivery cost tracking, post-delivery ratings, a POS integration) are
intentionally left out — see the implementation plan for why.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from typing import Optional

from sqlalchemy import Numeric, cast, desc, func
from sqlalchemy.orm import Session

from app.models.analytics import UserEvent, EventType, IssueReport
from app.models.catalog import Product
from app.models.commerce import Order, OrderGroup, OrderGroupStatus, OrderStatus
from app.models.delivery import Delivery, DeliveryAgent, DeliveryAgentStatus, DeliveryStatus
from app.models.shop import Shop, ShopStatus
from app.models.user import User, UserRole


def _hours_between(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 3600


def _bound(since: datetime, until: Optional[datetime]) -> datetime:
    return until or datetime.now(timezone.utc)


# ── Merchant activity & engagement ──────────────────────────────────────────

def get_merchant_activity_metrics(db: Session, since: datetime, until: Optional[datetime] = None) -> dict:
    end = _bound(since, until)
    since_30d = datetime.now(timezone.utc) - timedelta(days=30)

    total_merchants = db.query(func.count(Shop.id)).filter(Shop.status == ShopStatus.active).scalar() or 0

    def active_shop_ids(cutoff: datetime) -> set:
        ordering_shops = {
            row[0]
            for row in db.query(Order.shop_id).filter(Order.created_at >= cutoff).distinct().all()
        }
        logged_in_shops = {
            row[0]
            for row in db.query(Shop.id)
            .join(User, User.id == Shop.seller_id)
            .filter(User.last_login_at >= cutoff)
            .all()
        }
        return ordering_shops | logged_in_shops

    active_7d = active_shop_ids(datetime.now(timezone.utc) - timedelta(days=7))
    active_30d = active_shop_ids(since_30d)

    merchants_receiving_orders = (
        db.query(func.count(func.distinct(Order.shop_id)))
        .filter(Order.created_at >= since, Order.created_at < end)
        .scalar()
        or 0
    )
    merchants_processing_orders = (
        db.query(func.count(func.distinct(Order.shop_id)))
        .filter(
            Order.created_at >= since,
            Order.created_at < end,
            Order.status.in_([OrderStatus.confirmed, OrderStatus.processing, OrderStatus.shipped]),
        )
        .scalar()
        or 0
    )
    merchants_zero_activity = max(total_merchants - len(active_30d), 0)

    sellers_logged_in = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.seller, User.last_login_at >= since, User.last_login_at < end)
        .scalar()
        or 0
    )
    products_updated = (
        db.query(func.count(func.distinct(Product.id)))
        .filter(Product.updated_at >= since, Product.updated_at < end)
        .scalar()
        or 0
    )

    orders_in_period = db.query(func.count(Order.id)).filter(
        Order.created_at >= since, Order.created_at < end, Order.status != OrderStatus.pending
    ).scalar() or 0
    avg_transactions_per_merchant = (
        round(orders_in_period / len(active_7d), 2) if active_7d else 0.0
    )

    return {
        "active_merchants_7d": len(active_7d),
        "active_merchants_30d": len(active_30d),
        "merchants_receiving_orders": merchants_receiving_orders,
        "merchants_processing_orders": merchants_processing_orders,
        "merchants_zero_activity": merchants_zero_activity,
        "sellers_logged_in": sellers_logged_in,
        "products_updated": products_updated,
        "avg_transactions_per_merchant": avg_transactions_per_merchant,
    }


# ── Sales & demand ───────────────────────────────────────────────────────────

def get_sales_demand_metrics(db: Session, since: datetime, until: Optional[datetime] = None) -> dict:
    end = _bound(since, until)
    paid_groups = db.query(OrderGroup).filter(
        OrderGroup.status == OrderGroupStatus.paid,
        OrderGroup.created_at >= since,
        OrderGroup.created_at < end,
    )
    paid_group_count = paid_groups.count()
    gmv = sum((Decimal(g.total) for g in paid_groups.all()), Decimal("0"))
    average_order_value = (gmv / paid_group_count) if paid_group_count else Decimal("0")

    orders_query = db.query(Order).filter(
        Order.created_at >= since, Order.created_at < end, Order.status != OrderStatus.pending
    )
    total_orders = orders_query.count()
    cancelled_orders = orders_query.filter(Order.status == OrderStatus.cancelled).count()
    order_cancellation_rate = round((cancelled_orders / total_orders) * 100, 2) if total_orders else 0.0

    # A buyer's "first" paid order group defines whether they're new in this window.
    first_order_subq = (
        db.query(OrderGroup.buyer_id, func.min(OrderGroup.created_at).label("first_at"))
        .filter(OrderGroup.status == OrderGroupStatus.paid)
        .group_by(OrderGroup.buyer_id)
        .subquery()
    )
    new_customers = (
        db.query(func.count(first_order_subq.c.buyer_id))
        .filter(first_order_subq.c.first_at >= since, first_order_subq.c.first_at < end)
        .scalar()
        or 0
    )
    buyers_active_in_period = {
        row[0] for row in paid_groups.with_entities(OrderGroup.buyer_id).distinct().all()
    }
    repeat_customers = max(len(buyers_active_in_period) - new_customers, 0)

    new_users_in_period = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.buyer, User.created_at >= since, User.created_at < end)
        .scalar()
        or 0
    )
    customer_acquisition_rate = (
        round((new_customers / new_users_in_period) * 100, 2) if new_users_in_period else 0.0
    )

    # Cart abandonment: distinct sessions that added to cart vs. distinct sessions that purchased.
    adders = (
        db.query(func.count(func.distinct(UserEvent.session_id)))
        .filter(
            UserEvent.event_type == EventType.add_to_cart,
            UserEvent.created_at >= since,
            UserEvent.created_at < end,
        )
        .scalar()
        or 0
    )
    purchasers = (
        db.query(func.count(func.distinct(UserEvent.session_id)))
        .filter(
            UserEvent.event_type == EventType.purchase,
            UserEvent.created_at >= since,
            UserEvent.created_at < end,
        )
        .scalar()
        or 0
    )
    cart_abandonment_rate = round((1 - purchasers / adders) * 100, 2) if adders else 0.0

    return {
        "total_orders": total_orders,
        "gmv": str(gmv),
        "average_order_value": str(average_order_value.quantize(Decimal("0.01"))),
        "new_customers": new_customers,
        "repeat_customers": repeat_customers,
        "customer_acquisition_rate": customer_acquisition_rate,
        "cart_abandonment_rate": cart_abandonment_rate,
        "order_cancellation_rate": order_cancellation_rate,
    }


# ── Customer retention ───────────────────────────────────────────────────────

def get_customer_retention_metrics(db: Session, since: datetime, until: Optional[datetime] = None) -> dict:
    end = _bound(since, until)
    # Per-buyer purchase history (all-time), needed for churn/repeat/retention math.
    rows = (
        db.query(OrderGroup.buyer_id, OrderGroup.created_at)
        .filter(OrderGroup.status == OrderGroupStatus.paid)
        .order_by(OrderGroup.buyer_id, OrderGroup.created_at)
        .all()
    )
    history: dict = {}
    for buyer_id, created_at in rows:
        history.setdefault(buyer_id, []).append(created_at)

    now = datetime.now(timezone.utc)
    total_buyers_with_orders = len(history)
    repeat_buyers = sum(1 for dates in history.values() if len(dates) >= 2)
    repeat_purchase_rate = round((repeat_buyers / total_buyers_with_orders) * 100, 2) if total_buyers_with_orders else 0.0

    churned = sum(1 for dates in history.values() if (now - dates[-1]).days > 60)
    churn_rate = round((churned / total_buyers_with_orders) * 100, 2) if total_buyers_with_orders else 0.0

    eligible_cohort = [dates for dates in history.values() if (now - dates[0]).days >= 30]
    retained_30d = sum(
        1 for dates in eligible_cohort if len(dates) >= 2 and (dates[1] - dates[0]).days <= 30
    )
    retention_30d = round((retained_30d / len(eligible_cohort)) * 100, 2) if eligible_cohort else 0.0

    gaps = []
    for dates in history.values():
        for i in range(1, len(dates)):
            gaps.append((dates[i] - dates[i - 1]).days)
    avg_days_between_purchases = round(sum(gaps) / len(gaps), 1) if gaps else 0.0

    new_customers = sum(1 for dates in history.values() if since <= dates[0] < end)
    returning_customers = sum(
        1
        for dates in history.values()
        if dates[0] < since and any(since <= d < end for d in dates)
    )
    orders_in_period = sum(1 for dates in history.values() for d in dates if since <= d < end)
    buyers_in_period = sum(1 for dates in history.values() if any(since <= d < end for d in dates))
    orders_per_customer = round(orders_in_period / buyers_in_period, 2) if buyers_in_period else 0.0

    customer_complaints = (
        db.query(func.count(IssueReport.id))
        .filter(IssueReport.created_at >= since, IssueReport.created_at < end)
        .scalar()
        or 0
    )

    return {
        "new_customers": new_customers,
        "returning_customers": returning_customers,
        "repeat_purchase_rate": repeat_purchase_rate,
        "churn_rate": churn_rate,
        "retention_30d": retention_30d,
        "orders_per_customer": orders_per_customer,
        "avg_days_between_purchases": avg_days_between_purchases,
        "customer_complaints": customer_complaints,
    }


# ── Operations & delivery ────────────────────────────────────────────────────

def get_operations_delivery_metrics(db: Session, since: datetime, until: Optional[datetime] = None) -> dict:
    end = _bound(since, until)
    orders_received = (
        db.query(func.count(Order.id))
        .filter(Order.created_at >= since, Order.created_at < end, Order.status != OrderStatus.pending)
        .scalar()
        or 0
    )
    orders_fulfilled = (
        db.query(func.count(Order.id))
        .filter(Order.created_at >= since, Order.created_at < end, Order.status == OrderStatus.delivered)
        .scalar()
        or 0
    )
    orders_cancelled = (
        db.query(func.count(Order.id))
        .filter(Order.created_at >= since, Order.created_at < end, Order.status == OrderStatus.cancelled)
        .scalar()
        or 0
    )

    deliveries_in_period = (
        db.query(Delivery)
        .join(Order, Order.id == Delivery.order_id)
        .filter(Order.created_at >= since, Order.created_at < end)
        .all()
    )
    # "Accepted" = handed to a rider (assigned onward) — there's no separate
    # offer/accept step in this system, assignment is admin-driven.
    orders_accepted = sum(1 for d in deliveries_in_period if d.status != DeliveryStatus.pending)
    failed_deliveries = sum(1 for d in deliveries_in_period if d.status == DeliveryStatus.cancelled)

    dispatch_hours = [
        _hours_between(d.picked_at, d.created_at) for d in deliveries_in_period if d.picked_at
    ]
    avg_dispatch_time_hours = round(sum(dispatch_hours) / len(dispatch_hours), 2) if dispatch_hours else 0.0

    delivery_hours = [
        _hours_between(d.delivered_at, d.picked_at) for d in deliveries_in_period if d.delivered_at and d.picked_at
    ]
    avg_delivery_time_hours = round(sum(delivery_hours) / len(delivery_hours), 2) if delivery_hours else 0.0

    delivered_with_eta = [d for d in deliveries_in_period if d.status == DeliveryStatus.delivered and d.estimated_at]
    on_time = sum(1 for d in delivered_with_eta if d.delivered_at and d.delivered_at <= d.estimated_at)
    on_time_delivery_rate = round((on_time / len(delivered_with_eta)) * 100, 2) if delivered_with_eta else None

    active_agents = db.query(func.count(DeliveryAgent.id)).filter(DeliveryAgent.status != DeliveryAgentStatus.inactive).scalar() or 0
    completed_deliveries = sum(1 for d in deliveries_in_period if d.status == DeliveryStatus.delivered)
    rider_utilization = round(completed_deliveries / active_agents, 2) if active_agents else 0.0

    delivery_revenue = sum(
        (
            Decimal(o.delivery_fee or "0")
            for o in db.query(Order)
            .filter(Order.created_at >= since, Order.created_at < end, Order.status != OrderStatus.pending)
            .all()
        ),
        Decimal("0"),
    )

    return {
        "orders_received": orders_received,
        "orders_accepted": orders_accepted,
        "orders_fulfilled": orders_fulfilled,
        "orders_cancelled": orders_cancelled,
        "avg_dispatch_time_hours": avg_dispatch_time_hours,
        "avg_delivery_time_hours": avg_delivery_time_hours,
        "on_time_delivery_rate": on_time_delivery_rate,
        "failed_deliveries": failed_deliveries,
        "rider_utilization": rider_utilization,
        "delivery_revenue": str(delivery_revenue),
    }


# ── Cart abandonment (real persisted carts) ──────────────────────────────────

def get_cart_abandonment_metrics(db: Session, since: datetime, until: Optional[datetime] = None) -> dict:
    """Compute the cart funnel from persisted carts + cart_items vs paid orders.

    A cart counts as "touched" when one of its items was added inside the
    window. It is "converted" when its owner placed a paid order in the same
    window at or after the cart's earliest item in that window. Everything
    else touched but not converted is treated as abandoned.
    """
    end = _bound(since, until)

    active = (
        db.query(
            CartItem.cart_id,
            Cart.user_id,
            func.min(CartItem.added_at).label("min_added"),
        )
        .join(Cart, Cart.id == CartItem.cart_id)
        .filter(CartItem.added_at >= since, CartItem.added_at < end)
        .group_by(CartItem.cart_id, Cart.user_id)
        .all()
    )
    carts_touched = len(active)

    paid_by_buyer: dict = {}
    for buyer_id, created_at in (
        db.query(OrderGroup.buyer_id, OrderGroup.created_at)
        .filter(
            OrderGroup.status == OrderGroupStatus.paid,
            OrderGroup.created_at >= since,
            OrderGroup.created_at < end,
        )
        .all()
    ):
        paid_by_buyer.setdefault(buyer_id, []).append(created_at)

    def is_converted(cart_id, user_id, min_added) -> bool:
        return any(
            p >= min_added for p in paid_by_buyer.get(user_id, [])
        )

    converted_carts = sum(1 for row in active if is_converted(*row))
    abandoned_carts = carts_touched - converted_carts
    cart_abandonment_rate = round((abandoned_carts / carts_touched) * 100, 2) if carts_touched else 0.0

    abandoned_ids = [
        row.cart_id for row in active if not is_converted(row.cart_id, row.user_id, row.min_added)
    ]

    abandoned_products: list = []
    abandoned_units = 0
    at_risk_revenue = Decimal("0")
    if abandoned_ids:
        abandoned_items = (
            db.query(CartItem.product_id, func.sum(CartItem.quantity).label("units"))
            .join(Cart, Cart.id == CartItem.cart_id)
            .filter(
                CartItem.added_at >= since,
                CartItem.added_at < end,
                Cart.id.in_(abandoned_ids),
            )
            .group_by(CartItem.product_id)
            .all()
        )
        product_ids = [r.product_id for r in abandoned_items if r.product_id]
        products = {
            p.id: p
            for p in db.query(Product).filter(Product.id.in_(product_ids)).all()
        }
        for r in abandoned_items:
            product = products.get(r.product_id)
            name = product.name if product else "Deleted product"
            try:
                unit = Decimal(product.price) if product and product.price else Decimal("0")
            except Exception:
                unit = Decimal("0")
            units = int(r.units)
            risk = unit * units
            at_risk_revenue += risk
            abandoned_units += units
            abandoned_products.append(
                {
                    "product_id": r.product_id,
                    "name": name,
                    "slug": product.slug if product else None,
                    "units": units,
                    "at_risk_revenue": str(risk.quantize(Decimal("0.01"))),
                }
            )
        abandoned_products.sort(
            key=lambda x: Decimal(x["at_risk_revenue"]), reverse=True
        )

    top_rows = (
        db.query(
            OrderItem.product_id,
            func.sum(OrderItem.quantity).label("units"),
            func.sum(cast(OrderItem.line_total, Numeric)).label("revenue"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .join(OrderGroup, OrderGroup.id == Order.group_id)
        .filter(
            OrderGroup.status == OrderGroupStatus.paid,
            OrderGroup.created_at >= since,
            OrderGroup.created_at < end,
        )
        .group_by(OrderItem.product_id)
        .order_by(desc(func.sum(OrderItem.quantity)))
        .limit(10)
        .all()
    )
    top_product_ids = [r.product_id for r in top_rows if r.product_id]
    products = {
        p.id: p
        for p in db.query(Product).filter(Product.id.in_(top_product_ids)).all()
    }
    top_products = [
        {
            "product_id": r.product_id,
            "name": (
                products[r.product_id].name if r.product_id in products else "Deleted product"
            ),
            "slug": products[r.product_id].slug if r.product_id in products else None,
            "units": int(r.units),
            "revenue": str(Decimal(r.revenue or 0).quantize(Decimal("0.01"))),
        }
        for r in top_rows
    ]

    return {
        "carts_touched": carts_touched,
        "converted_carts": converted_carts,
        "abandoned_carts": abandoned_carts,
        "cart_abandonment_rate": cart_abandonment_rate,
        "abandoned_units": abandoned_units,
        "at_risk_revenue": str(at_risk_revenue.quantize(Decimal("0.01"))),
        "abandoned_products": abandoned_products,
        "top_products": top_products,
    }
