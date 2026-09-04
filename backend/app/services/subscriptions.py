from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.delivery import Notification
from app.models.shop import ShopStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import UserStatus
from app.services import email as email_service
from app.services.notifications import notify_admins_of_pos_provisioning
import logging

logger = logging.getLogger(__name__)

SUBSCRIPTION_PERIOD_DAYS = 30
REMINDER_DAYS_BEFORE_EXPIRY = (7, 1)
PAST_DUE_GRACE_DAYS = 3


def activate_subscription(db: Session, subscription: Subscription) -> None:
    """Flips a pending-payment (or lapsed) subscription, and its shop + seller,
    to active for a fresh 30-day period.

    Idempotent: calling this on an already-active subscription is a no-op, so
    both the Paystack webhook and the status-reconciliation endpoint can call
    it without double-processing a payment. Also used to reactivate a renewal
    payment from `past_due`/`cancelled`, not just the original `pending_payment`.
    """
    if subscription.status == SubscriptionStatus.active:
        return

    # only true the very first time this subscription is ever activated —
    # renewals must not re-trigger POS provisioning for an already-provisioned shop
    is_first_activation = subscription.current_period_start is None

    now = datetime.now(timezone.utc)
    subscription.status = SubscriptionStatus.active
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)
    subscription.reminder_7d_sent_at = None
    subscription.reminder_1d_sent_at = None

    shop = subscription.shop
    plan_features = subscription.plan.features or {}
    shop.status = ShopStatus.active
    shop.is_featured = bool(plan_features.get("featured_placement", False))

    shop.seller.status = UserStatus.active

    if is_first_activation and plan_features.get("pos_access", False):
        # No Tara POS API integration exists yet, so this is a manual
        # provisioning step for the ops team rather than an automated one.
        notify_admins_of_pos_provisioning(db, shop)


def _notify_seller(db: Session, subscription: Subscription, *, type: str, title: str, body: str) -> None:
    seller = subscription.shop.seller
    db.add(Notification(user_id=seller.id, type=type, title=title, body=body, data={"shop_id": str(subscription.shop_id)}))


def send_renewal_reminders(db: Session) -> int:
    """Emails sellers whose active subscription is about to expire, once per
    reminder window per period (reminder_*_sent_at is reset on every activation)."""
    now = datetime.now(timezone.utc)
    sent = 0

    for days_left, column in zip(REMINDER_DAYS_BEFORE_EXPIRY, ("reminder_7d_sent_at", "reminder_1d_sent_at")):
        window_start = now
        window_end = now + timedelta(days=days_left)
        subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.active,
                Subscription.current_period_end > window_start,
                Subscription.current_period_end <= window_end,
                getattr(Subscription, column).is_(None),
            )
            .all()
        )
        for subscription in subscriptions:
            try:
                email_service.send_subscription_reminder_email(
                    subscription.shop.seller.email,
                    subscription.shop,
                    subscription.plan.name,
                    days_left,
                    subscription.current_period_end,
                )
            except Exception as e:
                logger.warning("Failed to send renewal reminder for subscription %s: %s", subscription.id, e)
                continue
            setattr(subscription, column, now)
            sent += 1

    return sent


def expire_overdue_subscriptions(db: Session) -> int:
    """Flips active subscriptions past their current_period_end to past_due.
    The shop stays live during this grace window."""
    now = datetime.now(timezone.utc)
    subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.status == SubscriptionStatus.active,
            Subscription.current_period_end < now,
        )
        .all()
    )

    for subscription in subscriptions:
        subscription.status = SubscriptionStatus.past_due
        try:
            email_service.send_subscription_past_due_email(
                subscription.shop.seller.email, subscription.shop, PAST_DUE_GRACE_DAYS
            )
        except Exception as e:
            logger.warning("Failed to send past-due email for subscription %s: %s", subscription.id, e)
        _notify_seller(
            db,
            subscription,
            type="subscription_past_due",
            title="Your Ekshop subscription payment is overdue",
            body=f"Renew within {PAST_DUE_GRACE_DAYS} days to keep {subscription.shop.name} live.",
        )

    return len(subscriptions)


def suspend_cancelled_subscriptions(db: Session) -> int:
    """Flips past_due subscriptions that outlasted the grace window to
    cancelled and suspends the shop, hiding it from public listings."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=PAST_DUE_GRACE_DAYS)
    subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.status == SubscriptionStatus.past_due,
            Subscription.current_period_end < cutoff,
        )
        .all()
    )

    for subscription in subscriptions:
        subscription.status = SubscriptionStatus.cancelled
        shop = subscription.shop
        shop.status = ShopStatus.suspended
        shop.is_featured = False
        try:
            email_service.send_subscription_cancelled_email(shop.seller.email, shop)
        except Exception as e:
            logger.warning("Failed to send cancellation email for subscription %s: %s", subscription.id, e)
        _notify_seller(
            db,
            subscription,
            type="subscription_cancelled",
            title="Your shop has been suspended for non-payment",
            body=f"{shop.name} is hidden from Ekshop until you renew your subscription.",
        )

    return len(subscriptions)


def run_billing_cycle(db: Session) -> dict:
    """Daily entrypoint: sends renewal reminders, then expires overdue
    subscriptions, then suspends shops whose grace window has lapsed —
    in that order, so a subscription expiring today isn't also reminded."""
    reminders_sent = send_renewal_reminders(db)
    db.commit()

    expired = expire_overdue_subscriptions(db)
    db.commit()

    suspended = suspend_cancelled_subscriptions(db)
    db.commit()

    return {"reminders_sent": reminders_sent, "expired_to_past_due": expired, "suspended": suspended}
