from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.dependencies.database import get_db
from app.routers.payments import reconcile_stale_mpesa_intents
from app.services.subscriptions import run_billing_cycle
from app.services.email import _send, send_abandoned_cart_email
from app.services.dashboard_metrics import get_margin_leakage_metrics
from app.models.commerce import Order, Cart
from app.models.shop import Shop
from app.models.user import User

router = APIRouter(prefix="/internal/cron", tags=["internal"])


def verify_cron_secret(x_cron_secret: str | None = Header(default=None)) -> None:
    if not settings.CRON_SECRET or x_cron_secret != settings.CRON_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cron secret")


@router.post(
    "/billing-cycle",
    summary="Run the daily seller-subscription billing cycle (cron-triggered)",
    description="""
Sends renewal reminders, flips overdue subscriptions to `past_due`, and
suspends shops whose `past_due` grace window has lapsed. Triggered daily by
an external scheduler (GitHub Actions) — not user-facing, guarded by a
shared secret instead of a logged-in admin session.
""",
)
def run_billing_cycle_endpoint(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    return run_billing_cycle(db)


@router.post(
    "/mpesa-reconcile",
    summary="Sweep stuck-pending M-Pesa payment intents (cron-triggered)",
    description="""
Actively re-queries Safaricom for any M-Pesa STK push still sitting in
`pending` status a while after being initiated — covers a buyer who closed
the tab before the callback arrived (or before it ever would have) and
never revisited the order page to trigger the manual fallback. Triggered
periodically by an external scheduler (GitHub Actions), not user-facing.
""",
)
def run_mpesa_reconcile_endpoint(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    return reconcile_stale_mpesa_intents(db)


@router.post("/admin/daily-report")
def send_daily_admin_report(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    since = datetime.now(timezone.utc) - timedelta(days=1)
    metrics = get_margin_leakage_metrics(db, since)
    recipient = getattr(settings, "ADMIN_REPORT_EMAIL", None)
    if not recipient:
        return {"status": "skipped", "reason": "ADMIN_REPORT_EMAIL not configured"}

    subject = f"Ekshop daily ops report — gross margin {metrics.get('gross_margin_pct', 0):.2f}%"
    html = f"""
        <h2>Daily Margin Leakage Report</h2>
        <p>Period: {metrics.get('period')} | Orders: {metrics.get('orders')} | AOV: KES {metrics.get('average_order_value')}</p>
        <p>GMV: KES {metrics.get('gmv')} | Platform commission: KES {metrics.get('platform_commission')} | M-Pesa fees: KES {metrics.get('mpesa_fees')} | Net profit: KES {metrics.get('net_profit')} | Gross margin: {metrics.get('gross_margin_pct')}%</p>
        <p><a href="{settings.FRONTEND_URL}/admin/analytics">Open admin analytics</a></p>
    """
    try:
        _send(to=recipient, subject=subject, html=html)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send admin report: {exc}") from exc
    return {"status": "sent", "to": recipient}


@router.post("/admin/weekly-insight-digest")
def send_weekly_insight_digest(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    since = datetime.now(timezone.utc) - timedelta(days=7)
    recipient = getattr(settings, "ADMIN_REPORT_EMAIL", None)
    if not recipient:
        return {"status": "skipped", "reason": "ADMIN_REPORT_EMAIL not configured"}

    merchants = getattr(settings, "ADMIN_REPORT_EMAIL", None)
    top_merchants = (
        db.query(Shop.name, func.count(Order.id).label("orders"))
        .join(Order, Order.shop_id == Shop.id)
        .filter(Order.created_at >= since, Shop.status == "active")
        .group_by(Shop.name)
        .order_by(func.count(Order.id).desc())
        .limit(5)
        .all()
    )
    churn_risks = (
        db.query(User.first_name, User.last_name, User.email)
        .filter(User.role == "buyer", User.created_at < datetime.now(timezone.utc) - timedelta(days=60))
        .limit(10)
        .all()
    )

    top_merchants_rows = "".join(
        f"<tr><td>{name}</td><td>{orders}</td></tr>" for name, orders in top_merchants
    ) or "<tr><td colspan='2'>No data</td></tr>"

    churn_risks_rows = "".join(
        f"<tr><td>{first_name} {last_name}</td><td>{email}</td></tr>" for first_name, last_name, email in churn_risks
    ) or "<tr><td colspan='2'>No data</td></tr>"

    html = f"""
        <h2>Weekly Insight Digest</h2>
        <p>Period: last 7 days</p>
        <h3>Top Merchants</h3>
        <table border="1" cellpadding="4" cellspacing="0">
          <tr><th>Shop</th><th>Orders</th></tr>
          {top_merchants_rows}
        </table>
        <h3>Churn Risks</h3>
        <table border="1" cellpadding="4" cellspacing="0">
          <tr><th>Buyer</th><th>Email</th></tr>
          {churn_risks_rows}
        </table>
        <p><a href="{settings.FRONTEND_URL}/admin/analytics">Open admin analytics</a></p>
    """
    try:
        _send(to=recipient, subject="Ekshop weekly insight digest", html=html)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send weekly digest: {exc}") from exc
    return {"status": "sent", "to": recipient}


import logging
logger = logging.getLogger(__name__)


@router.post(
    "/abandoned-carts",
    summary="Send abandoned cart recovery emails (cron-triggered)",
    description="""
Finds carts with items that haven't been updated in the last 2 hours and
sends a recovery email to the user. Triggered periodically by an external scheduler.
""",
)
def run_abandoned_carts_recovery(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)

    abandoned_carts = (
        db.query(Cart)
        .join(Cart.items)
        .join(Cart.user)
        .filter(
            Cart.updated_at < cutoff,
            Cart.items.any(),
            User.email.isnot(None),
        )
        .distinct()
        .all()
    )

    sent = 0
    skipped = 0

    for cart in abandoned_carts:
        recent_order = (
            db.query(Order)
            .filter(
                Order.buyer_id == cart.user_id,
                Order.created_at > datetime.now(timezone.utc) - timedelta(hours=24),
            )
            .first()
        )
        if recent_order:
            skipped += 1
            continue

        items_data = []
        for item in cart.items:
            product = item.product
            if not product or product.status != "active":
                continue
            items_data.append({
                "name": product.name,
                "price": product.price,
                "quantity": item.quantity,
                "image_url": product.images[0].url if product.images else "",
            })

        if not items_data:
            skipped += 1
            continue

        cart_url = f"{settings.FRONTEND_URL}/cart"
        try:
            send_abandoned_cart_email(
                to=cart.user.email,
                user_name=cart.user.first_name,
                cart_items=items_data,
                cart_url=cart_url,
            )
            sent += 1
        except Exception as exc:
            logger.warning("Failed to send abandoned cart email to %s: %s", cart.user.email, exc)

    return {"status": "completed", "sent": sent, "skipped": skipped}
