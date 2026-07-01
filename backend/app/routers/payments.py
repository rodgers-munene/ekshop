import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_active_user
from app.dependencies.database import get_db
from app.models.user import User
from app.models.commerce import OrderGroup, OrderGroupStatus, OrderStatus, Order
from app.models.payment import PaymentIntent, Payment
from app.schemas.payment import StkPushRequest, StkPushResponse
from app.services import mpesa

router = APIRouter(prefix="/payments", tags=["payments"])

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
        # payment failed — record it, leave order as pending_payment
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

    # update order group and all its orders
    order_group = db.query(OrderGroup).filter(
        OrderGroup.id == intent.order_group_id
    ).first()
    order_group.status = OrderGroupStatus.paid

    for order in order_group.orders:
        order.status = OrderStatus.confirmed

    db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted"}

