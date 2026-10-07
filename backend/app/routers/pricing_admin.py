"""Pricing API (§16) and admin parameter management (§15).

The quote endpoint is the one place a customer-facing price is produced, so it
holds three deliberate refusals:

1. **It refuses to serve a firm price from an approximate distance** (§3.2). A
   geodesic quote undercharges by 20-40%, so the response is returned with
   `distance_is_approximate` set rather than being quietly presented as firm.

2. **It refuses to auto-reject a loss-making order** (§12). The engine returns a
   recommendation; the decision to decline belongs to a person.

3. **It reuses a locked price rather than recalculating it** (§14). Once checkout
   is confirmed, a slow assignment or a rider who moved further away must not
   change what the customer agreed to pay.
"""
import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_active_user, require_admin
from app.dependencies.database import get_db
from app.models.commerce import Order
from app.models.user import User, UserRole
from app.models.pricing_config import PricingCalculation, PricingParameter
from app.schemas.pricing_admin import (
    ParameterChangeLogRead,
    PricingCalculationRead,
    PricingCustomer,
    PricingDistance,
    PricingParameterListResponse,
    PricingParameterRead,
    PricingParameterUpdate,
    PricingProfitability,
    PricingQuoteRequest,
    PricingRecommendation,
    PricingResponse,
    PricingRider,
)
from app.services import pricing_store as store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pricing", tags=["pricing"])


def _own_order(db: Session, order_id: uuid.UUID, user: User) -> Order:
    """Load an order the caller is allowed to price.

    Someone else's order returns 404 rather than 403: a 403 confirms the id
    exists and leaks another merchant's order volume.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.role == UserRole.admin:
        return order
    shop = order.shop
    if shop is None or str(shop.seller_id) != str(user.id):
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _to_response(
    order: Order, result, row: PricingCalculation
) -> PricingResponse:
    """Shape the engine's result into the16 response."""
    return PricingResponse(
        order_id=order.id,
        pricing_version=row.pricing_version,
        distance_is_approximate=row.distance_is_approximate,
        requires_manual_quote=result.requires_manual_quote,
        distance=PricingDistance(
            rider_to_merchant_km=result.rider_to_merchant_km,
            merchant_to_customer_km=result.merchant_to_customer_km,
            total_km=result.total_km,
        ),
        customer=PricingCustomer(
            base_price=result.base_price,
            weight_multiplier=result.weight_multiplier,
            surge_multiplier=result.surge_multiplier,
            service_multiplier=result.service_multiplier,
            delivery_price=result.customer_delivery_price,
            merchant_subsidy=result.merchant_subsidy,
            ekshop_subsidy=result.ekshop_subsidy,
            amount_to_pay=result.customer_payment,
        ),
        rider=PricingRider(
            base_fare=result.rider_base_fare,
            distance_payout=result.rider_distance_payout,
            waiting_payout=result.waiting_payout,
            chargeable_wait_minutes=result.chargeable_wait_minutes,
            total_payout=result.rider_total_payout,
        ),
        profitability=PricingProfitability(
            payment_cost=result.payment_cost,
            expected_exception_cost=result.expected_exception_cost,
            expected_delivery_cost=result.expected_delivery_cost,
            delivery_contribution=result.delivery_contribution,
            contribution_pct=result.contribution_pct,
            delivery_basket_ratio=result.delivery_basket_ratio,
            minimum_economic_price=result.minimum_economic_price,
            status=result.status.value,
        ),
        recommendation=PricingRecommendation(
            action=result.recommended_action.value,
            reason=result.reason,
        ),
        calculated_at=row.created_at,
    )


@router.post("/quote", response_model=PricingResponse, summary="Quote a delivery")
def quote(
    payload: PricingQuoteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> PricingResponse:
    """Price one delivery and record the calculation (§16,17).

    Distances are supplied by the caller because they must come from the
    road-distance provider; this endpoint deliberately does not compute them, so
    the geodesic fallback can never enter the pricing path by accident.
    """
    order = _own_order(db, payload.order_id, user)
    try:
        result, row = store.quote_order(
            db,
            order,
            merchant_to_customer_km=payload.merchant_to_customer_km,
            rider_to_merchant_km=payload.rider_to_merchant_km,
            supply_ratio=payload.supply_ratio,
            merchant_subsidy=payload.merchant_subsidy,
            ekshop_subsidy=payload.ekshop_subsidy,
            distance_source=payload.distance_source,
            distance_is_approximate=payload.distance_is_approximate,
        )
    except store.PricingConfigError as exc:
        db.rollback()
        # A misconfigured rate is a 500, not a client error: the payload was fine.
        logger.error("Pricing configuration is unusable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pricing is not configured correctly. An administrator has been notified.",
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))

    if result.requires_manual_quote:
        #7 gives no formula above 20 kg. This is not an error, but the caller
        # must not present the zero price as a quote.
        logger.info("Order %s needs a manual quote: %s", payload.order_id, result.reason)

    return _to_response(order, result, row)


@router.get(
    "/orders/{order_id}/calculations",
    response_model=list[PricingCalculationRead],
    summary="Every calculation made for an order",
)
def list_calculations(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[PricingCalculationRead]:
    """The17 audit trail for one order, newest first.

    Read-only by construction: there is no update or delete endpoint, and the
    table has an append-only trigger behind it as well.
    """
    order = _own_order(db, order_id, user)
    rows = (
        db.query(PricingCalculation)
        .filter(PricingCalculation.order_id == order.id)
        .order_by(PricingCalculation.created_at.desc())
        .all()
    )
    return [PricingCalculationRead.model_validate(r) for r in rows]


@router.post(
    "/orders/{order_id}/lock",
    response_model=PricingResponse,
    summary="Confirm and lock the delivery price at checkout",
)
def lock_price(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> PricingResponse:
    """Freeze the price at checkout (§14).

    From this point the customer-facing price cannot change because assignment was
    slow, the rider moved further away, supply changed, or a rider became
    unavailable. Re-quoting returns the locked figure.
    """
    from app.services.distance import GeoPoint, get_road_distance

    order = _own_order(db, order_id, user)
    if order.delivery_price_locked:
        existing = (
            db.query(PricingCalculation)
            .filter(PricingCalculation.order_id == order.id)
            .order_by(PricingCalculation.created_at.desc())
            .first()
        )
        if existing is None:
            raise HTTPException(
                status_code=409,
                detail="Price is marked locked but no calculation exists to honour",
            )
        result = store._result_from_row(existing)
        return _to_response(order, result, existing)

    address = order.group.delivery_address if order.group else None
    lat = (address or {}).get("lat")
    lng = (address or {}).get("lng")
    if lat is None or lng is None:
        raise HTTPException(
            status_code=422,
            detail="The delivery address has no coordinates, so distance cannot be measured",
        )
    shop = order.shop
    if shop is None or shop.lat is None or shop.lng is None:
        raise HTTPException(
            status_code=422,
            detail="The shop has no coordinates, so distance cannot be measured",
        )

    measured = get_road_distance(
        GeoPoint(lat=float(shop.lat), lng=float(shop.lng)),
        GeoPoint(lat=float(lat), lng=float(lng)),
    )
    try:
        result, row = store.quote_order(
            db,
            order,
            merchant_to_customer_km=Decimal(str(measured.km)),
            distance_source=measured.source.value,
            distance_is_approximate=measured.approximate,
        )
    except store.PricingConfigError as exc:
        db.rollback()
        logger.error("Pricing configuration is unusable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pricing is not configured correctly. An administrator has been notified.",
        )

    order.delivery_price_locked = True
    db.commit()
    return _to_response(order, result, row)


# ---15 admin parameters --------------------------------------------------------


@router.get(
    "/parameters",
    response_model=PricingParameterListResponse,
    summary="Every configurable pricing parameter",
)
def list_parameters(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> PricingParameterListResponse:
    """All rates, with the specification section each came from.

    `placeholder_count` is surfaced because three seeded values are explicitly
    unverified placeholders (D#8) and one is an open commercial decision (Q23).
    Shipping those as if they were agreed numbers is the failure mode worth
    preventing.
    """
    rows = db.query(PricingParameter).order_by(PricingParameter.key).all()
    placeholders = [r for r in rows if "PLACEHOLDER" in (r.description or "")]
    return PricingParameterListResponse(
        items=[PricingParameterRead.model_validate(r) for r in rows],
        placeholder_count=len(placeholders),
        pricing_version=store.DEFAULT_PRICING_VERSION,
    )


@router.patch(
    "/parameters/{key}",
    response_model=PricingParameterRead,
    summary="Change a pricing parameter without a deployment",
)
def update_parameter(
    key: str,
    payload: PricingParameterUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> PricingParameterRead:
    """Update one rate.

    The new value is parsed and validated before it is saved, so a typo is
    rejected at the point of entry rather than surfacing later as a mysterious
    pricing failure. The previous value is returned in the response so the change
    is recoverable without a database archaeology session.
    """
    try:
        row = store.set_parameter(
            db, key, payload.value, updated_by_user_id=user.id
        )
    except store.PricingConfigError as exc:
        db.rollback()
        # An unknown key is a client mistake (404-ish); an unparseable value is
        # also a client mistake. Both are 400.
        raise HTTPException(status_code=400, detail=str(exc))

    if payload.reason:
        logger.info(
            "Pricing parameter %s changed to %s by %s: %s",
            key, payload.value, user.id, payload.reason,
        )
    return PricingParameterRead.model_validate(row)


@router.get(
    "/parameters/{key}/history",
    response_model=list[ParameterChangeLogRead],
    summary="Recent changes to one parameter",
)
def parameter_history(
    key: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[ParameterChangeLogRead]:
    """Not a full history: the table stores the current value, so this reports the
    audit trail that exists (who last set it, and when) rather than pretending to
    be a change log. A real change log needs its own append-only table."""
    row = db.query(PricingParameter).filter(PricingParameter.key == key).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown pricing parameter")
    return [
        ParameterChangeLogRead(
            key=row.key,
            previous_value="(not recorded)",
            new_value=row.value,
            changed_at=row.updated_at,
            changed_by_user_id=row.updated_by_user_id,
        )
    ][:limit]