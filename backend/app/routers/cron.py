from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from html import escape

from app.core.config import settings
from app.dependencies.database import get_db
from app.models.commerce import Order
from app.models.shop import Shop, ShopStatus
from app.models.user import User, UserStatus
from app.routers.payments import reconcile_stale_mpesa_intents
from app.services.subscriptions import run_billing_cycle
from app.services.automation import get_or_create_automation_settings
from app.services.email import _send
from app.services.dashboard_metrics import get_margin_leakage_metrics

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


def _report_recipient(enabled: bool, email: str | None) -> str | None:
    """The address a scheduled report goes to, or None when it's switched off.
    Falls back to the ADMIN_REPORT_EMAIL env var when no address is saved."""
    if not enabled:
        return None
    return email or settings.ADMIN_REPORT_EMAIL


@router.post("/admin/daily-report")
def send_daily_admin_report(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    automation = get_or_create_automation_settings(db)
    db.commit()
    if not automation.daily_admin_report_enabled:
        return {"status": "skipped", "reason": "Daily report is turned off in automation settings"}
    recipient = _report_recipient(True, automation.daily_admin_report_email)
    if not recipient:
        return {"status": "skipped", "reason": "No daily report email set"}

    since = datetime.now(timezone.utc) - timedelta(days=1)
    metrics = get_margin_leakage_metrics(db, since)

    subject = f"Ekshop daily ops report: gross margin {metrics.get('gross_margin_pct', 0):.2f}%"
    html = f"""
        <h2>Daily Margin Leakage Report</h2>
        <p>Period: {escape(str(metrics.get('period')))} | Orders: {metrics.get('orders')} | AOV: KES {metrics.get('average_order_value')}</p>
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
    automation = get_or_create_automation_settings(db)
    db.commit()
    if not automation.weekly_insight_digest_enabled:
        return {"status": "skipped", "reason": "Weekly digest is turned off in automation settings"}
    recipient = _report_recipient(True, automation.weekly_insight_digest_email)
    if not recipient:
        return {"status": "skipped", "reason": "No weekly digest email set"}

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    top_merchants = (
        db.query(Shop.name, func.count(Order.id).label("orders"))
        .join(Order, Order.shop_id == Shop.id)
        .filter(Order.created_at >= since, Shop.status == ShopStatus.active)
        .group_by(Shop.name)
        .order_by(func.count(Order.id).desc())
        .limit(5)
        .all()
    )
    # Churn risk: buyers who have ordered before but not in the last 60 days,
    # most recently lapsed first.
    last_order_at = func.max(Order.created_at)
    churn_risks = (
        db.query(User.first_name, User.last_name, User.email, last_order_at.label("last_order_at"))
        .join(Order, Order.buyer_id == User.id)
        .filter(User.status == UserStatus.active)
        .group_by(User.id, User.first_name, User.last_name, User.email)
        .having(last_order_at < now - timedelta(days=60))
        .order_by(last_order_at.desc())
        .limit(10)
        .all()
    )

    top_merchants_rows = "".join(
        f"<tr><td>{escape(name)}</td><td>{orders}</td></tr>" for name, orders in top_merchants
    ) or "<tr><td colspan='2'>No data</td></tr>"

    churn_risks_rows = "".join(
        f"<tr><td>{escape(f'{first} {last}')}</td><td>{escape(email)}</td><td>{last_at:%d %b %Y}</td></tr>"
        for first, last, email, last_at in churn_risks
    ) or "<tr><td colspan='3'>No data</td></tr>"

    html = f"""
        <h2>Weekly Insight Digest</h2>
        <p>Period: last 7 days</p>
        <h3>Top Merchants</h3>
        <table border="1" cellpadding="4" cellspacing="0">
          <tr><th>Shop</th><th>Orders</th></tr>
          {top_merchants_rows}
        </table>
        <h3>Churn Risks</h3>
        <p>Customers who have ordered before but not in the last 60 days.</p>
        <table border="1" cellpadding="4" cellspacing="0">
          <tr><th>Customer</th><th>Email</th><th>Last order</th></tr>
          {churn_risks_rows}
        </table>
        <p><a href="{settings.FRONTEND_URL}/admin/analytics">Open admin analytics</a></p>
    """
    try:
        _send(to=recipient, subject="Ekshop weekly insight digest", html=html)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send weekly digest: {exc}") from exc
    return {"status": "sent", "to": recipient}
