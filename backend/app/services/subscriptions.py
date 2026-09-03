from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.shop import ShopStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import UserStatus
from app.services.notifications import notify_admins_of_pos_provisioning

SUBSCRIPTION_PERIOD_DAYS = 30


def activate_subscription(db: Session, subscription: Subscription) -> None:
    """Flips a pending-payment subscription (and its shop + seller) to active.

    Idempotent: calling this on an already-active subscription is a no-op, so
    both the Paystack webhook and the status-reconciliation endpoint can call
    it without double-processing a payment.
    """
    if subscription.status == SubscriptionStatus.active:
        return

    now = datetime.now(timezone.utc)
    subscription.status = SubscriptionStatus.active
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)

    shop = subscription.shop
    plan_features = subscription.plan.features or {}
    shop.status = ShopStatus.active
    shop.is_featured = bool(plan_features.get("featured_placement", False))

    shop.seller.status = UserStatus.active

    if plan_features.get("pos_access", False):
        # No Tara POS API integration exists yet, so this is a manual
        # provisioning step for the ops team rather than an automated one.
        notify_admins_of_pos_provisioning(db, shop)
