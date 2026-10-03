"""HTTP surface for the fulfillment state machine.

Three audiences, three sets of permissions:

* **Merchant** — may act only on fulfillments for orders in their own shop. The
  ownership check is `:func:`_merchant_fulfillment`; it is applied to every
  merchant route rather than trusted from the caller.
* **Rider** — may only see and move jobs assigned to them. A rider token is a
  different token type from a user token, so this cannot be reached with a
  customer session.
* **Ops/admin** — may override any job, with a mandatory logged reason.

Every state change goes through `app.services.fulfillment`, which owns the
transition rules. Nothing here writes `job.status` directly.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session, selectinload

from app.core.security import decode_access_token
from app.dependencies.auth import get_current_active_user, require_admin
from app.dependencies.database import get_db
from app.models.commerce import Order
from app.models.delivery import DeliveryAgent
from app.models.fulfillment import (
    AssignmentStatus,
    DeliveryAssignment,
    DeliveryJob,
    DeliveryJobStatus,
    Fulfillment,
)
from app.models.user import User, UserRole
from app.schemas.fulfillment import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentRespond,
    DeliveryJobDetail,
    FulfillmentCreate,
    FulfillmentDetail,
    FulfillmentListResponse,
    FulfillmentRead,
    FulfillmentSettlementRead,
    IssueOtpRequest,
    IssueOtpResponse,
    JobSettlementCreate,
    JobTransitionRequest,
    OverrideRequest,
    ReasonRequest,
)
from app.services import fulfillment as fs

router = APIRouter(prefix="/fulfillments", tags=["fulfillment"])
bearer_scheme = HTTPBearer(auto_error=False)

_agent_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate rider credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


# ── auth helpers ──────────────────────────────────────────────────────────────


def get_current_agent(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> DeliveryAgent:
    """Rider identity. Requires a token issued with `type: agent`."""
    if credentials is None:
        raise _agent_credentials_error
    try:
        payload = decode_access_token(credentials.credentials)
        agent_id: Optional[str] = payload.get("sub")
        if not agent_id or payload.get("type") != "agent":
            raise _agent_credentials_error
    except JWTError:
        raise _agent_credentials_error

    agent = db.query(DeliveryAgent).filter(DeliveryAgent.id == uuid.UUID(agent_id)).first()
    if not agent:
        raise _agent_credentials_error
    return agent


def _load_fulfillment(db: Session, fulfillment_id: uuid.UUID) -> Fulfillment:
    fulfillment = (
        db.query(Fulfillment)
        .options(
            selectinload(Fulfillment.jobs).selectinload(DeliveryJob.events),
            selectinload(Fulfillment.jobs).selectinload(DeliveryJob.assignments),
            selectinload(Fulfillment.settlement),
        )
        .filter(Fulfillment.id == fulfillment_id)
        .first()
    )
    if not fulfillment:
        raise HTTPException(status_code=404, detail="Fulfillment not found")
    return fulfillment


def _owns_fulfillment(fulfillment: Fulfillment, user: User) -> bool:
    """True when the order behind this fulfillment belongs to the user's shop.

    Admin is handled by the caller, not here, so a merchant can never widen
    their own access by holding a second role.
    """
    order = fulfillment.order
    if order is None or order.shop is None:
        return False
    return str(order.shop.seller_id) == str(user.id)


def _merchant_fulfillment(
    fulfillment_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> Fulfillment:
    """Load a fulfillment, enforcing that the caller owns it.

    Returns 404 rather than 403 for someone else's fulfillment: a 403 would
    confirm the id exists, which leaks another merchant's order volume.
    """
    fulfillment = _load_fulfillment(db, fulfillment_id)
    if user.role == UserRole.admin or _owns_fulfillment(fulfillment, user):
        return fulfillment
    raise HTTPException(status_code=404, detail="Fulfillment not found")


def _require_seller(user: User = Depends(get_current_active_user)) -> User:
    if user.role not in (UserRole.seller, UserRole.admin):
        raise HTTPException(status_code=403, detail="Seller account required")
    return user


def _http_error(exc: fs.FulfillmentError) -> HTTPException:
    """Map a domain error onto an HTTP status.

    Everything this service raises on purpose means "well-formed, but not
    allowed right now" -- the order already has a fulfillment, the job is not
    dispatched yet, this attempt is already settled. That is a 409 Conflict.

    400 is reserved for a malformed request, which Pydantic already rejects with
    422 before a handler runs. Splitting the two means a client can tell "fix
    your payload" (422) from "the world moved, re-read and retry" (409) without
    parsing the message.
    """
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# ── merchant: read ────────────────────────────────────────────────────────────


@router.get("", response_model=FulfillmentListResponse, summary="List fulfillments")
def list_fulfillments(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> FulfillmentListResponse:
    """Fulfillments visible to the caller.

    A seller sees only their own shop's orders. An admin sees everything. There
    is no way to request another merchant's data through this endpoint.
    """
    query = db.query(Fulfillment)
    if user.role != UserRole.admin:
        query = query.join(Order, Fulfillment.order_id == Order.id).join(
            Order.shop
        ).filter(Order.shop.has(seller_id=user.id))
    if status_filter:
        # status is derived in Python, so it cannot be filtered in SQL. Page
        # through the caller's own rows and filter here; the volume per seller
        # is small enough that this is cheaper than mirroring the state machine
        # into SQL and letting the two drift apart.
        rows = [f for f in query.order_by(Fulfillment.created_at.desc()).all()
                if f.status.value == status_filter]
        total = len(rows)
        start = (page - 1) * page_size
        items = rows[start:start + page_size]
    else:
        total = query.count()
        items = (
            query.order_by(Fulfillment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
    return FulfillmentListResponse(
        items=[FulfillmentRead.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{fulfillment_id}", response_model=FulfillmentDetail, summary="Fulfillment detail with history")
def get_fulfillment(fulfillment: Fulfillment = Depends(_merchant_fulfillment)) -> FulfillmentDetail:
    return FulfillmentDetail.model_validate(fulfillment)


# ── merchant: create and advance ──────────────────────────────────────────────


@router.post(
    "",
    response_model=FulfillmentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Request fulfillment for an order",
)
def create_fulfillment(
    payload: FulfillmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_require_seller),
) -> FulfillmentDetail:
    order = db.get(Order, payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.role != UserRole.admin:
        if order.shop is None or str(order.shop.seller_id) != str(user.id):
            raise HTTPException(status_code=404, detail="Order not found")

    try:
        fulfillment = fs.create_fulfillment(
            db,
            order.id,
            mode=payload.mode,
            merchant_subsidy=payload.merchant_subsidy,
            ekshop_subsidy=payload.ekshop_subsidy,
            self_rider_name=payload.self_rider_name,
            self_rider_phone=payload.self_rider_phone,
            quoted_fee=payload.quoted_fee,
        )
    except fs.FulfillmentError as e:
        raise _http_error(e)

    if payload.quoted_fee is not None:
        fulfillment.confirmed_at = fulfillment.quoted_at
        db.commit()
    return FulfillmentDetail.model_validate(_load_fulfillment(db, fulfillment.id))


@router.post(
    "/{fulfillment_id}/dispatch",
    response_model=DeliveryJobDetail,
    summary="Ask for the current job to be dispatched",
)
def request_dispatch(
    fulfillment: Fulfillment = Depends(_merchant_fulfillment),
    db: Session = Depends(get_db),
) -> DeliveryJobDetail:
    job = fulfillment.current_job
    if job is None:
        raise HTTPException(status_code=409, detail="Fulfillment has no delivery job")
    try:
        fs.transition_job(
            db,
            job,
            DeliveryJobStatus.dispatch_requested,
            event_type="DISPATCH_REQUESTED",
            actor_user_id=fulfillment.order.shop.seller_id,
            actor_role="merchant",
        )
        db.commit()
    except fs.FulfillmentError as e:
        db.rollback()
        raise _http_error(e)
    return DeliveryJobDetail.model_validate(job)


@router.post(
    "/{fulfillment_id}/offers",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Offer the current job to a rider",
)
def create_offer(
    payload: AssignmentCreate,
    fulfillment: Fulfillment = Depends(_merchant_fulfillment),
    db: Session = Depends(get_db),
) -> AssignmentRead:
    job = fulfillment.current_job
    if job is None:
        raise HTTPException(status_code=409, detail="Fulfillment has no delivery job")
    agent = db.get(DeliveryAgent, payload.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Rider not found")
    try:
        # Expire anything already past its window first, so the wave counter and
        # the offer list reflect reality.
        fs.expire_stale_assignments(db, job)
        assignment = fs.create_assignment(
            db,
            job,
            agent.id,
            wave=payload.wave,
            payout_estimate=payload.payout_estimate,
            distance_km=payload.distance_km,
            ttl_seconds=payload.ttl_seconds,
        )
        db.commit()
        db.refresh(assignment)
    except fs.FulfillmentError as e:
        db.rollback()
        raise _http_error(e)
    return AssignmentRead.model_validate(assignment)


@router.post(
    "/{fulfillment_id}/retry",
    response_model=DeliveryJobDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Open a retry attempt after a failed delivery",
)
def open_retry(
    payload: ReasonRequest,
    fulfillment: Fulfillment = Depends(_merchant_fulfillment),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> DeliveryJobDetail:
    try:
        job = fs.open_retry_job(
            db, fulfillment, actor_user_id=user.id, reason=payload.reason
        )
    except fs.FulfillmentError as e:
        db.rollback()
        raise _http_error(e)
    return DeliveryJobDetail.model_validate(job)


@router.post(
    "/{fulfillment_id}/return",
    response_model=DeliveryJobDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Open a return leg back to the merchant",
)
def open_return(
    payload: ReasonRequest,
    fulfillment: Fulfillment = Depends(_merchant_fulfillment),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> DeliveryJobDetail:
    try:
        job = fs.open_return_job(
            db, fulfillment, actor_user_id=user.id, reason=payload.reason
        )
    except fs.FulfillmentError as e:
        db.rollback()
        raise _http_error(e)
    return DeliveryJobDetail.model_validate(job)


@router.post(
    "/{fulfillment_id}/close",
    response_model=FulfillmentRead,
    summary="Close a fulfillment",
)
def close(
    payload: ReasonRequest,
    fulfillment: Fulfillment = Depends(_merchant_fulfillment),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> FulfillmentRead:
    try:
        fs.close_fulfillment(db, fulfillment, reason=payload.reason, actor_user_id=user.id)
    except fs.FulfillmentError as e:
        db.rollback()
        raise _http_error(e)
    return FulfillmentRead.model_validate(fulfillment)


# ── money ─────────────────────────────────────────────────────────────────────


@router.post(
    "/{fulfillment_id}/settlement",
    response_model=FulfillmentSettlementRead,
    summary="Record money for the current attempt",
)
def record_settlement(
    payload: JobSettlementCreate,
    fulfillment: Fulfillment = Depends(_merchant_fulfillment),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> FulfillmentSettlementRead:
    job = fulfillment.current_job
    if job is None:
        raise HTTPException(status_code=409, detail="Fulfillment has no delivery job")
    try:
        fs.record_job_settlement(db, job, actor_user_id=user.id, **payload.model_dump())
    except fs.FulfillmentError as e:
        db.rollback()
        raise _http_error(e)
    return FulfillmentSettlementRead.model_validate(
        fs.settle_fulfillment(db, fulfillment, actor_user_id=user.id)
    )


@router.get(
    "/{fulfillment_id}/settlement",
    response_model=Optional[FulfillmentSettlementRead],
    summary="Settlement roll-up for this fulfillment",
)
def get_settlement(
    fulfillment: Fulfillment = Depends(_merchant_fulfillment),
) -> Optional[FulfillmentSettlementRead]:
    if fulfillment.settlement is None:
        return None
    return FulfillmentSettlementRead.model_validate(fulfillment.settlement)


# ── rider ─────────────────────────────────────────────────────────────────────


@router.get(
    "/jobs/{job_id}",
    response_model=DeliveryJobDetail,
    summary="A job assigned to the calling rider",
)
def get_my_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
) -> DeliveryJobDetail:
    job = (
        db.query(DeliveryJob)
        .options(
            selectinload(DeliveryJob.events),
            selectinload(DeliveryJob.assignments),
        )
        .filter(DeliveryJob.id == job_id)
        .first()
    )
    if not job or job.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Job not found")
    return DeliveryJobDetail.model_validate(job)


@router.post(
    "/jobs/{job_id}/respond",
    response_model=AssignmentRead,
    summary="Accept or decline an offer",
)
def respond_to_offer(
    job_id: uuid.UUID,
    payload: AssignmentRespond,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
) -> AssignmentRead:
    assignment = (
        db.query(DeliveryAssignment)
        .filter(
            DeliveryAssignment.job_id == job_id,
            DeliveryAssignment.agent_id == agent.id,
        )
        .order_by(DeliveryAssignment.wave.desc())
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="No offer for this rider")
    try:
        updated = fs.respond_to_assignment(
            db, assignment, payload.status, decline_reason=payload.decline_reason
        )
        job = assignment.job
        if payload.status == AssignmentStatus.accepted and job is not None:
            fs.transition_job(
                db,
                job,
                DeliveryJobStatus.accepted,
                event_type="RIDER_ACCEPTED",
                actor_agent_id=agent.id,
                actor_role="agent",
            )
        db.commit()
        db.refresh(updated)
    except fs.FulfillmentError as e:
        db.rollback()
        raise _http_error(e)
    return AssignmentRead.model_validate(updated)


@router.post(
    "/jobs/{job_id}/transition",
    response_model=DeliveryJobDetail,
    summary="Advance a job the calling rider is working",
)
def transition(
    job_id: uuid.UUID,
    payload: JobTransitionRequest,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
) -> DeliveryJobDetail:
    job = db.get(DeliveryJob, job_id)
    if not job or job.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == DeliveryJobStatus.offered and payload.status != DeliveryJobStatus.accepted:
        raise HTTPException(
            status_code=409,
            detail="Use /respond to accept an offer before moving the job",
        )
    try:
        fs.transition_job(
            db,
            job,
            payload.status,
            event_type=payload.event_type,
            actor_agent_id=agent.id,
            actor_role="agent",
            notes=payload.notes,
            validate_otp=payload.validate_otp,
            otp=payload.otp,
        )
        db.commit()
        db.refresh(job)
    except fs.FulfillmentError as e:
        db.rollback()
        raise _http_error(e)
    return DeliveryJobDetail.model_validate(job)


# ── delivery code ─────────────────────────────────────────────────────────────


@router.post(
    "/jobs/{job_id}/otp",
    response_model=IssueOtpResponse,
    summary="Issue a delivery code for a job",
)
def issue_otp(
    job_id: uuid.UUID,
    payload: IssueOtpRequest,
    db: Session = Depends(get_db),
    agent: DeliveryAgent = Depends(get_current_agent),
) -> IssueOtpResponse:
    raise HTTPException(
        status_code=501,
        detail=(
            "A delivery code is issued by the merchant or ops and delivered to "
            "the customer out of band. Riders must never be able to read it: the "
            "code exists to prove the goods reached the customer, so a rider who "
            "can read it can mark a delivery complete without the customer."
        ),
    )


@router.post(
    "/{fulfillment_id}/otp",
    response_model=IssueOtpResponse,
    summary="Issue a delivery code for the current attempt",
)
def issue_otp_for_fulfillment(
    payload: IssueOtpRequest,
    fulfillment: Fulfillment = Depends(_merchant_fulfillment),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> IssueOtpResponse:
    """Mint a delivery code and return the plaintext exactly once.

    Only the hash is stored, so this response is the one and only time the code
    is readable. The channel used to reach the customer is still an open team
    decision (questionnaire Q11) -- until an SMS or WhatsApp integration exists,
    the caller is responsible for passing the code to the customer.
    """
    job = fulfillment.current_job
    if job is None:
        raise HTTPException(status_code=409, detail="Fulfillment has no delivery job")
    try:
        otp = fs.issue_otp(
            db, job, actor_user_id=user.id, ttl_minutes=payload.ttl_minutes
        )
        db.commit()
    except fs.FulfillmentError as e:
        db.rollback()
        raise _http_error(e)
    return IssueOtpResponse(otp=otp, expires_at=job.otp_expires_at)


# ── ops ───────────────────────────────────────────────────────────────────────


@router.post(
    "/jobs/{job_id}/override",
    response_model=DeliveryJobDetail,
    summary="Ops override, always with a logged reason",
)
def override(
    job_id: uuid.UUID,
    payload: OverrideRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> DeliveryJobDetail:
    job = db.get(DeliveryJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        fs.override_job(
            db,
            job,
            reason=payload.reason,
            actor_user_id=user.id,
            target=payload.status,
            notes=payload.notes,
        )
        db.commit()
        db.refresh(job)
    except fs.FulfillmentError as e:
        db.rollback()
        raise _http_error(e)
    return DeliveryJobDetail.model_validate(job)
