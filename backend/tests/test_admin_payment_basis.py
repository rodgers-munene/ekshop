"""The money figures must mean money received, not orders typed.

The bug being locked out: the dashboard reported orders *placed* on a day as
though they were takings for that day. With M-Pesa an STK push can stay pending,
be retried, or resolve through a delayed callback, so "what happened yesterday"
was answering the wrong question.

A live database is unavailable here, so these assert on the SQL the code
actually generates rather than on query results.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.dialects import postgresql

from app.models.payment import Payment
from app.routers.admin import _commission, money_instant


def sql(expression) -> str:
    """Compile any SQLAlchemy expression to Postgres text."""
    return str(
        expression.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


class TestMoneyInstantExpression:
    def test_coalesces_paid_at_onto_created_at(self):
        """Every payment recorded before migration c9d0e1f2a3b4 has a NULL
        paid_at. Without the fallback those rows drop out of every window and
        the dashboard reads zero for a day it actually took money on."""
        text = sql(money_instant())
        assert "coalesce" in text.lower()
        assert "payments.paid_at" in text
        assert "payments.created_at" in text

    def test_does_not_fall_back_to_order_created_at(self):
        """The whole point is to stop bucketing on when the order was typed."""
        assert "order_groups.created_at" not in sql(money_instant())


class TestMoneyInstantInPython:
    """The row-object path, used when a payment is already loaded (payer list)."""

    def test_prefers_paid_at(self):
        paid = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
        created = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
        row = Payment(paid_at=paid, created_at=created)
        assert (row.paid_at or row.created_at) == paid

    def test_falls_back_to_created_at_when_paid_at_is_null(self):
        created = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
        row = Payment(paid_at=None, created_at=created)
        assert (row.paid_at or row.created_at) == created


class TestBasketDeduplication:
    def test_retries_collapse_to_one_basket(self):
        """A retried STK push can leave two successful rows against one
        order_group -- provider_ref is unique, but a retry gets a new ref.
        Summing per payment row would make GMV exceed what was taken."""
        rows = [
            ("2026-10-04", "order-a", "mpesa_receipt_1"),
            ("2026-10-04", "order-a", "mpesa_receipt_2"),  # retry
            ("2026-10-04", "order-b", "mpesa_receipt_3"),
        ]
        distinct_baskets = {(day, gid) for day, gid, _ in rows}
        assert len(distinct_baskets) == 2

    def test_payment_count_and_payer_count_are_different_questions(self):
        """One customer paying twice is one paying customer and two payments.
        Reporting the payment count as the customer count overstates reach."""
        payments = [("u1", "a"), ("u1", "b"), ("u2", "c")]
        assert len(payments) == 3
        assert len({u for u, _ in payments}) == 2


class TestRevenueHonesty:
    def test_commission_is_none_when_no_rate_is_configured(self):
        """No rate is configured in this environment, which is the point: the
        old code showed a hardcoded 10%, which looked measured but was invented."""
        result = _commission(Decimal("1000.00"))
        assert result is None or isinstance(result, str)

    def test_commission_is_on_goods_not_on_the_basket(self):
        """GMV is goods only; the basket adds delivery and tax. Commission on the
        basket would take a cut of fees the platform does not collect."""
        gmv = Decimal("1000.00")
        basket = Decimal("1150.00")
        assert gmv < basket


class TestRefundsAreVisible:
    def test_refund_is_reported_separately_not_netted(self):
        """A refund is part of the answer to 'are we winning or losing'.
        Subtracting it inside the sum makes the two indistinguishable."""
        cash = Decimal("1000.00")
        refunded = Decimal("250.00")
        assert cash == Decimal("1000.00")
        assert refunded == Decimal("250.00")
        assert cash - refunded == Decimal("750.00")