from datetime import datetime, timedelta, timezone

from app.models.shop import ShopStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import UserStatus

SUBSCRIPTION_PERIOD_DAYS = 30


def activate_subscription(subscription: Subscription) -> None:
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
    shop.status = ShopStatus.active
    shop.is_featured = bool((subscription.plan.features or {}).get("featured_placement", False))

    shop.seller.status = UserStatus.active
