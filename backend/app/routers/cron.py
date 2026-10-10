from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.dependencies.database import get_db
from app.routers.payments import reconcile_stale_mpesa_intents
from app.services.subscriptions import run_billing_cycle
from app.services.email import _send, send_abandoned_cart_email
from app.services import dashboard_metrics, reports, etims as etims_service
from app.services.reports import EAT
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
    """Yesterday, complete. Meant to be called each morning.

    This used to report the margin-leakage monitor's figures, which were built
    from hardcoded rates and a formula that subtracted the platform's own
    commission out of GMV. It now reports money that actually arrived.
    """
    yesterday = datetime.now(EAT).date() - timedelta(days=1)
    start, end, label = reports.daily_window(yesterday)
    summary = reports.build_trading_summary(db, start, end, label)
    recipient = getattr(settings, "ADMIN_REPORT_EMAIL", None)
    if not recipient:
        return {"status": "skipped", "reason": "ADMIN_REPORT_EMAIL not configured"}

    figures = "".join(
        f"<tr><th>{name}</th><td style='text-align:right'>{value}</td></tr>"
        for name, value in reports.summary_lines(summary)
    )
    html = f"""
        <h2>Yesterday on Ekshop</h2>
        <p><strong>{summary.verdict}</strong></p>
        <table cellpadding="4" cellspacing="0" style="border-collapse:collapse">
          {figures}
        </table>
        <p><a href="{settings.FRONTEND_URL}/admin/analytics">Open admin analytics</a></p>
    """
    try:
        _send(to=recipient, subject=f"Ekshop {label} — {summary.verdict}", html=html)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send admin report: {exc}") from exc
    return {"status": "sent", "to": recipient, "period": label, "verdict": summary.verdict}


@router.post("/admin/weekly-report")
def send_weekly_report(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    """The week that just finished, Monday to Sunday. Call on Monday morning.

    The window is the completed calendar week rather than "the last 7 days from
    whenever this fired", so the figure an admin is asked about on Monday is the
    figure they mean.
    """
    start, end, label = reports.weekly_window()
    summary = reports.build_trading_summary(db, start, end, label)
    recipient = getattr(settings, "ADMIN_REPORT_EMAIL", None)
    if not recipient:
        return {"status": "skipped", "reason": "ADMIN_REPORT_EMAIL not configured"}

    html = _report_email(
        summary,
        heading="Weekly trading report",
        intro="The week just finished, Monday to Sunday.",
    )
    try:
        _send(to=recipient, subject=f"Ekshop weekly report — {summary.verdict}", html=html)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send weekly report: {exc}") from exc
    return {"status": "sent", "to": recipient, "period": label, "verdict": summary.verdict}


@router.post("/admin/monthly-report")
def send_monthly_report(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    """The calendar month just finished. Call on the 1st.

    There was no monthly report at all before, so month-on-month performance had
    to be reconstructed by hand from the dashboard.
    """
    start, end, label = reports.monthly_window()
    summary = reports.build_trading_summary(db, start, end, label)
    recipient = getattr(settings, "ADMIN_REPORT_EMAIL", None)
    if not recipient:
        return {"status": "skipped", "reason": "ADMIN_REPORT_EMAIL not configured"}

    html = _report_email(
        summary,
        heading="Monthly trading report",
        intro="The calendar month just finished.",
    )
    try:
        _send(to=recipient, subject=f"Ekshop monthly report — {summary.verdict}", html=html)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send monthly report: {exc}") from exc
    return {"status": "sent", "to": recipient, "period": label, "verdict": summary.verdict}


def _report_email(summary, heading: str, intro: str) -> str:
    figures = "".join(
        f"<tr><th style='text-align:left;padding:4px 10px 4px 0'>{name}</th>"
        f"<td style='text-align:right;padding:4px 0'>{value}</td></tr>"
        for name, value in reports.summary_lines(summary)
    )
    daily = "".join(
        f"<tr>"
        f"<td style='padding:3px 10px 3px 0'>{row.label}</td>"
        f"<td style='text-align:right;padding:3px 10px 3px 0'>{row.cash_received:,.2f}</td>"
        f"<td style='text-align:right;padding:3px 10px 3px 0'>{row.refunds:,.2f}</td>"
        f"<td style='text-align:right;padding:3px 10px 3px 0'>{row.cash_received - row.refunds:,.2f}</td>"
        f"<td style='text-align:right;padding:3px 10px 3px 0'>{row.gmv:,.2f}</td>"
        f"<td style='text-align:right;padding:3px 10px 3px 0'>{row.orders}</td>"
        f"</tr>"
        for row in summary.daily
    )
    return f"""
        <h2>{heading}</h2>
        <p>{intro} Period: <strong>{summary.period_label}</strong></p>
        <p style="font-size:15px"><strong>{summary.verdict}</strong></p>
        <h3>Figures</h3>
        <table cellpadding="4" cellspacing="0" style="border-collapse:collapse">
          {figures}
        </table>
        <h3>By day</h3>
        <table cellpadding="4" cellspacing="0" style="border-collapse:collapse;border:1px solid #ddd">
          <thead><tr>
            <th style="text-align:left">Day</th>
            <th style="text-align:right">Received</th>
            <th style="text-align:right">Refunds</th>
            <th style="text-align:right">Net cash</th>
            <th style="text-align:right">GMV</th>
            <th style="text-align:right">Baskets</th>
          </tr></thead>
          <tbody>{daily}</tbody>
        </table>
        <p style="color:#666;font-size:12px">Received and refunds come from the
        payments table by the time the money arrived. Baskets and GMV count each
        order once, so a retried payment cannot inflate them. Net is left
        uncalculated rather than estimated when a rate it depends on is not
        configured.</p>
        <p><a href="{settings.FRONTEND_URL}/admin/analytics">Open admin analytics</a></p>
    """


@router.post("/admin/weekly-insight-digest")
def send_weekly_insight_digest(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    """Commercial digest: which merchants and which customers to chase.

    Distinct from the weekly *report*, which is about money. This one is a list.
    """
    since = datetime.now(timezone.utc) - timedelta(days=7)
    recipient = getattr(settings, "ADMIN_REPORT_EMAIL", None)
    if not recipient:
        return {"status": "skipped", "reason": "ADMIN_REPORT_EMAIL not configured"}

    top_merchants = (
        db.query(Shop.name, func.count(Order.id).label("orders"))
        .join(Order, Order.shop_id == Shop.id)
        .filter(Order.created_at >= since, Shop.status == "active")
        .group_by(Shop.name)
        .order_by(func.count(Order.id).desc())
        .limit(5)
        .all()
    )
    # Previously this was "every buyer older than 60 days" with no reference to
    # whether they had ordered recently -- so the list was labelled churn risk
    # while containing accounts that had bought yesterday. It now uses the same
    # inactivity test as the analytics churn panel.
    churn_risks = dashboard_metrics.get_churn_risks_insight(db, since)

    top_merchants_rows = "".join(
        f"<tr><td>{name}</td><td>{orders}</td></tr>" for name, orders in top_merchants
    ) or "<tr><td colspan='2'>No data</td></tr>"

    churn_risks_rows = "".join(
        f"<tr><td>{c['first_name']} {c['last_name']}</td><td>{c['email']}</td>"
        f"<td>{c['last_order_at'] or 'never'}</td></tr>"
        for c in churn_risks
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
        <p style="color:#666;font-size:12px">Buyers whose last order predates the
        period shown above.</p>
        <table border="1" cellpadding="4" cellspacing="0">
          <tr><th>Buyer</th><th>Email</th><th>Last order</th></tr>
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


@router.post(
    "/process-scheduled-orders",
    summary="Process scheduled orders that are due (cron-triggered)",
)
def process_scheduled_orders(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    """Find order groups with scheduled_at <= now and pending_payment status,
    then trigger payment flow or mark as ready for payment."""
    from app.models.commerce import OrderGroup, OrderGroupStatus

    now = datetime.now(timezone.utc)

    scheduled_groups = db.query(OrderGroup).filter(
        OrderGroup.scheduled_at.isnot(None),
        OrderGroup.scheduled_at <= now,
        OrderGroup.status == OrderGroupStatus.pending_payment,
    ).all()

    processed = 0
    for group in scheduled_groups:
        group.status = OrderGroupStatus.pending_payment
        processed += 1

    db.commit()
    return {"status": "completed", "processed": processed}


@router.post(
    "/expire-old-scheduled-orders",
    summary="Cancel scheduled orders past their expiry (cron-triggered)",
)
def expire_old_scheduled_orders(
    expiry_hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    """Cancel scheduled orders that are past their scheduled time + expiry window."""
    from app.models.commerce import OrderGroup, OrderGroupStatus

    expiry_cutoff = datetime.now(timezone.utc) - timedelta(hours=expiry_hours)

    expired_groups = db.query(OrderGroup).filter(
        OrderGroup.scheduled_at.isnot(None),
        OrderGroup.scheduled_at < expiry_cutoff,
        OrderGroup.status == OrderGroupStatus.pending_payment,
    ).all()

    cancelled = 0
    for group in expired_groups:
        group.status = OrderGroupStatus.cancelled
        cancelled += 1

    db.commit()
    return {"status": "completed", "cancelled": cancelled}


@router.post(
    "/etims-process-queue",
    summary="Process pending eTIMS submission queue (cron-triggered)",
    description="""
Processes pending eTIMS invoices and credit notes in the submission queue.
Retries failed submissions with exponential backoff. Respects ETIMS_ENABLED setting.
Triggered periodically by an external scheduler (GitHub Actions).
""",
)
def process_etims_queue(
    batch_size: int = Query(settings.ETIMS_QUEUE_BATCH_SIZE, ge=1, le=200),
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    if not settings.ETIMS_ENABLED:
        return {"status": "skipped", "reason": "ETIMS_ENABLED is false"}

    # Import here to avoid circular dependency at module load time
    import asyncio
    from app.services import etims as etims_service

    processed = asyncio.run(etims_service.process_queue_batch(db, batch_size))
    return {"status": "completed", "processed": processed, "batch_size": batch_size}
