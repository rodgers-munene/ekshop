import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dependencies.auth import require_seller
from app.dependencies.database import get_db
from app.models.shop import Shop
from app.models.subscription import SubscriptionStatus
from app.models.user import User
from app.schemas.subscription import RenewSubscriptionResponse, SubscriptionRead
from app.services import paystack

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _get_my_subscription(db: Session, current_user: User):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()
    if not shop or not shop.subscription:
        raise HTTPException(status_code=404, detail="You don't have a subscription yet")
    return shop.subscription


@router.get(
    "/me",
    response_model=SubscriptionRead,
    status_code=status.HTTP_200_OK,
    summary="Get my subscription",
)
def get_my_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller),
):
    return _get_my_subscription(db, current_user)


@router.post(
    "/me/renew",
    response_model=RenewSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a renewal payment for my subscription",
    description="""
Generates a fresh Paystack transaction for the current plan's monthly price.
Does not change the subscription's status — it only flips to `active` once
the payment is confirmed (via the Paystack webhook, or `/auth/subscription-status`),
same as the original registration payment.
""",
)
def renew_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_seller),
):
    subscription = _get_my_subscription(db, current_user)

    if subscription.status == SubscriptionStatus.active:
        raise HTTPException(status_code=400, detail="Your subscription is already active")

    reference = f"eks_sub_{uuid.uuid4().hex[:20]}"
    try:
        result = paystack.initialize_transaction(
            email=current_user.email,
            amount=subscription.plan.price_monthly,
            reference=reference,
            callback_url=f"{settings.FRONTEND_URL}/dashboard/billing/payment-status?ref={reference}",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Paystack error: {str(e)}")

    subscription.provider_ref = reference
    db.commit()

    return RenewSubscriptionResponse(authorization_url=result["authorization_url"], reference=reference)
