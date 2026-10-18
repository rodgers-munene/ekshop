"""Admin sessions get one absolute window and are never silently renewed.

The dashboard is the surface that can move money, so an admin gets
ADMIN_SESSION_MINUTES from login and then signs in again. These tests pin the
two halves of that promise: the token issued to an admin dies with the session,
and /auth/refresh refuses to extend one past its window -- while buyer and
seller sessions keep the renew-for-as-long-as-the-refresh-token-lasts behaviour
they rely on.
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import decode_access_token
from app.models.user import RefreshToken, UserRole
from app.routers.auth import refresh
from app.services.sessions import SessionExpired, access_token_ttl

NOW = datetime.now(timezone.utc)


class TestAccessTokenTtl:
    def test_buyer_tokens_keep_the_short_ttl(self):
        # A buyer logged in a month ago still gets a 15 minute token: their
        # session is kept alive by rotation, not by long-lived tokens.
        assert access_token_ttl("buyer", NOW - timedelta(days=30), NOW) == timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    def test_admin_login_token_lives_the_whole_session(self):
        assert access_token_ttl("admin", NOW, NOW) == timedelta(
            minutes=settings.ADMIN_SESSION_MINUTES
        )

    def test_admin_refresh_never_reaches_past_the_window(self):
        start = NOW - timedelta(minutes=settings.ADMIN_SESSION_MINUTES - 10)
        assert access_token_ttl("admin", start, NOW) == timedelta(minutes=10)

    def test_admin_session_is_over_at_the_cap(self):
        start = NOW - timedelta(minutes=settings.ADMIN_SESSION_MINUTES)
        with pytest.raises(SessionExpired):
            access_token_ttl("admin", start, NOW)

    def test_naive_session_start_is_read_as_utc(self):
        # Postgres hands back aware datetimes, but a row read through a driver
        # that does not must not crash the comparison.
        naive = (NOW - timedelta(minutes=5)).replace(tzinfo=None)
        assert access_token_ttl("admin", naive, NOW) == timedelta(
            minutes=settings.ADMIN_SESSION_MINUTES - 5
        )


def _db(stored, user):
    db = MagicMock()

    def query(model, *args):
        result = MagicMock()
        result.filter.return_value = result
        result.first.return_value = stored if model is RefreshToken else user
        return result

    db.query.side_effect = query
    return db


def _stored(session_start):
    return SimpleNamespace(
        user_id=uuid.uuid4(),
        token_hash="hash",
        revoked_at=None,
        created_at=session_start,
        session_started_at=session_start,
        expires_at=NOW + timedelta(days=7),
    )


def _user(role):
    return SimpleNamespace(id=uuid.uuid4(), role=role)


def _exp(token):
    return datetime.fromtimestamp(decode_access_token(token)["exp"], tz=timezone.utc)


class TestRefreshEndpoint:
    def test_admin_refresh_inside_the_window_is_shortened_to_the_cap(self):
        start = NOW - timedelta(minutes=50)
        stored = _stored(start)
        db = _db(stored, _user(UserRole.admin))

        result = refresh("raw-token", db)

        assert _exp(result.access_token) <= start + timedelta(
            minutes=settings.ADMIN_SESSION_MINUTES
        )
        assert _exp(result.access_token) > NOW
        # Rotation carries the original login forward, otherwise the cap would
        # reset on every refresh and never bite.
        assert db.add.call_args.args[0].session_started_at == start

    def test_admin_refresh_after_the_window_is_refused(self):
        stored = _stored(NOW - timedelta(minutes=settings.ADMIN_SESSION_MINUTES + 1))
        db = _db(stored, _user(UserRole.admin))

        with pytest.raises(HTTPException) as excinfo:
            refresh("raw-token", db)

        assert excinfo.value.status_code == 401
        # The dead token is revoked as well, so a replay cannot be retried.
        assert stored.revoked_at is not None
        db.add.assert_not_called()
        db.commit.assert_called()

    def test_buyer_refresh_is_not_capped(self):
        stored = _stored(NOW - timedelta(days=30))
        db = _db(stored, _user(UserRole.buyer))

        result = refresh("raw-token", db)

        assert _exp(result.access_token) > NOW + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES - 1
        )
        assert db.add.call_args.args[0].session_started_at == stored.session_started_at

    def test_refresh_for_a_deleted_user_issues_nothing(self):
        stored = _stored(NOW - timedelta(minutes=1))
        db = _db(stored, None)

        with pytest.raises(HTTPException) as excinfo:
            refresh("raw-token", db)

        assert excinfo.value.status_code == 401
        assert stored.revoked_at is not None
        db.add.assert_not_called()
