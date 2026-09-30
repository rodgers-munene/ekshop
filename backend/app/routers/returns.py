from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
import uuid
from typing import Optional
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import desc

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_active_user, require_admin
from app.models.user import User, UserRole
from app.models.commerce import Order, OrderItem, ReturnRequest, ReturnItem, ReturnStatus, ReturnReason, OrderStatus
from app.models.shop import Shop
from app.schemas.commerce import (
    ReturnRequestCreate,
    ReturnRequestRead,
    ReturnRequestListResponse,
    ReturnStatusUpdate,
)
from app.services.notifications import create_notification

returns_router = APIRouter(prefix="/returns", tags=["returns"])


@returns_router.post(
    "/",
    response_model=ReturnRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="Request a return for an order",
)
def create_return_request(
    payload: ReturnRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    order = db.query(Order).filter(
        Order.id == payload.order_id,
        Order.buyer_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check if order is eligible for return (delivered within last 14 days)
    from datetime import datetime, timedelta, timezone
    if order.status != OrderStatus.delivered:
        raise HTTPException(status_code=400, detail="Only delivered orders can be returned")

    if order.updated_at < datetime.now(timezone.utc) - timedelta(days=14):
        raise HTTPException(status_code=400, detail="Return window has expired (14 days)")

    # Check if return already exists for this order
    existing = db.query(ReturnRequest).filter(
        ReturnRequest.order_id == order.id,
        ReturnRequest.buyer_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Return already requested for this order")

    # Validate items belong to this order
    total_refund = "0.00"
    return_items = []
    for item_data in payload.items:
        order_item = db.query(OrderItem).filter(
            OrderItem.id == item_data.order_item_id,
            OrderItem.order_id == order.id,
        ).first()
        if not order_item:
            raise HTTPException(status_code=404, detail=f"Order item {item_data.order_item_id} not found")

        if item_data.quantity > order_item.quantity:
            raise HTTPException(status_code=400, detail=f"Quantity exceeds ordered amount for item {order_item.id}")

        # Calculate refund amount for this item
        from decimal import Decimal
        unit_price = Decimal(order_item.unit_price)
        refund = unit_price * item_data.quantity
        total_refund = str(Decimal(total_refund) + refund)

        return_items.append(ReturnItem(
            order_item_id=item_data.order_item_id,
            quantity=item_data.quantity,
            refund_amount=str(refund),
            condition=item_data.condition,
        ))

    return_request = ReturnRequest(
        order_id=order.id,
        buyer_id=current_user.id,
        shop_id=order.shop_id,
        reason=payload.reason,
        reason_detail=payload.reason_detail,
        refund_amount=total_refund,
    )
    db.add(return_request)
    db.flush()

    for ri in return_items:
        ri.return_request_id = return_request.id
        db.add(ri)

    db.commit()
    db.refresh(return_request)

    # Notify seller
    if order.shop and order.shop.seller_id:
        create_notification(
            db,
            user_id=order.shop.seller_id,
            type="return_requested",
            title=f"Return requested for order {order.id}",
            body=f"Buyer {current_user.first_name} requested a return: {payload.reason.value}",
            data={"return_request_id": str(return_request.id), "order_id": str(order.id)},
        )

    return return_request


@returns_router.get(
    "/",
    response_model=ReturnRequestListResponse,
    summary="Get my return requests",
)
def list_my_returns(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[ReturnStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(ReturnRequest).filter(ReturnRequest.buyer_id == current_user.id)
    if status_filter:
        query = query.filter(ReturnRequest.status == status_filter)

    total = query.count()
    results = (
        query.options(selectinload(ReturnRequest.items).selectinload(ReturnItem.order_item))
        .order_by(desc(ReturnRequest.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ReturnRequestListResponse(total=total, page=page, limit=limit, results=results)


@returns_router.get(
    "/{return_id}",
    response_model=ReturnRequestRead,
    summary="Get a specific return request",
)
def get_return(
    return_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return_req = db.query(ReturnRequest).filter(
        ReturnRequest.id == return_id,
        ReturnRequest.buyer_id == current_user.id,
    ).options(selectinload(ReturnRequest.items).selectinload(ReturnItem.order_item)).first()
    if not return_req:
        raise HTTPException(status_code=404, detail="Return request not found")
    return return_req


@returns_router.patch(
    "/{return_id}/cancel",
    response_model=ReturnRequestRead,
    summary="Cancel a return request (buyer)",
)
def cancel_return(
    return_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return_req = db.query(ReturnRequest).filter(
        ReturnRequest.id == return_id,
        ReturnRequest.buyer_id == current_user.id,
    ).first()
    if not return_req:
        raise HTTPException(status_code=404, detail="Return request not found")

    if return_req.status not in (ReturnStatus.requested, ReturnStatus.approved):
        raise HTTPException(status_code=400, detail="Return cannot be cancelled at this stage")

    return_req.status = ReturnStatus.cancelled
    db.commit()
    db.refresh(return_req)
    return return_req


# ── Seller/Admin endpoints ──

@returns_router.get(
    "/seller",
    response_model=ReturnRequestListResponse,
    summary="Get return requests for my shop (seller)",
)
def list_seller_returns(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[ReturnStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")

    query = db.query(ReturnRequest).filter(ReturnRequest.shop_id == shop.id)
    if status_filter:
        query = query.filter(ReturnRequest.status == status_filter)

    total = query.count()
    results = (
        query.options(selectinload(ReturnRequest.items).selectinload(ReturnItem.order_item))
        .order_by(desc(ReturnRequest.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ReturnRequestListResponse(total=total, page=page, limit=limit, results=results)


@returns_router.patch(
    "/{return_id}",
    response_model=ReturnRequestRead,
    summary="Update return status (seller/admin)",
)
def update_return_status(
    return_id: uuid.UUID,
    payload: ReturnStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return_req = db.query(ReturnRequest).filter(ReturnRequest.id == return_id).first()
    if not return_req:
        raise HTTPException(status_code=404, detail="Return request not found")

    # Authorization: seller of the shop or admin
    is_seller = return_req.shop.seller_id == current_user.id
    is_admin = current_user.role == UserRole.admin
    if not (is_seller or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Validate state transitions
    valid_transitions = {
        ReturnStatus.requested: [ReturnStatus.approved, ReturnStatus.rejected],
        ReturnStatus.approved: [ReturnStatus.received, ReturnStatus.refunded],
        ReturnStatus.received: [ReturnStatus.refunded],
    }
    if return_req.status in valid_transitions:
        if payload.status not in valid_transitions[return_req.status]:
            raise HTTPException(status_code=400, detail=f"Invalid transition from {return_req.status.value} to {payload.status.value}")

    old_status = return_req.status
    return_req.status = payload.status
    if payload.admin_notes is not None:
        return_req.admin_notes = payload.admin_notes
    if payload.refund_amount is not None:
        return_req.refund_amount = payload.refund_amount

    if payload.status in (ReturnStatus.refunded, ReturnStatus.rejected, ReturnStatus.cancelled):
        return_req.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(return_req)

    # Notify buyer
    from app.services.notifications import create_notification
    status_messages = {
        ReturnStatus.approved: "Your return has been approved. Please ship the item back.",
        ReturnStatus.rejected: "Your return request has been rejected.",
        ReturnStatus.received: "We've received your return. Refund is being processed.",
        ReturnStatus.refunded: f"Your return has been refunded (KES {return_req.refund_amount}).",
    }
    if payload.status in status_messages:
        create_notification(
            db,
            user_id=return_req.buyer_id,
            type="return_update",
            title=f"Return {payload.status.value}",
            body=status_messages[payload.status],
            data={"return_request_id": str(return_req.id), "order_id": str(return_req.order_id)},
        )

    return return_req


@returns_router.get(
    "/admin",
    response_model=ReturnRequestListResponse,
    summary="Get all return requests (admin)",
)
def list_all_returns_admin(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[ReturnStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(ReturnRequest)
    if status_filter:
        query = query.filter(ReturnRequest.status == status_filter)

    total = query.count()
    results = (
        query.options(selectinload(ReturnRequest.items).selectinload(ReturnItem.order_item))
        .order_by(desc(ReturnRequest.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return ReturnRequestListResponse(total=total, page=page, limit=limit, results=results)


@returns_router.get(
    "/reasons",
    response_model=list[ReturnReason],
    summary="Get available return reasons",
)
def get_return_reasons():
    return list(ReturnReason)


@returns_router.get(
    "/statuses",
    response_model=list[ReturnStatus],
    summary="Get available return statuses",
)
def get_return_statuses():
    return list(ReturnStatus)