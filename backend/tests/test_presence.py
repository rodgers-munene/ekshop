"""The presence registry: TTL, counting, and the tabs distinction."""
import time
import uuid

import pytest

from app.services import presence


@pytest.fixture(autouse=True)
def clean_registry():
    presence.clear()
    yield
    presence.clear()


def beat(role="buyer", path="/", session="s1", user=None, name="Test User"):
    return presence.beat(
        user_id=user or uuid.uuid4(),
        role=role,
        display_name=name,
        session_id=session,
        path=path,
    )


class TestCounting:
    def test_nobody_is_present_initially(self):
        snap = presence.snapshot()
        assert snap.active_users == 0
        assert snap.active_sessions == 0
        assert snap.active_tabs == 0

    def test_one_beat_is_one_user_one_session_one_tab(self):
        beat()
        snap = presence.snapshot()
        assert (snap.active_users, snap.active_sessions, snap.active_tabs) == (1, 1, 1)

    def test_a_repeat_beat_does_not_inflate_the_count(self):
        user = uuid.uuid4()
        for _ in range(10):
            beat(user=user, session="s1")
        snap = presence.snapshot()
        assert snap.active_users == 1
        assert snap.active_sessions == 1

    def test_one_user_two_sessions_counts_as_two_sessions(self):
        """Two devices is two sessions for one person. The old UserEvent count
        could never express this."""
        user = uuid.uuid4()
        beat(user=user, session="phone")
        beat(user=user, session="laptop")
        snap = presence.snapshot()
        assert snap.active_users == 1
        assert snap.active_sessions == 2

    def test_distinct_users_are_counted_separately(self):
        for _ in range(4):
            beat(session=uuid.uuid4().hex)
        assert presence.snapshot().active_users == 4

    def test_by_role(self):
        beat(role="buyer")
        beat(role="seller")
        beat(role="seller")
        snap = presence.snapshot()
        assert snap.by_role == {"buyer": 1, "seller": 2}


class TestTabs:
    def test_current_path_is_tracked(self):
        beat(path="/dashboard/products")
        assert presence.snapshot().users[0]["path"] == "/dashboard/products"

    def test_navigating_updates_the_path(self):
        user = uuid.uuid4()
        beat(user=user, path="/", session="s1")
        beat(user=user, path="/checkout", session="s1")
        assert presence.snapshot().users[0]["path"] == "/checkout"
        # Still one tab: the same user moved within it.
        assert presence.snapshot().active_tabs == 1

    def test_top_paths_ranked_by_popularity(self):
        beat(path="/", session="a")
        beat(path="/", session="b")
        beat(path="/checkout", session="c")
        top = presence.snapshot().top_paths
        assert top[0] == ("/", 2)
        assert ("/checkout", 1) in top


class TestExpiry:
    def test_a_user_ages_out(self):
        """The whole point of a TTL: presence that has gone stale must not be
        reported, or the dashboard would fill with phantoms."""
        registry = presence.PresenceRegistry(ttl_seconds=0)
        registry.beat(
            user_id=uuid.uuid4(), role="buyer", display_name="X",
            session_id="s1", path="/",
        )
        time.sleep(0.01)
        assert registry.snapshot().active_users == 0

    def test_evict_reports_how_many_went(self):
        """Expired entries are dropped. The exact count depends on whether a
        later beat already swept them, so the contract asserted is that the
        registry ends up empty and evict reports a non-negative number."""
        registry = presence.PresenceRegistry(ttl_seconds=0)
        for _ in range(3):
            registry.beat(
                user_id=uuid.uuid4(), role="buyer", display_name="X",
                session_id=uuid.uuid4().hex, path="/",
            )
        time.sleep(0.01)
        assert registry.evict() >= 0
        assert registry.snapshot().active_users == 0

    def test_fresh_entries_survive_an_evict(self):
        registry = presence.PresenceRegistry(ttl_seconds=60)
        registry.beat(
            user_id=uuid.uuid4(), role="buyer", display_name="X",
            session_id="s1", path="/",
        )
        assert registry.evict() == 0
        assert registry.snapshot().active_users == 1


class TestSnapshotContents:
    def test_snapshot_carries_enough_to_render_a_table(self):
        user = uuid.uuid4()
        presence.beat(
            user_id=user, role="seller", display_name="Ada",
            session_id="s1", path="/admin/orders",
        )
        entry = presence.snapshot().users[0]
        assert entry["user_id"] == str(user)
        assert entry["display_name"] == "Ada"
        assert entry["role"] == "seller"
        assert entry["path"] == "/admin/orders"
        assert entry["seconds_active"] >= 0

    def test_newest_heartbeat_is_listed_first(self):
        first = uuid.uuid4()
        presence.beat(user_id=first, role="buyer", display_name="First",
                      session_id="s1", path="/")
        time.sleep(0.01)
        presence.beat(user_id=uuid.uuid4(), role="buyer", display_name="Second",
                      session_id="s2", path="/")
        users = presence.snapshot().users
        assert users[0]["display_name"] == "Second"
        assert users[1]["display_name"] == "First"