"""How long an authenticated session may last.

Buyer and seller sessions are renewed silently by the frontend proxy for as long
as their refresh token is valid, so a logged-in shopper is not interrupted
mid-basket. The admin dashboard is treated differently: it gets one absolute
window (``ADMIN_SESSION_MINUTES``) and then the admin signs in again. The window
is stamped on the refresh-token row at login and copied onto every successor on
rotation, so "how old is this session" stays answerable across refreshes.

Idle timeout is deliberately *not* here. The server cannot tell an idle tab from
a working one, so the frontend watches for inactivity and signs the admin out
(``frontend/components/admin/AdminSessionGuard.tsx``). This module owns the
absolute cap, which is the part a client cannot talk its way out of.
"""
from datetime import datetime, timedelta, timezone

from app.core.config import settings

ADMIN_ROLE = "admin"


class SessionExpired(Exception):
    """The absolute session window is over: a fresh login is required."""


def session_started_at_value(explicit: datetime | None, created_at: datetime) -> datetime:
    """The session start for a token row.

    Rows written before the column existed (and any row somehow missing it) fall
    back to their own creation time, which is the closest honest answer.
    """
    return explicit or created_at


def access_token_ttl(role: str, session_started_at: datetime, now: datetime) -> timedelta:
    """Lifetime of the next access token for this session.

    An admin token is issued to die exactly when the session window closes, so
    the JWT itself carries the cap and the browser needs no callback to know
    when to re-authenticate. Everyone else gets the plain short TTL.
    """
    if role != ADMIN_ROLE:
        return timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    if session_started_at.tzinfo is None:
        # A naive value can only have come from the database; the app writes UTC.
        session_started_at = session_started_at.replace(tzinfo=timezone.utc)

    remaining = (
        session_started_at + timedelta(minutes=settings.ADMIN_SESSION_MINUTES)
    ) - now
    if remaining <= timedelta(0):
        raise SessionExpired(
            f"Admin sessions last {settings.ADMIN_SESSION_MINUTES} minutes"
        )
    return remaining
