import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.dependencies.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.models.commerce import OrderGroup
from app.models.payment import PaymentIntent

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.get("/{order_id}")
def get_thermal_receipt(
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

    address = group.delivery_address or {}
    lines = []
    lines.append("=" * 40)
    lines.append("EKSHOP KENYA")
    lines.append("HYPERLOCAL MARKETPLACE")
    lines.append("=" * 40)
    lines.append(f"Order:     #{str(group.id)[:8]}")
    lines.append(f"Date:      {group.created_at.strftime('%d/%m/%Y %H:%M')}")
    lines.append(f"Customer:  {current_user.first_name} {current_user.last_name}")
    lines.append(f"Address:   {(address.get('exact_location') or address.get('town') or '').strip()}")
    lines.append("=" * 40)
    lines.append("QTY  ITEM                        AMT")
    lines.append("-" * 40)
    for order in group.orders:
        for item in order.items:
            name = (item.product_snapshot.get("name", "Product") if item.product_snapshot else "Product")[:22]
            qty = str(item.quantity)
            amt = f"KES {Decimal(item.line_total):.2f}"  # stored as a string
            lines.append(f"{qty:<4} {name:<22} {amt}")
    lines.append("-" * 40)
    lines.append(f"Subtotal:      KES {Decimal(str(group.subtotal or 0)):.2f}")
    lines.append(f"Delivery:      KES {Decimal(str(group.delivery_fee or 0)):.2f}")
    lines.append(f"TOTAL:         KES {Decimal(str(group.total or 0)):.2f}")
    lines.append("=" * 40)
    payment = (
        db.query(PaymentIntent)
        .filter(PaymentIntent.order_group_id == group.id)
        .order_by(PaymentIntent.created_at.desc())
        .first()
    )
    lines.append(f"Payment: {payment.provider.upper() if payment else 'N/A'}")
    lines.append(f"Ref:   {(payment.provider_ref if payment else None) or group.id}")
    lines.append("=" * 40)
    lines.append("Thank you for shopping local!")
    receipt_text = "\n".join(lines)
    return Response(content=receipt_text, media_type="text/plain", headers={"Content-Disposition": f"attachment; filename=receipt-{str(group.id)[:8]}.txt"})
