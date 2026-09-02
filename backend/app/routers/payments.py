import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dependencies.auth import get_current_active_user
from app.dependencies.database import get_db
from app.models.user import User
from app.models.commerce import OrderGroup, OrderGroupStatus, OrderStatus, Order
from app.models.payment import PaymentIntent, Payment, PaymentStatus
from app.models.analytics import EventType
from app.schemas.payment import (
    StkPushRequest,
    StkPushResponse,
    PaystackInitRequest,
    PaystackInitResponse,
    PaystackVerifyResponse,
)
from app.services import mpesa, paystack
from app.services import recommendations as rec_service
from app.services.notifications import create_notification, notify_admins_of_new_order

router = APIRouter(prefix="/payments", tags=["payments"])


def _mark_order_paid(db: Session, order_group_id: uuid.UUID) -> None:
    order_group = db.query(OrderGroup).filter(OrderGroup.id == order_group_id).first()
    order_group.status = OrderGroupStatus.paid
    for order in order_group.orders:
        order.status = OrderStatus.confirmed
        notify_admins_of_new_order(db, order)
        for item in order.items:
            # feeds the recommendation engine's trending/purchase-affinity signals;
            # session_id here is synthetic since this fires server-side on payment
            # confirmation, not from a browser session
            rec_service.log_event(
                db,
                session_id=f"order:{order_group_id}",
                event_type=EventType.purchase,
                user_id=order_group.buyer_id,
                product_id=item.product_id,
            )

    create_notification(
        db,
        user_id=order_group.buyer_id,
        type="payment_success",
        title="Payment received",
        body=f"We've received your payment of KES {order_group.total}.",
        data={"order_group_id": str(order_group.id)},
    )

@router.post("/mpesa/stk-push", response_model=StkPushResponse, status_code=201)
def mpesa_stk_push(
    payload: StkPushRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    #get the order, must belong to this buyer and be unpaid
    order_group = db.query(OrderGroup).filter(
        OrderGroup.id == payload.order_group_id,
        OrderGroup.buyer_id == current_user.id,
        OrderGroup.status == OrderGroupStatus.pending_payment,
    ).first()
    if not order_group:
        raise HTTPException(404, "Order not found or already paid")

    # call Safaricom
    try:
        token = mpesa.get_access_token()
        result = mpesa.initiate_stk_push(
            access_token=token,
            phone=payload.phone,
            amount=int(float(order_group.total)),  # M-Pesa needs integer KES
            order_ref=str(order_group.id)[:12],    # max 12 chars
        )
    except Exception as e:
        raise HTTPException(502, f"M-Pesa error: {str(e)}")

    # save the attempt
    intent = PaymentIntent(
        order_group_id=order_group.id,
        user_id=current_user.id,
        provider="mpesa",
        provider_ref=result["CheckoutRequestID"],
        amount=order_group.total,
    )
    db.add(intent)
    db.commit()

    return StkPushResponse(
        message="Payment prompt sent to your phone",
        checkout_request_id=result["CheckoutRequestID"],
    )
    
    
@router.post("/mpesa/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    callback = data["Body"]["stkCallback"]

    result_code = callback["ResultCode"]
    checkout_request_id = callback["CheckoutRequestID"]

    # find the PaymentIntent Safaricom is responding to
    intent = db.query(PaymentIntent).filter(
        PaymentIntent.provider_ref == checkout_request_id
    ).first()

    if not intent:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}  # unknown ref, ignore

    if result_code != 0:
        # payment failed, record it, leave order as pending_payment
        intent.status = "failed"
        db.commit()
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # payment succeeded, extract metadata from callback
    items = {i["Name"]: i["Value"] for i in callback["CallbackMetadata"]["Item"]}
    receipt = items.get("MpesaReceiptNumber")
    amount = items.get("Amount")

    # idempotency check, don't process the same payment twice
    existing = db.query(Payment).filter(Payment.provider_ref == receipt).first()
    if existing:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # create permanent payment record
    payment = Payment(
        order_group_id=intent.order_group_id,
        user_id=intent.user_id,
        provider="mpesa",
        provider_ref=receipt,
        amount=str(amount),
        status="success",
        raw_response=data,
    )
    db.add(payment)
    intent.status = "success"

    _mark_order_paid(db, intent.order_group_id)

    db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.post("/paystack/initialize", response_model=PaystackInitResponse, status_code=201)
def paystack_initialize(
    payload: PaystackInitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    order_group = db.query(OrderGroup).filter(
        OrderGroup.id == payload.order_group_id,
        OrderGroup.buyer_id == current_user.id,
        OrderGroup.status == OrderGroupStatus.pending_payment,
    ).first()
    if not order_group:
        raise HTTPException(404, "Order not found or already paid")

    reference = f"eks_{uuid.uuid4().hex[:20]}"

    try:
        result = paystack.initialize_transaction(
            email=current_user.email,
            amount=order_group.total,
            reference=reference,
            callback_url=f"{settings.FRONTEND_URL}/orders/{order_group.id}?paystack_ref={reference}",
        )
    except Exception as e:
        raise HTTPException(502, f"Paystack error: {str(e)}")

    intent = PaymentIntent(
        order_group_id=order_group.id,
        user_id=current_user.id,
        provider="paystack",
        provider_ref=reference,
        amount=order_group.total,
    )
    db.add(intent)
    db.commit()

    return PaystackInitResponse(
        authorization_url=result["authorization_url"],
        reference=reference,
    )


@router.post("/paystack/callback")
async def paystack_callback(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("x-paystack-signature")

    if not paystack.verify_webhook_signature(raw_body, signature):
        raise HTTPException(401, "Invalid signature")

    data = (await request.json())
    event = data.get("event")
    if event != "charge.success":
        return {"status": "ignored"}

    tx = data["data"]
    reference = tx["reference"]

    intent = db.query(PaymentIntent).filter(PaymentIntent.provider_ref == reference).first()
    if not intent:
        return {"status": "ignored"}

    # idempotency check, don't process the same payment twice
    existing = db.query(Payment).filter(Payment.provider_ref == reference).first()
    if existing:
        return {"status": "already processed"}

    if tx.get("status") != "success":
        intent.status = PaymentStatus.failed
        db.commit()
        return {"status": "recorded"}

    payment = Payment(
        order_group_id=intent.order_group_id,
        user_id=intent.user_id,
        provider="paystack",
        provider_ref=reference,
        amount=str(tx["amount"] / 100),
        status=PaymentStatus.success,
        channel=tx.get("channel"),
        raw_response=data,
    )
    db.add(payment)
    intent.status = PaymentStatus.success

    _mark_order_paid(db, intent.order_group_id)

    db.commit()
    return {"status": "recorded"}


def _reconcile_paystack_intent(db: Session, intent: PaymentIntent) -> PaymentStatus:
    """Checks Paystack's own record for a payment intent and marks the order paid
    if it succeeded there, regardless of whether our webhook or redirect ever fired."""
    if intent.status == PaymentStatus.success:
        return intent.status

    try:
        result = paystack.verify_transaction(intent.provider_ref)
    except Exception as e:
        raise HTTPException(502, f"Paystack error: {str(e)}")

    if result.get("status") == "success":
        existing = db.query(Payment).filter(Payment.provider_ref == intent.provider_ref).first()
        if not existing:
            payment = Payment(
                order_group_id=intent.order_group_id,
                user_id=intent.user_id,
                provider="paystack",
                provider_ref=intent.provider_ref,
                amount=str(result["amount"] / 100),
                status=PaymentStatus.success,
                channel=result.get("channel"),
                raw_response=result,
            )
            db.add(payment)
            intent.status = PaymentStatus.success
            _mark_order_paid(db, intent.order_group_id)
            db.commit()
    elif result.get("status") == "failed":
        intent.status = PaymentStatus.failed
        db.commit()

    return intent.status


@router.get("/paystack/verify/{reference}", response_model=PaystackVerifyResponse)
def paystack_verify(
    reference: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lets the frontend confirm payment status immediately after the buyer is
    redirected back from Paystack, without waiting on the webhook."""
    intent = db.query(PaymentIntent).filter(
        PaymentIntent.provider_ref == reference,
        PaymentIntent.user_id == current_user.id,
    ).first()
    if not intent:
        raise HTTPException(404, "Payment not found")

    status_ = _reconcile_paystack_intent(db, intent)
    return PaystackVerifyResponse(status=status_, order_group_id=intent.order_group_id)


@router.get("/paystack/verify-order/{order_group_id}", response_model=PaystackVerifyResponse)
def paystack_verify_order(
    order_group_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Fallback reconciliation for buyers who never made it back to our callback
    URL (e.g. the Paystack checkout page crashed after they paid via mobile money).
    Looks up the latest Paystack payment intent for this order and re-checks it
    against Paystack directly, so the buyer isn't stuck on 'pending' waiting on a
    webhook that may be missing or delayed."""
    intent = db.query(PaymentIntent).filter(
        PaymentIntent.order_group_id == order_group_id,
        PaymentIntent.user_id == current_user.id,
        PaymentIntent.provider == "paystack",
    ).order_by(PaymentIntent.created_at.desc()).first()
    if not intent:
        raise HTTPException(404, "No Paystack payment found for this order")

    status_ = _reconcile_paystack_intent(db, intent)
    return PaystackVerifyResponse(status=status_, order_group_id=intent.order_group_id)

