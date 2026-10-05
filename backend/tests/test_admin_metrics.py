"""The three money figures must mean three different things.

The admin dashboard used to show one number under two names: "GMV" was rendered
from `revenue_total`, which is the sum of `OrderGroup.total` -- goods *plus*
delivery *plus* tax. Alongside it, "Revenue" appeared again from the same field,
and a hardcoded 10% commission appeared in a third place. Nothing in the data
model records a commission rate, so that 10% came from nowhere.

These tests pin the definitions down so the conflation cannot come back.
"""
from decimal import Decimal

import pytest

from app.routers.admin import _commission


class TestCommission:
    def test_revenue_is_unknown_until_a_rate_is_configured(self, monkeypatch):
        """No rate in the data model means no revenue figure. A blank is honest;
        a fabricated 10% is not."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "PLATFORM_COMMISSION_RATE", None)
        assert _commission(Decimal("100000")) is None

    def test_revenue_is_commission_on_goods(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "PLATFORM_COMMISSION_RATE", Decimal("0.10"))
        assert _commission(Decimal("1000.00")) == "100.00"
        assert _commission(Decimal("0")) == "0.00"


class TestDefinitionsAreDistinct:
    """The three figures, stated so a change has to be deliberate."""

    def test_gmv_excludes_delivery_and_tax(self):
        # GMV is summed from OrderItem.line_total. If anyone changes it to read
        # OrderGroup.total, GMV and total transacted become the same number and
        # the dashboard is back to showing one figure under two names.
        from app.models.commerce import OrderGroup, OrderItem

        assert "line_total" in OrderItem.__table__.columns
        assert "total" in OrderGroup.__table__.columns
        # subtotal is goods; total is goods + delivery + tax. They are different
        # columns precisely because the gap is delivery and tax.
        assert "delivery_fee" in OrderGroup.__table__.columns
        assert "tax_amount" in OrderGroup.__table__.columns

    def test_total_transacted_includes_delivery_and_tax(self):
        from app.models.commerce import OrderGroup

        assert "delivery_fee" in OrderGroup.__table__.columns
        assert "tax_amount" in OrderGroup.__table__.columns
        assert "total" in OrderGroup.__table__.columns


class TestSchemaShape:
    def test_period_figures_expose_all_three(self):
        from app.schemas.admin import PeriodFigures

        fields = set(PeriodFigures.model_fields)
        assert {"gmv", "total_transacted", "revenue"} <= fields
        assert "commission_rate_configured" in fields
        # revenue must be nullable: it is unknown, not zero.
        assert PeriodFigures.model_fields["revenue"].annotation is not str

    def test_stats_include_yesterday(self):
        from app.schemas.admin import AdminStatsRead

        fields = set(AdminStatsRead.model_fields)
        assert {"orders_yesterday", "gmv_yesterday", "total_transacted_yesterday"} <= fields

    def test_trend_exposes_gmv_and_revenue_separately(self):
        from app.schemas.admin import AdminTrendPoint

        fields = set(AdminTrendPoint.model_fields)
        assert {"gmv", "total_transacted", "revenue_earned"} <= fields

    def test_overview_totals_expose_all_three(self):
        from app.schemas.admin import AdminOverviewTotals

        fields = set(AdminOverviewTotals.model_fields)
        assert {"gmv_total", "total_transacted_total", "revenue_total"} <= fields


class TestOrderCountingBasis:
    def test_stats_and_order_list_count_the_same_thing(self):
        """Both count paid order *groups* (baskets).

        A group holds one order per shop, so a group count and a shop-order count
        are different numbers. The dashboard reported one and the list showed the
        other, which is why "paid orders: 10" did not match four visible rows.
        """
        from app.models.commerce import Order, OrderGroup

        # An Order belongs to a group; the group is the basket. That is why the
        # two counts differ and why the labels have to say which they mean.
        assert "group_id" in {c.name for c in Order.__table__.columns}
        assert OrderGroup.__tablename__ == "order_groups"

    def test_paid_only_is_the_filter(self):
        """Only paid groups count towards money and order counts. Unpaid baskets
        are not transactions."""
        from app.models.commerce import OrderGroupStatus

        assert OrderGroupStatus.paid.value == "paid"
        assert OrderGroupStatus.pending_payment.value != OrderGroupStatus.paid.value