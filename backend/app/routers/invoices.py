"""Customer invoice data endpoint."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.dependencies.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.models.commerce import OrderGroup, Order
from app.models.payment import PaymentIntent

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("/{order_id}")
def get_customer_invoice(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    group = (
        db.query(OrderGroup)
        .filter(OrderGroup.id == order_id, OrderGroup.buyer_id == current_user.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Order not found")

    payment = (
        db.query(PaymentIntent)
        .filter(PaymentIntent.order_group_id == group.id)
        .order_by(PaymentIntent.created_at.desc())
        .first()
    )

    address = group.delivery_address or {}
    items = []
    for order in group.orders:
        for item in order.items:
            # The name at time of purchase, not the product's current name.
            snapshot = item.product_snapshot or {}
            items.append({
                "name": snapshot.get("name") or (item.product.name if item.product else "Product"),
                "qty": item.quantity,
                "unit_price": str(item.unit_price),
                "subtotal": str(item.line_total),
            })

    delivery_fee = Decimal("0.00")
    try:
        delivery_fee = Decimal(group.delivery_fee or "0.00")
    except Exception:
        delivery_fee = Decimal("0.00")

    subtotal = Decimal(group.subtotal or "0.00")
    total = Decimal(group.total or "0.00")

    return {
        "invoice_id": f"INV-{group.id}",
        "order_id": str(group.id),
        "created_at": group.created_at.isoformat(),
        "customer_name": f"{current_user.first_name} {current_user.last_name}",
        "delivery_address": f"{address.get('exact_location') or address.get('town') or ''}, {address.get('county') or ''}".strip(", "),
        "payment_reference": payment.provider_ref if payment else None,
        "payment_status": group.status.value if hasattr(group.status, "value") else str(group.status),
        "items": items,
        "subtotal": str(subtotal),
        "delivery_fee": str(delivery_fee),
        "total": str(total),
        "currency": "KES",
    }
