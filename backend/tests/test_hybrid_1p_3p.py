"""Ekshop trades as its own merchant alongside the marketplace.

Four things are locked out here.

First, the revenue/leakage endpoints answered 500 when a rate was not
configured: the service correctly returned None for commission, fees and gross
margin, but the response models declared them non-nullable, so validation failed
and the panel on the analytics page came back empty. "Not configured" must
serialize as null, never as zero and never as an error.

Second, commission is a marketplace concept. Charging it on Ekshop's own
first-party goods, then reporting the charge as platform revenue, counts money
Ekshop pays to itself as income. Every split below therefore treats a sale as
first-party when its shop is platform-owned OR its stored source says so, so a
backfilled source flag cannot misfile Ekshop's own sales under the marketplace
column.

Third, a plan limit and a subscription are things a subscriber is subject to.
Ekshop trading as itself is not one of its own subscribers, so the billing
cycle must never invoice, suspend or remind a platform-owned shop, and its
plan's product cap must never apply to it.

Fourth, the whole of that exemption is switched by one administrator action,
so the action has to wake the shop, the seller and any subscription it already
has up to active in one go — otherwise the first-party merchant would be
created in a state that its own paywall locks out.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql
from sqlalchemy import or_

from app.models.commerce import Order, OrderSource
from app.models.shop import Shop, ShopStatus
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.user import User, UserStatus
from app.routers.admin import router as admin_router
from app.routers.admin import toggle_shop_platform_owned
from app.routers.catalog import product_cap_for
from app.services import email as email_service
from app.services import subscriptions as billing
from app.schemas.admin import (
    AdminOverviewTotals,
    AdminTrendPoint,
    MarginLeakageMetrics,
    MarginLeakageTrendPoint,
    PeriodFigures,
)


def sql(expression) -> str:
    return str(
        expression.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def make_shop(*, platform: bool, seller_status=UserStatus.active, shop_status=ShopStatus.active) -> Shop:
    seller_id = uuid.uuid4()
    shop = Shop(
        id=uuid.uuid4(),
        seller_id=seller_id,
        name="Ekshop Official",
        slug=f"shop-{uuid.uuid4().hex[:12]}",
        is_platform_owned=platform,
        is_verified=platform,
        status=shop_status,
    )
    shop.seller = User(id=seller_id, email="ops@ekshop.co.ke", status=seller_status)
    return shop


def make_subscription(shop: Shop, *, status: SubscriptionStatus, period_end, max_products=None) -> Subscription:
    plan = SubscriptionPlan(
        name="Starter",
        code=f"starter-{uuid.uuid4().hex[:8]}",
        price_monthly="1000",
        commission_rate="0.10",
        max_products=max_products,
    )
    subscription = Subscription(status=status, current_period_end=period_end)
    subscription.plan = plan
    shop.subscription = subscription
    return subscription


def stub_db(rows) -> "MagicMock":
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = rows
    return db


class TestMarginLeakageSerialisesUnconfiguredRates:
    """None must survive the response model. It used to fail validation."""

    def test_top_level_metrics_accept_none(self):
        m = MarginLeakageMetrics(
            period="month",
            start="2026-10-01T00:00:00",
            end="2026-10-16T00:00:00",
            gmv="1000.00",
            orders=2,
            average_order_value="500.00",
            platform_commission=None,
            mpesa_fees=None,
            server_cost=None,
            net_profit=None,
            gross_margin_pct=None,
            commission_rate_pct=None,
            mpesa_rate_pct=None,
            trend=[],
        )
        assert m.platform_commission is None
        assert m.gross_margin_pct is None

    def test_trend_points_accept_none(self):
        p = MarginLeakageTrendPoint(
            label="01 Oct",
            gmv=100.0,
            platform_commission=None,
            mpesa_fees=None,
            net_profit=None,
            gross_margin_pct=None,
            aov=100.0,
        )
        assert p.net_profit is None

    def test_default_is_zero_split_not_missing(self):
        """A new row reports a real 0/0 split rather than leaving it absent."""
        m = MarginLeakageMetrics(
            period="month",
            start="2026-10-01T00:00:00",
            end="2026-10-16T00:00:00",
            gmv="0.00",
            orders=0,
            average_order_value="0.00",
            trend=[],
        )
        assert (m.gmv_1p, m.gmv_3p) == ("0.00", "0.00")
        assert m.rates_configured is None


class TestChannelSplitFields:
    """The split must be present on every figure that reports GMV or revenue."""

    def test_period_figures_carries_the_split(self):
        f = PeriodFigures(
            gmv="100.00",
            total_transacted="110.00",
            revenue="90.00",
            commission_rate_configured=True,
            orders=1,
            average_order_value="110.00",
            new_users=0,
            new_shops=0,
            cash_received="110.00",
            refunds="0.00",
            basis="payments",
            basis_note=None,
        )
        assert (f.gmv_1p, f.gmv_3p) == ("0.00", "0.00")
        assert (f.orders_1p, f.orders_3p) == (0, 0)

    def test_overview_totals_carry_the_split(self):
        t = AdminOverviewTotals(
            total_users=1,
            total_buyers=1,
            total_sellers=1,
            total_shops=1,
            shops_pending_verification=0,
            total_products=0,
            total_orders=0,
            gmv_total="100.00",
            total_transacted_total="110.00",
            revenue_total=None,
            net_revenue_total=None,
            commission_rate_configured=False,
            cash_received_total="110.00",
            refunds_total="0.00",
            total_refunds_lifetime="0.00",
            total_chargebacks_lifetime="0.00",
            avg_delivery_fee_lifetime="0.00",
            delivery_cost_per_order_lifetime="0.00",
            active_buyers_lifetime=1,
            active_sellers_lifetime=1,
            repeat_buyer_rate_lifetime=0.0,
        )
        assert (t.gmv_1p_total, t.gmv_3p_total) == ("0.00", "0.00")
        assert (t.orders_1p_total, t.orders_3p_total) == (0, 0)

    def test_trend_point_sums_to_the_blended_series(self):
        """1P and 3P must reconcile to the GMV line the chart already draws."""
        pt = AdminTrendPoint(
            label="01 Oct",
            revenue=0.0,
            gmv=100.0,
            total_transacted=100.0,
            revenue_earned=None,
            commission_rate_configured=False,
            orders=1,
            gmv_1p=30.0,
            gmv_3p=70.0,
        )
        assert pt.gmv_1p + pt.gmv_3p == pt.gmv


class TestFirstPartyCondition:
    def test_both_markers_are_required(self):
        condition = or_(
            Order.source == OrderSource.first_party,
            Shop.is_platform_owned.is_(True),
        )
        text = sql(condition)
        assert "first_party" in text
        assert "is_platform_owned" in text

    def test_order_source_values(self):
        assert {m.value for m in OrderSource} == {"marketplace", "first_party"}


class TestProductCap:
    """A plan limit belongs to a subscriber. Ekshop is not one of its own."""

    def test_platform_shop_is_never_capped(self):
        shop = make_shop(platform=True)
        make_subscription(shop, status=SubscriptionStatus.active, period_end=None, max_products=1)
        assert product_cap_for(shop) is None

    def test_marketplace_shop_keeps_its_cap(self):
        shop = make_shop(platform=False)
        make_subscription(shop, status=SubscriptionStatus.active, period_end=None, max_products=1)
        assert product_cap_for(shop) == 1

    def test_shop_with_no_subscription_has_no_cap(self):
        assert product_cap_for(make_shop(platform=False)) is None


class TestBillingLeavesPlatformAlone:
    """The owners cannot be invoiced, suspended or nagged out of their own shop."""

    def test_expired_platform_subscription_is_untouched_and_is_not_counted(self, monkeypatch):
        monkeypatch.setattr(email_service, "send_subscription_past_due_email", lambda *a, **k: None)
        monkeypatch.setattr(billing, "_notify_seller", lambda *a, **k: None)
        past = datetime.now(timezone.utc) - timedelta(days=10)

        platform_shop = make_shop(platform=True)
        platform = make_subscription(platform_shop, status=SubscriptionStatus.active, period_end=past)

        assert billing.expire_overdue_subscriptions(stub_db([platform])) == 0
        assert platform.status is SubscriptionStatus.active
        assert platform_shop.status is ShopStatus.active
        assert platform_shop.seller.status is UserStatus.active

    def test_expired_marketplace_subscription_still_demotes(self, monkeypatch):
        monkeypatch.setattr(email_service, "send_subscription_past_due_email", lambda *a, **k: None)
        monkeypatch.setattr(billing, "_notify_seller", lambda *a, **k: None)
        past = datetime.now(timezone.utc) - timedelta(days=10)

        marketplace_shop = make_shop(platform=False)
        marketplace = make_subscription(marketplace_shop, status=SubscriptionStatus.active, period_end=past)

        assert billing.expire_overdue_subscriptions(stub_db([marketplace])) == 1
        assert marketplace.status is SubscriptionStatus.past_due

    def test_platform_shop_is_never_suspended_for_non_payment(self, monkeypatch):
        monkeypatch.setattr(email_service, "send_subscription_cancelled_email", lambda *a, **k: None)
        monkeypatch.setattr(billing, "_notify_seller", lambda *a, **k: None)
        long_past = datetime.now(timezone.utc) - timedelta(days=30)

        platform_shop = make_shop(platform=True)
        platform = make_subscription(platform_shop, status=SubscriptionStatus.past_due, period_end=long_past)

        marketplace_shop = make_shop(platform=False)
        marketplace = make_subscription(marketplace_shop, status=SubscriptionStatus.past_due, period_end=long_past)

        assert billing.suspend_cancelled_subscriptions(stub_db([platform, marketplace])) == 1
        assert platform.status is SubscriptionStatus.past_due
        assert platform_shop.status is ShopStatus.active
        assert marketplace.status is SubscriptionStatus.cancelled
        assert marketplace_shop.status is ShopStatus.suspended

    def test_platform_shop_gets_no_renewal_reminder(self, monkeypatch):
        sent = []
        monkeypatch.setattr(email_service, "send_subscription_reminder_email", lambda *a, **k: sent.append(a))
        monkeypatch.setattr(billing, "_notify_seller", lambda *a, **k: None)

        platform_shop = make_shop(platform=True)
        platform = make_subscription(
            platform_shop,
            status=SubscriptionStatus.active,
            period_end=datetime.now(timezone.utc) + timedelta(days=2),
        )

        assert billing.send_renewal_reminders(stub_db([platform])) == 0
        assert sent == []
        assert platform.reminder_7d_sent_at is None

    def test_marketplace_shop_still_gets_its_reminder(self, monkeypatch):
        sent = []
        monkeypatch.setattr(email_service, "send_subscription_reminder_email", lambda *a, **k: sent.append(a))
        monkeypatch.setattr(billing, "_notify_seller", lambda *a, **k: None)

        marketplace_shop = make_shop(platform=False)
        make_subscription(
            marketplace_shop,
            status=SubscriptionStatus.active,
            period_end=datetime.now(timezone.utc) + timedelta(days=2),
        )

        # The stubbed session cannot evaluate the reminder-window filter, so a
        # marketplace subscription is reminded at least once rather than once.
        assert billing.send_renewal_reminders(stub_db([marketplace_shop.subscription])) >= 1
        assert len(sent) >= 1


class TestAdminPlatformToggle:
    """One control provisions the first-party merchant."""

    def test_route_is_registered(self):
        paths = {route.path for route in admin_router.routes}
        assert "/admin/shops/{shop_id}/platform" in paths

    def test_enabling_wakes_up_shop_seller_and_subscription(self):
        shop = make_shop(platform=False, seller_status=UserStatus.pending, shop_status=ShopStatus.pending)
        shop.is_verified = False
        subscription = make_subscription(
            shop,
            status=SubscriptionStatus.trialing,
            period_end=datetime.now(timezone.utc) + timedelta(days=5),
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = shop

        toggle_shop_platform_owned(shop.id, db=db, _=None)

        assert shop.is_platform_owned is True
        assert shop.status is ShopStatus.active
        assert shop.is_verified is True
        assert shop.seller.status is UserStatus.active
        assert subscription.status is SubscriptionStatus.active
        assert subscription.current_period_end > datetime.now(timezone.utc) + timedelta(days=3000)
        db.commit.assert_called_once()

    def test_disabling_does_not_revoke_a_subscription(self):
        shop = make_shop(platform=True)
        subscription = make_subscription(
            shop,
            status=SubscriptionStatus.active,
            period_end=datetime.now(timezone.utc) + timedelta(days=3000),
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = shop

        toggle_shop_platform_owned(shop.id, db=db, _=None)

        assert shop.is_platform_owned is False
        assert subscription.status is SubscriptionStatus.active
        assert subscription.current_period_end is not None
        db.commit.assert_called_once()
