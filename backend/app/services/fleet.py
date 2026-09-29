"""Fleet operations: rider onboarding gating, ping dispatch engine, the
wallet/ledger that backs rider payouts, and the metered (distance + surge)
pricing engine.

Everything money-side lives here so routers stay thin. Wallet mutation is
single-threaded through post_ledger_entry() with a balance_after stamped on
every row — the double-entry discipline the funds-splitting report asks for
without a formal offsetting row (delivery fees already touch the order
revenue side).
"""

import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.delivery import (
    Delivery,
    DeliveryAgent,
    DeliveryAgentStatus,
    DeliveryLedgerEntry,
    DeliveryOffer,
    DeliveryPricingRule,
    DeliveryStatus,
    KYCStatus,
    LedgerEntryType,
    LedgerStatus,
    OfferStatus,
    VehicleType,
)

EAST_AFRICA_TZ = timezone(timedelta(hours=3))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    if lat1 is None or lng1 is None or lat2 is None or lng2 is None:
        return float("inf")
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


# ──────────────────────────────────────────────────────────────────────────
# 1. KYC gating
# ──────────────────────────────────────────────────────────────────────────
def eligible_for_pings(agent: DeliveryAgent) -> bool:
    """A rider is dispatchable only after an admin approved their KYC and their
    vehicle/equipment was verified. Prevents unvetted riders from getting
    deliveries — the spec's core safety gate."""
    return (
        agent.status == DeliveryAgentStatus.active
        and agent.kyc_status == KYCStatus.approved
        and agent.equipment_verified
        and agent.current_order_id is None
        and agent.current_lat is not None
        and agent.current_lng is not None
    )


# ──────────────────────────────────────────────────────────────────────────
# 2. Ping dispatch engine
# ──────────────────────────────────────────────────────────────────────────
def find_candidates(
    db: Session,
    delivery: Delivery,
    radius_km: float | None = None,
    limit: int = 5,
    exclude_agent_id: uuid.UUID | None = None,
) -> list[DeliveryAgent]:
    """Dispatchable riders within radius of the pickup point, nearest-first.

    PostGIS note: the schema keeps plain lat/lng columns (no PostGIS
    extension), so the radius scan uses the haversine in Python. When a
    deployment enables PostGIS this is the one function to re-implement with
    ST_DWithin(); every caller stays unchanged."""
    radius = float(radius_km if radius_km is not None else settings.PING_RADIUS_KM)

    pickup_lat, pickup_lng = _pickup_point(db, delivery)
    if pickup_lat is None or pickup_lng is None:
        return []

    agents = (
        db.query(DeliveryAgent)
        .filter(DeliveryAgent.status == DeliveryAgentStatus.active)
        .filter(DeliveryAgent.kyc_status == KYCStatus.approved)
        .filter(DeliveryAgent.equipment_verified.is_(True))
        .filter(DeliveryAgent.current_order_id.is_(None))
        .all()
    )

    ranked = []
    for agent in agents:
        if exclude_agent_id is not None and agent.id == exclude_agent_id:
            continue
        d = _haversine_km(pickup_lat, pickup_lng, agent.current_lat, agent.current_lng)
        if d <= radius:
            ranked.append((d, agent))
    if not ranked:
        return []
    ranked.sort(key=lambda pair: pair[0])
    return [agent for _, agent in ranked[:limit]]


def _pickup_point(db: Session, delivery: Delivery) -> tuple[float | None, float | None]:
    """Lat/lng to run the radius scan from — the shop's location, where a
    rider must travel to pick up first."""
    order = delivery.order
    shop = order.shop if order is not None else None
    if shop is None:
        return None, None
    return shop.lat, shop.lng


def dispatch(
    db: Session,
    delivery: Delivery,
    radius_km: float | None = None,
    expires_after_seconds: int | None = None,
) -> list[DeliveryOffer]:
    """Opens the ping window for a delivery.

    Riders are offered strictly sequentially, nearest first: the closest
    candidate gets a live (pending) offer with a 30 s countdown; every other
    candidate is parked in the queue. When a pending offer expires or is
    declined, promote_next_in_queue() wakes the next rider with a fresh 30 s
    window. This satisfies the design's 30-second sequential fallback without
    a background worker."""
    if delivery.status != DeliveryStatus.pending:
        raise ValueError(f"Cannot dispatch delivery in status {delivery.status.value}")

    candidates = find_candidates(db, delivery, radius_km=radius_km)
    if not candidates:
        return []

    expires_at = utcnow() + timedelta(seconds=int(expires_after_seconds or settings.PING_EXPIRY_SECONDS))
    offers = []
    for position, agent in enumerate(candidates, start=1):
        offer = DeliveryOffer(
            delivery_id=delivery.id,
            agent_id=agent.id,
            status=OfferStatus.pending if position == 1 else OfferStatus.queued,
            queue_position=position,
            expires_at=expires_at if position == 1 else None,
        )
        db.add(offer)
        offers.append(offer)
    db.flush()
    return offers


def accept_offer(db: Session, offer: DeliveryOffer, agent: DeliveryAgent) -> Delivery:
    """Rider accepts a ping. Validates the window is still open, cancels the
    sibling offers for the same delivery, and attaches the rider — the same
    effect as an admin manual assign."""
    if offer.status != OfferStatus.pending:
        raise ValueError("This ping is no longer open")
    if offer.agent_id != agent.id:
        raise ValueError("This ping was not sent to you")
    if offer.expires_at is not None and offer.expires_at < utcnow():
        offer.status = OfferStatus.expired
        offer.responded_at = utcnow()
        db.flush()
        raise ValueError("This ping has expired")
    if agent.current_order_id is not None:
        raise ValueError("You already have an active delivery")

    delivery = db.get(Delivery, offer.delivery_id)
    if delivery is None or delivery.status != DeliveryStatus.pending:
        offer.status = OfferStatus.cancelled
        offer.responded_at = utcnow()
        db.flush()
        raise ValueError("This delivery is no longer looking for a rider")

    stale = (
        db.query(DeliveryOffer)
        .filter(DeliveryOffer.delivery_id == delivery.id)
        .filter(DeliveryOffer.id != offer.id)
        .all()
    )
    now = utcnow()
    for other in stale:
        other.status = OfferStatus.cancelled
        other.responded_at = now

    offer.status = OfferStatus.accepted
    offer.responded_at = now
    delivery.agent_id = agent.id
    delivery.status = DeliveryStatus.assigned
    agent.current_order_id = delivery.order_id
    agent.status = DeliveryAgentStatus.busy
    db.flush()
    return delivery


def decline_offer(db: Session, offer: DeliveryOffer, agent: DeliveryAgent) -> DeliveryOffer:
    if offer.agent_id != agent.id:
        raise ValueError("This ping was not sent to you")
    if offer.status != OfferStatus.pending:
        raise ValueError("This ping is no longer open")

    offer.status = OfferStatus.declined
    offer.responded_at = utcnow()
    db.flush()

    # Sequential fallback: promote the next rider in the chain to pending
    # with a fresh expiry window.
    promote_next_in_queue(db, offer.delivery_id, after_position=offer.queue_position)
    return offer


def promote_next_in_queue(db: Session, delivery_id: uuid.UUID, after_position: int) -> DeliveryOffer | None:
    next_offer = (
        db.query(DeliveryOffer)
        .filter(DeliveryOffer.delivery_id == delivery_id)
        .filter(DeliveryOffer.status == OfferStatus.queued)
        .filter(DeliveryOffer.queue_position > after_position)
        .order_by(DeliveryOffer.queue_position)
        .first()
    )
    if next_offer is not None:
        next_offer.status = OfferStatus.pending
        next_offer.expires_at = utcnow() + timedelta(seconds=settings.PING_EXPIRY_SECONDS)
        db.flush()
    return next_offer


def expire_stale_offers(db: Session) -> int:
    """Lazily expires pending offers whose deadline has passed (no background
    worker required), promoting the next queued rider for each delivery."""
    now = utcnow()
    stale = (
        db.query(DeliveryOffer)
        .filter(DeliveryOffer.status == OfferStatus.pending)
        .filter(DeliveryOffer.expires_at.isnot(None))
        .filter(DeliveryOffer.expires_at < now)
        .all()
    )
    expired = 0
    for offer in stale:
        offer.status = OfferStatus.expired
        offer.responded_at = now
        expired += 1
        promote_next_in_queue(db, offer.delivery_id, after_position=offer.queue_position)
    if expired:
        db.flush()
    return expired


# ──────────────────────────────────────────────────────────────────────────
# 3. Wallet ledger + B2C payouts + reversal
# ──────────────────────────────────────────────────────────────────────────
def post_ledger_entry(
    db: Session,
    agent: DeliveryAgent,
    entry_type: LedgerEntryType,
    amount: Decimal,
    *,
    delivery_id: uuid.UUID | None = None,
    reference: str | None = None,
    status: LedgerStatus = LedgerStatus.succeeded,
    failure_reason: str | None = None,
) -> DeliveryLedgerEntry:
    """Applies a signed amount change to a rider's wallet, stamping the running
    balance on the entry row. All wallet writes must go through here."""
    balance = Decimal(agent.wallet_balance or 0)
    new_balance = (balance + amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    entry = DeliveryLedgerEntry(
        agent_id=agent.id,
        delivery_id=delivery_id,
        entry_type=entry_type,
        amount=amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        balance_after=new_balance,
        reference=reference,
        status=status,
        failure_reason=failure_reason,
    )
    agent.wallet_balance = new_balance
    db.add(entry)
    db.flush()
    return entry


def credit_delivery_earnings(db: Session, delivery: Delivery, agent: DeliveryAgent) -> DeliveryLedgerEntry:
    """Credits the rider's share of the order delivery fee when a delivery is
    completed. RIDER_PAYOUT_SHARE (default 80%) of the fee the buyer paid is
    the rider's earning. Idempotent per delivery."""
    existing = (
        db.query(DeliveryLedgerEntry)
        .filter(DeliveryLedgerEntry.delivery_id == delivery.id)
        .filter(DeliveryLedgerEntry.entry_type == LedgerEntryType.earning)
        .first()
    )
    if existing is not None:
        return existing

    order = delivery.order
    fee = Decimal("0.00")
    if order is not None and order.delivery_fee:
        fee = Decimal(order.delivery_fee or "0.00")
    if fee <= 0 and order is not None and order.group is not None:
        group_fee = Decimal(order.group.delivery_fee or "0.00")
        if group_fee > 0:
            count = max(len(order.group.orders), 1)
            fee = group_fee / count

    share = (fee * Decimal(str(settings.RIDER_PAYOUT_SHARE))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return post_ledger_entry(db, agent, LedgerEntryType.earning, share, delivery_id=delivery.id)


def create_manual_payout(db: Session, agent: DeliveryAgent, amount: Decimal) -> DeliveryLedgerEntry:
    """Admin-triggered B2C disbursement. Posts a PENDING debit entry (kept on
    the books but not yet finalized); the B2C caller reconciles the entry via
    mark_payout_result."""
    return post_ledger_entry(
        db,
        agent,
        LedgerEntryType.b2c_payout,
        -amount,
        status=LedgerStatus.pending,
    )


def mark_payout_queued(db: Session, entry: DeliveryLedgerEntry, reference: str) -> DeliveryLedgerEntry:
    """Records that Daraja accepted (but not yet settled) a B2C disbursement.
    ResponseCode 0 from the initiation means QUEUED, not final: the entry stays
    pending and `reference` stores the OriginatorConversationID so the Result
    callback (/payments/b2c/callback) can reconcile it later."""
    if entry.status != LedgerStatus.pending:
        return entry
    entry.reference = reference
    db.flush()
    return entry


def find_pending_payout(db: Session, originator_conversation_id: str) -> DeliveryLedgerEntry | None:
    """Looks up a rider payout that is mid-flight pending its Daraja Result
    callback, matched by the OriginatorConversationID echoed back to us."""
    if not originator_conversation_id:
        return None
    return (
        db.query(DeliveryLedgerEntry)
        .filter(DeliveryLedgerEntry.entry_type == LedgerEntryType.b2c_payout)
        .filter(DeliveryLedgerEntry.status == LedgerStatus.pending)
        .filter(DeliveryLedgerEntry.reference == originator_conversation_id)
        .order_by(DeliveryLedgerEntry.created_at.desc())
        .first()
    )


def mark_payout_result(
    db: Session,
    entry: DeliveryLedgerEntry,
    *,
    reference: str | None,
    succeeded: bool,
    failure_reason: str | None = None,
) -> DeliveryLedgerEntry:
    """Reconciles a pending B2C ledger entry after the Daraja call. On failure
    the provisional debit is reversed with an offsetting reversal entry so the
    wallet stays consistent."""
    if entry.status != LedgerStatus.pending:
        return entry

    if succeeded:
        entry.status = LedgerStatus.succeeded
        entry.reference = reference
    else:
        entry.status = LedgerStatus.failed
        entry.failure_reason = failure_reason
        agent = db.get(DeliveryAgent, entry.agent_id)
        if agent is not None:
            post_ledger_entry(
                db,
                agent,
                LedgerEntryType.reversal,
                -entry.amount,  # entry.amount is negative, so this credits it back
                delivery_id=entry.delivery_id,
                reference=reference,
            )
    db.flush()
    return entry


# ──────────────────────────────────────────────────────────────────────────
# 4. Metered pricing + surge engine
# ──────────────────────────────────────────────────────────────────────────
def get_pricing_rule(db: Session, vehicle_type: VehicleType) -> DeliveryPricingRule | None:
    return (
        db.query(DeliveryPricingRule)
        .filter(DeliveryPricingRule.vehicle_type == vehicle_type)
        .filter(DeliveryPricingRule.is_active.is_(True))
        .first()
    )


def calculate_metered_fee(
    *,
    distance_km: float,
    duration_min: float,
    vehicle_type: VehicleType,
    rule: DeliveryPricingRule,
    now: datetime | None = None,
    raining: bool = False,
) -> tuple[Decimal, dict]:
    """base + per_km*km + per_min*min, multiplied by the surge factors
    (peak-hours × rain × supply/demand), then capped at max_surge_cap.

    `now` is injectable for deterministic tests. Peak hours = 17:00–20:00
    Mon–Sat (evening rush). Rain applies the rule's rain_multiplier when the
    caller reports rain (e.g. OpenWeather)."""
    now = now or utcnow().astimezone(EAST_AFRICA_TZ)

    peak = _is_peak_hour(now)
    rain_mult = Decimal(rule.rain_multiplier) if raining else Decimal("1.00")
    peak_mult = Decimal(rule.peak_hours_multiplier) if peak else Decimal("1.00")
    supply_mult = Decimal(rule.supply_demand_multiplier)

    surge = max(Decimal("1.00"), rain_mult * peak_mult * supply_mult)
    cap = Decimal(rule.max_surge_cap)
    surge = min(surge, max(Decimal("1.00"), cap))
    surge = surge.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    base = Decimal(rule.base_fare)
    per_km = Decimal(rule.per_km_rate) * Decimal(str(distance_km))
    per_min = Decimal(rule.per_minute_rate) * Decimal(str(duration_min))
    raw = base + per_km + per_min
    total = (raw * surge).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    breakdown = {
        "base_fare": str(base.quantize(Decimal("0.01"))),
        "per_km": str(per_km.quantize(Decimal("0.01"))),
        "per_minute": str(per_min.quantize(Decimal("0.01"))),
        "surge_multiplier": str(surge),
        "peak_hours": peak,
        "raining": raining,
        "rain_multiplier": str(rain_mult),
        "peak_hours_multiplier": str(peak_mult),
        "supply_demand_multiplier": str(supply_mult),
        "currency": rule.currency or "KES",
    }
    return total, breakdown


def _is_peak_hour(now: datetime) -> bool:
    if now.weekday() == 6:
        return False
    return 17 <= now.hour < 20