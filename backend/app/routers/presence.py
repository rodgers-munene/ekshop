"""Presence heartbeats and the admin view of who is online.

The heartbeat is open to any authenticated role on purpose: knowing a buyer is
browsing is the point, and restricting it to admins would make the metric useless.
It records nothing but a user id, a role, a session id and the current path, and
holds them in memory for a minute.
"""


from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_active_user, require_admin
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.admin import RealTimeMetrics
from app.services import dashboard_metrics
from app.services import presence as presence_service

router = APIRouter(tags=["presence"])


class HeartbeatRequest(BaseModel):
    """A periodic "I am still here, on this page" ping.

    `path` is sent rather than read from a header so the admin sees which tab a
    user is actually looking at, which is the useful part.
    """

    session_id: str = Field(min_length=8, max_length=64)
    path: str = Field(default="/", max_length=200)


@router.post("/presence/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
def heartbeat(
    payload: HeartbeatRequest,
    user: User = Depends(get_current_active_user),
) -> None:
    """Record presence. Deliberately returns nothing: the client sends this every
    twenty seconds and should not be parsing a body each time."""
    display_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
    presence_service.beat(
        user_id=user.id,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        display_name=display_name,
        session_id=payload.session_id,
        path=payload.path,
    )


@router.get("/admin/metrics/presence")
def admin_presence(_: User = Depends(require_admin)) -> dict:
    """Who is online right now, and what they are looking at."""
    snap = presence_service.snapshot()
    return {
        "active_users": snap.active_users,
        "active_sessions": snap.active_sessions,
        "active_tabs": snap.active_tabs,
        "by_role": snap.by_role,
        "top_paths": [{"path": p, "count": c} for p, c in snap.top_paths],
        "users": snap.users,
        "ttl_seconds": presence_service.PRESENCE_TTL_SECONDS,
        # Stated on the response so a reader is not misled into thinking this is
        # a fleet-wide total when several API processes are running.
        "scope": "this_api_process",
    }


@router.get("/admin/metrics/real-time", response_model=RealTimeMetrics)
def get_real_time_metrics(
    minutes: int = Query(15, ge=1, le=60),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> RealTimeMetrics:
    """Real-time panel.

    `active_sessions` and `active_users` now come from the in-memory presence
    registry, so they reflect people actually on the site right now. The previous
    implementation counted `UserEvent` rows -- a behavioural analytics table only
    written for purchases and product views -- which is why it read zero with the
    site open in a tab.

    `recent_purchases` and `active_carts` still come from the database, because
    they are historical facts rather than live presence.
    """
    snap = presence_service.snapshot()
    figures = dashboard_metrics.get_real_time_metrics(db, minutes)
    return RealTimeMetrics(
        active_sessions=snap.active_sessions,
        active_users=snap.active_users,
        recent_purchases=figures.get("recent_purchases", 0),
        active_carts=figures.get("active_carts", 0),
    )
