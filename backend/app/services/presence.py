"""Live presence, in memory.

`active_sessions` on the dashboard was always 0. It was counting rows in
`UserEvent` -- a behavioural analytics table written only by the recommender for
purchases and product views. Browsing the site writes nothing, so the number could
only ever be zero, and it was zero even with the site open in a tab.

Presence is the wrong thing to store. It is worthless a minute after the user
leaves, and writing every page view to the database to then throw it away costs
writes and buys nothing. So this is an in-process registry with a TTL: the client
sends a heartbeat, and anything that has not been heard from in a minute is
simply gone.

What that means for correctness, stated plainly:

* **Per-instance.** Each API process keeps its own registry. Running three workers
  behind a load balancer reports roughly a third of the true presence, because a
  user's heartbeats land on one worker and the admin reads another. This is fine
  for the single-process deployment it is built for and wrong for a scaled one.
  The honest fix at that point is Redis, which is a deliberate future change, not
  an oversight.
* **Lost on restart.** Everyone appears to leave at once. Harmless.
* **Heartbeat-driven, not inferred.** A user with the tab open but the network
  down will age out. That is the correct direction to fail: we would rather
  under-report than show a phantom.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

# A user is considered present until this long after their last heartbeat.
# One minute: a client beats every 20s, so two missed beats retire them.
PRESENCE_TTL_SECONDS = 60


@dataclass
class Presence:
    """One user's current presence, keyed by user id."""

    user_id: str
    role: str
    display_name: str
    session_id: str
    path: str
    first_seen: float
    last_seen: float = field(default=0.0)

    def is_stale(self, now: float, ttl: int = PRESENCE_TTL_SECONDS) -> bool:
        return (now - self.last_seen) > ttl


@dataclass(frozen=True)
class PresenceSnapshot:
    """A point-in-time view, returned to the admin dashboard."""

    active_users: int
    active_sessions: int
    active_tabs: int
    by_role: dict[str, int]
    # Distinct pages currently open, most-used first.
    top_paths: list[tuple[str, int]]
    users: list[dict]


class PresenceRegistry:
    """Thread-safe in-memory presence with a TTL.

    A lock rather than an asyncio structure because the FastAPI endpoints here are
    synchronous, and a lock is the honest amount of machinery for that.
    """

    def __init__(self, ttl_seconds: int = PRESENCE_TTL_SECONDS) -> None:
        # Keyed by user *and* session, not by user alone. Keying on the user would
        # mean a person on a phone and a laptop could only ever occupy one entry,
        # so "active sessions" would silently equal "active users" and the tab
        # count would be meaningless. `active_users` de-duplicates on read instead.
        self._entries: dict[str, Presence] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    @staticmethod
    def _key(user_id: uuid.UUID | str, session_id: str) -> str:
        return f"{user_id}:{session_id}"

    def _now(self) -> float:
        return time.monotonic()

    def beat(
        self,
        *,
        user_id: uuid.UUID | str,
        role: str,
        display_name: str,
        session_id: str,
        path: str,
    ) -> Presence:
        """Record a heartbeat. A repeat beat from the same user+session refreshes it."""
        key = self._key(user_id, session_id)
        now = self._now()
        with self._lock:
            self._evict_locked(now)
            existing = self._entries.get(key)
            if existing is None:
                existing = Presence(
                    user_id=str(user_id),
                    role=role,
                    display_name=display_name,
                    session_id=session_id,
                    path=path,
                    first_seen=now,
                )
                self._entries[key] = existing
            else:
                # Same session moving to another page. Last writer wins, which is
                # what the admin expects to see.
                existing.role = role
                existing.display_name = display_name
                existing.path = path
            existing.last_seen = now
            return existing

    def _evict_locked(self, now: float) -> int:
        stale = [k for k, v in self._entries.items() if v.is_stale(now, self._ttl)]
        for key in stale:
            del self._entries[key]
        return len(stale)

    def evict(self) -> int:
        with self._lock:
            return self._evict_locked(self._now())

    def snapshot(self) -> PresenceSnapshot:
        """Current presence, with expired entries dropped first."""
        now = self._now()
        with self._lock:
            self._evict_locked(now)
            live = list(self._entries.values())

        by_role: dict[str, int] = {}
        path_counts: dict[str, int] = {}
        for entry in live:
            by_role[entry.role] = by_role.get(entry.role, 0) + 1
            path_counts[entry.path] = path_counts.get(entry.path, 0) + 1

        users = [
            {
                "user_id": entry.user_id,
                "role": entry.role,
                "display_name": entry.display_name,
                "session_id": entry.session_id,
                "path": entry.path,
                "seconds_active": int(now - entry.first_seen),
            }
            for entry in sorted(live, key=lambda e: e.last_seen, reverse=True)
        ]

        top_paths = sorted(path_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]

        return PresenceSnapshot(
            active_users=len({e.user_id for e in live}),
            # A user with two devices open is two sessions, which is the
            # distinction the old UserEvent count could never make.
            active_sessions=len(live),
            # One entry per user+session; each holds the page that session is on.
            active_tabs=len({(e.user_id, e.session_id) for e in live}),
            by_role=by_role,
            top_paths=top_paths,
            users=users,
        )

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


registry = PresenceRegistry()


def beat(
    *,
    user_id: uuid.UUID | str,
    role: str,
    display_name: str,
    session_id: str,
    path: str,
) -> Presence:
    return registry.beat(
        user_id=user_id, role=role, display_name=display_name,
        session_id=session_id, path=path,
    )


def snapshot() -> PresenceSnapshot:
    return registry.snapshot()


def clear() -> None:
    """Test hook."""
    registry.clear()
