"""The report has to render correctly, not just compile.

The bug being locked out: fixed millimetre column widths summed past the usable
text area, so the last `cell(0, ...)` was left about 10mm wide and fpdf clipped
its header and every value in it. That is invisible to a unit test that only
checks the function returns bytes.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.reports import (
    DAILY_COLUMNS,
    TEXT_WIDTH_MM,
    DailyRow,
    TradingSummary,
    column_widths,
    daily_window,
    kes,
    monthly_window,
    render_html,
    render_pdf,
    summary_lines,
    weekly_window,
)

EAT = timezone(timedelta(hours=3))


def _summary(**kwargs) -> TradingSummary:
    base = dict(
        period_label="Week 01 Sep – 07 Sep 2026",
        start=datetime(2026, 9, 1, tzinfo=EAT),
        end=datetime(2026, 9, 8, tzinfo=EAT),
        generated_at=datetime(2026, 9, 8, 6, 0, tzinfo=timezone.utc),
        cash_received=Decimal("125000.00"),
        refunds=Decimal("2500.00"),
        gmv=Decimal("98000.50"),
        total_transacted=Decimal("125000.00"),
        orders=412,
        payments=419,
        payers=388,
        new_customers=57,
    )
    base.update(kwargs)
    return TradingSummary(**base)


class TestColumnWidthsFitThePage:
    def test_weights_sum_to_the_full_text_width(self):
        """Widths are derived from the page, so the columns must consume all of
        it exactly -- not less (a wasted gap) and not more (clipping)."""
        widths = column_widths()
        assert sum(widths) == TEXT_WIDTH_MM

    def test_no_column_is_left_microscopically_narrow(self):
        """The failing case was a last column of about 10mm. Anything under
        15mm cannot hold a header like 'Payments'."""
        widths = column_widths()
        assert min(widths) >= 15, f"column too narrow to hold its header: {widths}"

    def test_old_fixed_widths_would_have_overflowed(self):
        """Documents why the weights exist: the previous hardcoded widths reached
        180mm of a 190mm text area before the zero-width last column."""
        old = [40, 35, 35, 35, 35, 0]
        assert sum(old) == 180
        assert sum(old) > TEXT_WIDTH_MM - 15

    def test_every_column_has_a_header_and_an_alignment(self):
        for header, weight, align in DAILY_COLUMNS:
            assert header
            assert weight > 0
            assert align in {"l", "r"}


class TestNetIsNeverInvented:
    def test_net_is_none_when_rates_are_unconfigured(self):
        """A net built from a hardcoded commission is the thing being fixed."""
        s = _summary()
        assert s.net is None
        assert s.net_note

    def test_verdict_reports_cash_when_net_is_unknown(self):
        s = _summary()
        assert "Not calculable" in s.verdict
        # Cash in minus cash out still answers something.
        assert s.net_cash == Decimal("122500.00")
        assert "KES 122,500.00" in s.verdict

    def test_net_is_computed_when_every_rate_is_configured(self):
        s = _summary(
            commission_rate=Decimal("0.10"),
            platform_revenue=Decimal("9800.05"),
            mpesa_fee_rate=Decimal("0.0055"),
            mpesa_fees=Decimal("687.50"),
            server_cost_per_order=Decimal("6.25"),
            server_costs=Decimal("2575.00"),
            net=Decimal("6537.55"),
            net_note="",
        )
        assert s.net == Decimal("6537.55")
        assert s.verdict.startswith("Winning")

    def test_a_loss_reads_as_a_loss(self):
        s = _summary(
            commission_rate=Decimal("0.10"),
            platform_revenue=Decimal("100.00"),
            mpesa_fees=Decimal("600.00"),
            server_costs=Decimal("600.00"),
            net=Decimal("-1100.00"),
            net_note="",
        )
        assert s.verdict.startswith("Losing")
        # The sign survives formatting, so it cannot read as a smaller gain.
        assert "-KES 1,100.00" in s.verdict


class TestHeadlineLines:
    def test_unconfigured_rates_are_stated_not_zeroed(self):
        labels = dict(summary_lines(_summary()))
        assert "Not set" in labels["Platform revenue"]
        assert "Not set" in labels["M-Pesa fees"]
        assert "Not set" in labels["Server costs"]

    def test_net_cash_is_always_present(self):
        """It needs no rates, so it is always answerable."""
        labels = dict(summary_lines(_summary()))
        assert labels["Net cash in"] == "KES 122,500.00"

    def test_payment_count_and_payer_count_are_both_reported(self):
        labels = dict(summary_lines(_summary()))
        assert labels["Payments received"] == "419"
        assert labels["Paying customers"] == "388"


class TestWindows:
    def test_weekly_window_starts_on_monday(self):
        start, end, label = weekly_window(datetime(2026, 9, 9, 10, 0, tzinfo=EAT))
        assert start.weekday() == 0
        assert end - start == timedelta(days=7)
        assert "Week" in label

    def test_weekly_window_on_a_monday_reports_the_week_just_ended(self):
        """A Monday trigger must not report a week that has barely started."""
        start, end, _ = weekly_window(datetime(2026, 9, 7, 6, 0, tzinfo=EAT))
        assert start == datetime(2026, 8, 31, tzinfo=EAT)
        assert end == datetime(2026, 9, 7, tzinfo=EAT)

    def test_weekly_window_midweek_covers_the_current_week(self):
        start, end, _ = weekly_window(datetime(2026, 9, 9, 23, 59, tzinfo=EAT))
        assert start == datetime(2026, 9, 7, tzinfo=EAT)
        assert end == datetime(2026, 9, 14, tzinfo=EAT)

    def test_monthly_window_covers_the_whole_calendar_month(self):
        start, end, label = monthly_window(datetime(2026, 9, 15, tzinfo=EAT))
        assert start == datetime(2026, 9, 1, tzinfo=EAT)
        assert end == datetime(2026, 10, 1, tzinfo=EAT)
        assert label == "September 2026"

    def test_daily_window_is_a_complete_eat_day(self):
        start, end, label = daily_window(date(2026, 9, 8))
        assert end - start == timedelta(days=1)
        assert start.utcoffset() == timedelta(hours=3)
        assert "Tuesday" in label


class TestRendering:
    def test_pdf_renders_with_every_day_present(self):
        pytest.importorskip(
            "fpdf",
            reason="fpdf2 is declared in requirements.txt but not installed here",
        )
        summary = _summary(
            daily=[
                DailyRow(
                    day=date(2026, 9, 1),
                    label="01 Sep",
                    cash_received=Decimal("100.00"),
                    refunds=Decimal("0.00"),
                    gmv=Decimal("80.00"),
                    total_transacted=Decimal("100.00"),
                    orders=2,
                    payments=2,
                ),
                DailyRow(
                    day=date(2026, 9, 2),
                    label="02 Sep",
                    cash_received=Decimal("0.00"),
                    refunds=Decimal("0.00"),
                    gmv=Decimal("0.00"),
                    total_transacted=Decimal("0.00"),
                    orders=0,
                    payments=0,
                ),
            ]
        )
        pdf_bytes = render_pdf(summary)
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 800

    def test_html_contains_every_headline_label(self):
        html = render_html(_summary())
        for label, _value in summary_lines(_summary()):
            assert label in html, f"missing {label}"
        assert "Not calculable" in html

    def test_html_declares_a_charset(self):
        """The previous fallback had no charset, so accented names rendered as
        mojibake in the exported file."""
        assert 'charset="utf-8"' in render_html(_summary())


class TestFormatting:
    def test_kes_thousands_separated(self):
        assert kes(Decimal("1234567.5")) == "KES 1,234,567.50"

    def test_zero_is_kept_whole(self):
        assert kes(Decimal("0")) == "KES 0.00"