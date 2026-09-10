import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dependencies.auth import require_seller_allow_unpaid
from app.dependencies.database import get_db
from app.models.shop import Shop
from app.models.subscription import SubscriptionPlan
from app.models.user import User
from app.schemas.subscription import (
    RenewSubscriptionRequest,
    RenewSubscriptionResponse,
    SubscriptionPlanRead,
    SubscriptionRead,
)
from app.services import paystack

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _get_my_subscription(db: Session, current_user: User):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()
    if not shop or not shop.subscription:
        raise HTTPException(status_code=404, detail="You don't have a subscription yet")
    return shop.subscription


@router.get(
    "/plans",
    response_model=list[SubscriptionPlanRead],
    status_code=status.HTTP_200_OK,
    summary="List available subscription plans",
)
def list_plans(db: Session = Depends(get_db)):
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.price_monthly).all()


@router.get(
    "/me",
    response_model=SubscriptionRead,
    status_code=status.HTTP_200_OK,
    summary="Get my subscription",
)
def get_my_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller_allow_unpaid),
):
    return _get_my_subscription(db, current_user)


@router.post(
    "/me/renew",
    response_model=RenewSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a renewal (or plan-switch) payment for my subscription",
    description="""
Generates a fresh Paystack transaction, for the current plan/interval by
default, or for `plan_code`/`billing_interval` if given (staged on the
subscription's pending_plan_id/pending_billing_interval — not applied
until payment confirms, so an abandoned checkout can't grant a higher
plan's limits for free). Works whether the subscription is
past_due/cancelled (reactivating it) or still active (an early renewal or
switch, at the seller's option — no need to wait for the current period to
end). Does not change the subscription's status itself — it only flips to
(or stays) `active`, with the plan/interval and period applied, once the
payment is confirmed (via the Paystack webhook, or
`/auth/subscription-status`), same as the original registration payment.
""",
)
def renew_subscription(
    body: RenewSubscriptionRequest = RenewSubscriptionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller_allow_unpaid),
):
    subscription = _get_my_subscription(db, current_user)

    plan = subscription.plan
    if body.plan_code is not None and body.plan_code != plan.code:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == body.plan_code, SubscriptionPlan.is_active.is_(True)).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Unknown plan")
        subscription.pending_plan_id = plan.id

    interval = body.billing_interval or subscription.billing_interval
    if body.billing_interval is not None and body.billing_interval != subscription.billing_interval:
        subscription.pending_billing_interval = body.billing_interval

    amount = plan.price_yearly if interval == "annual" and plan.price_yearly else plan.price_monthly

    reference = f"eks_sub_{uuid.uuid4().hex[:20]}"
    try:
        result = paystack.initialize_transaction(
            email=current_user.email,
            amount=amount,
            reference=reference,
            callback_url=f"{settings.FRONTEND_URL}/dashboard/billing/payment-status?ref={reference}",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Paystack error: {str(e)}")

    subscription.provider_ref = reference
    db.commit()

    return RenewSubscriptionResponse(authorization_url=result["authorization_url"], reference=reference)
