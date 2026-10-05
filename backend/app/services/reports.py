"""Trading reports: the figures that answer "are we winning or losing".

This module exists because the numbers that matter most were the least
trustworthy. Three separate problems, all of which made the report read as
measured while being invented or mislabelled:

1. `dashboard_metrics.get_margin_leakage_metrics` hardcoded a 10% commission, a
   0.55% M-Pesa rate and a KES 6.25 per-order server cost. Meanwhile
   `settings.PLATFORM_COMMISSION_RATE` was deliberately left unset so the
   dashboard would report revenue as unknown rather than invent it. So the same
   platform showed an invented commission in one place and an honest blank in
   another.

2. That function's `net_profit` was structurally wrong regardless of the rates.
   It started from GMV -- the value of the *goods*, which the platform sells on
   behalf of merchants and does not own -- then subtracted commission as though
   it were a cost, then subtracted fees. The result was neither revenue nor
   profit. Money passing through the platform is not money kept by it.

3. The PDF export drew its table with fixed column widths summing to 180mm on a
   page with ~190mm usable, leaving the final `cell(0, ...)` about 10mm wide.
   fpdf truncated the last header and its values, which is why the report looked
   like two columns were overriding the others.

Everything here is on the payment basis (`payments.paid_at`) used by the rest of
the dashboard, so a report and a stat card for the same window agree.

Figures are reported as either measured or unknown. Nothing is defaulted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Numeric, cast, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.commerce import OrderGroup, Order, OrderItem
from app.models.payment import Payment, PaymentStatus
from app.models.user import User

EAT = timezone(timedelta(hours=3), "EAT")

TWO_PLACES = Decimal("0.01")

# A4 portrait in millimetres, with fpdf2's default 10mm margins. Held here
# rather than read from an FPDF instance so the column arithmetic can be tested
# without fpdf2 installed -- it is declared in requirements.txt but is not always
# present, and the widths are exactly the thing that was wrong.
PAGE_WIDTH_MM = 210.0
PAGE_MARGIN_MM = 10.0
TEXT_WIDTH_MM = PAGE_WIDTH_MM - 2 * PAGE_MARGIN_MM


def money_instant():
    """When a payment's money actually landed.

    `paid_at` is populated from the c9d0e1f2a3b4 backfill onward; the coalesce
    keeps rows written before it in the correct window.
    """
    return func.coalesce(Payment.paid_at, Payment.created_at)


def _q(value) -> Decimal:
    return Decimal(value or 0).quantize(TWO_PLACES)


def kes(value) -> str:
    """Formatted for a report. Negative values keep their sign so a loss reads
    as a loss rather than as a smaller positive number."""
    amount = _q(value)
    return f"{'-' if amount < 0 else ''}KES {abs(amount):,.2f}"


@dataclass
class DailyRow:
    day: date
    label: str
    cash_received: Decimal = Decimal("0.00")
    refunds: Decimal = Decimal("0.00")
    gmv: Decimal = Decimal("0.00")
    total_transacted: Decimal = Decimal("0.00")
    orders: int = 0
    payments: int = 0


@dataclass
class TradingSummary:
    """One report for one window. Every field is either measured or explicitly
    unknown -- there is no zero standing in for "we do not know"."""

    period_label: str
    start: datetime
    end: datetime
    generated_at: datetime

    cash_received: Decimal = Decimal("0.00")
    refunds: Decimal = Decimal("0.00")
    gmv: Decimal = Decimal("0.00")
    total_transacted: Decimal = Decimal("0.00")
    orders: int = 0
    payments: int = 0
    payers: int = 0
    new_customers: int = 0

    # None means "not configured", which is different from zero.
    commission_rate: Optional[Decimal] = None
    platform_revenue: Optional[Decimal] = None
    mpesa_fee_rate: Optional[Decimal] = None
    mpesa_fees: Optional[Decimal] = None
    server_cost_per_order: Optional[Decimal] = None
    server_costs: Optional[Decimal] = None
    # Net only exists when every input to it is known.
    net: Optional[Decimal] = None
    net_note: str = ""

    daily: List[DailyRow] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Invariant: an unknown net always carries a reason. A None net with a
        # blank note is how a report ends up printing an unexplained gap.
        if self.net is None and not self.net_note:
            self.net_note = (
                "a required rate is not configured, so this is not estimated. "
            )

    @property
    def net_cash(self) -> Decimal:
        """Money in minus money out. Always computable -- it needs no rates."""
        return _q(self.cash_received - self.refunds)

    @property
    def average_order_value(self) -> Decimal:
        if not self.orders:
            return Decimal("0.00")
        return _q(self.total_transacted / self.orders)

    @property
    def verdict(self) -> str:
        """A one-line plain answer, never a euphemism."""
        net = self.net
        if net is None:
            return (
                f"Not calculable: {self.net_note.strip()} "
                f"Cash received {kes(self.net_cash)}."
            )
        if net > 0:
            return f"Winning: {kes(net)} over {self.period_label}."
        if net < 0:
            return f"Losing: {kes(net)} over {self.period_label}."
        return f"Break-even over {self.period_label}."


def build_trading_summary(
    db: Session,
    start: datetime,
    end: datetime,
    period_label: str,
) -> TradingSummary:
    instant = money_instant()

    cash, payments = (
        db.query(
            func.coalesce(func.sum(cast(Payment.amount, Numeric)), 0),
            func.count(Payment.id),
        )
        .filter(
            Payment.status == PaymentStatus.success,
            instant >= start,
            instant < end,
        )
        .one()
    )
    payers = (
        db.query(func.count(func.distinct(Payment.user_id)))
        .filter(
            Payment.status == PaymentStatus.success,
            instant >= start,
            instant < end,
        )
        .scalar()
        or 0
    )
    refunded = (
        db.query(func.coalesce(func.sum(cast(Payment.amount, Numeric)), 0))
        .filter(
            Payment.status == PaymentStatus.refunded,
            instant >= start,
            instant < end,
        )
        .scalar()
    )

    # Distinct baskets behind those payments, so a retried push cannot inflate
    # the basket figures past what was actually taken.
    paid_pairs = (
        db.query(
            func.date_trunc(
                "day", func.timezone("Africa/Nairobi", instant)
            ).label("day"),
            Payment.order_group_id.label("gid"),
        )
        .filter(
            Payment.status == PaymentStatus.success,
            instant >= start,
            instant < end,
        )
        .distinct()
        .subquery()
    )
    basket_totals = (
        db.query(
            paid_pairs.c.day.label("day"),
            func.count(OrderGroup.id).label("orders"),
            func.sum(cast(OrderGroup.total, Numeric)).label("transacted"),
        )
        .select_from(paid_pairs)
        .join(OrderGroup, OrderGroup.id == paid_pairs.c.gid)
        .group_by(paid_pairs.c.day)
        .subquery()
    )
    basket_rows = db.query(
        basket_totals.c.day, basket_totals.c.orders, basket_totals.c.transacted
    ).all()

    gmv_rows = (
        db.query(
            paid_pairs.c.day.label("day"),
            func.sum(cast(OrderItem.line_total, Numeric)).label("gmv"),
        )
        .select_from(paid_pairs)
        .join(Order, Order.group_id == paid_pairs.c.gid)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .group_by(paid_pairs.c.day)
        .all()
    )

    # Per-day cash and refunds, for the daily table.
    day_col = func.date_trunc("day", func.timezone("Africa/Nairobi", instant))
    cash_rows = (
        db.query(
            day_col.label("day"),
            func.coalesce(func.sum(cast(Payment.amount, Numeric)), 0),
            func.count(Payment.id),
        )
        .filter(
            Payment.status == PaymentStatus.success,
            instant >= start,
            instant < end,
        )
        .group_by(day_col)
        .all()
    )
    refund_rows = (
        db.query(
            day_col.label("day"),
            func.coalesce(func.sum(cast(Payment.amount, Numeric)), 0),
        )
        .filter(
            Payment.status == PaymentStatus.refunded,
            instant >= start,
            instant < end,
        )
        .group_by(day_col)
        .all()
    )

    cash_by_day = {r.day.date(): (r[1], r[2]) for r in cash_rows}
    refunds_by_day = {r.day.date(): r[1] for r in refund_rows}
    orders_by_day = {r.day.date(): (int(r.orders), _q(r.transacted)) for r in basket_rows}
    gmv_by_day = {r.day.date(): _q(r.gmv) for r in gmv_rows}

    summary = TradingSummary(
        period_label=period_label,
        start=start,
        end=end,
        generated_at=datetime.now(timezone.utc),
        cash_received=_q(cash),
        refunds=_q(refunded),
        orders=sum(v[0] for v in orders_by_day.values()),
        payments=int(payments or 0),
        payers=int(payers),
        gmv=sum(gmv_by_day.values(), Decimal("0.00")),
        total_transacted=sum((v[1] for v in orders_by_day.values()), Decimal("0.00")),
    )

    # Commission is a configured rate or nothing. A plausible-looking default is
    # worse than a blank, because a blank gets investigated.
    rate = settings.PLATFORM_COMMISSION_RATE
    if rate is not None:
        summary.commission_rate = Decimal(rate)
        summary.platform_revenue = _q(summary.gmv * Decimal(rate))

    fee_rate = getattr(settings, "MPESA_FEE_RATE", None)
    if fee_rate is not None:
        summary.mpesa_fee_rate = Decimal(fee_rate)
        summary.mpesa_fees = _q(summary.cash_received * Decimal(fee_rate))

    per_order = getattr(settings, "SERVER_COST_PER_ORDER", None)
    if per_order is not None:
        summary.server_cost_per_order = Decimal(per_order)
        summary.server_costs = _q(Decimal(summary.orders) * Decimal(per_order))

    missing = []
    if summary.platform_revenue is None:
        missing.append("PLATFORM_COMMISSION_RATE")
    if summary.mpesa_fees is None:
        missing.append("MPESA_FEE_RATE")
    if summary.server_costs is None:
        missing.append("SERVER_COST_PER_ORDER")
    if missing:
        summary.net = None
        summary.net_note = (
            "not configured: " + ", ".join(missing) + ". "
        )
    else:
        summary.net = _q(
            summary.platform_revenue - summary.mpesa_fees - summary.server_costs
        )

    summary.new_customers = (
        db.query(func.count(User.id))
        .filter(User.created_at >= start, User.created_at < end)
        .scalar()
        or 0
    )

    # Fill every day in the window, including the ones with no activity, so the
    # table cannot be read as "these were the only days that existed".
    day = start.astimezone(EAT).date()
    last = (end.astimezone(EAT) - timedelta(days=1)).date()
    while day <= last:
        orders, transacted = orders_by_day.get(day, (0, Decimal("0.00")))
        day_cash, day_payments = cash_by_day.get(day, (0, 0))
        summary.daily.append(
            DailyRow(
                day=day,
                label=day.strftime("%d %b"),
                cash_received=_q(day_cash),
                refunds=_q(refunds_by_day.get(day, 0)),
                gmv=gmv_by_day.get(day, Decimal("0.00")),
                total_transacted=transacted,
                orders=orders,
                payments=int(day_payments or 0),
            )
        )
        day += timedelta(days=1)

    return summary


def weekly_window(now: Optional[datetime] = None) -> tuple[datetime, datetime, str]:
    """Monday 00:00 EAT to the following Monday, as a closed-open window.

    A weekly report that ran "the last 7 days from whenever it was triggered"
    would not line up with the week anyone discusses on a Monday.
    """
    reference = (now or datetime.now(EAT)).astimezone(EAT)
    this_monday = reference.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=reference.weekday()
    )
    # On a Monday, report the week just finished rather than a week that has
    # barely started.
    if reference.date() == this_monday.date():
        this_monday -= timedelta(days=7)
    return this_monday, this_monday + timedelta(days=7), (
        f"Week {this_monday.strftime('%d %b')} – "
        f"{(this_monday + timedelta(days=6)).strftime('%d %b %Y')}"
    )


def monthly_window(now: Optional[datetime] = None) -> tuple[datetime, datetime, str]:
    """First of the month to the first of the next, in EAT."""
    reference = (now or datetime.now(EAT)).astimezone(EAT)
    first = reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if reference.date() == first.date():
        first = (first - timedelta(days=1)).replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return first, nxt, first.strftime("%B %Y")


def daily_window(day: date) -> tuple[datetime, datetime, str]:
    """One complete calendar day in EAT."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=EAT)
    return start, start + timedelta(days=1), day.strftime("%A %d %B %Y")


# ── Rendering ────────────────────────────────────────────────────────────────

# Column weights, not widths in millimetres. The renderer converts them to
# whatever the page actually allows. Hardcoded millimetre widths were how the
# last two columns ended up clipped: they summed to more than the text area.
DAILY_COLUMNS = [
    ("Day", 1.5, "l"),
    ("Received", 2.0, "r"),
    ("Refunds", 1.7, "r"),
    ("Net cash", 1.9, "r"),
    ("GMV", 1.9, "r"),
    ("Baskets", 1.4, "r"),
    ("Payments", 1.4, "r"),
]


def column_widths(text_width: Optional[float] = None) -> List[float]:
    """Millimetre widths for the daily table, summing exactly to the text area.

    Weights rather than literal widths, converted against the real text area. The
    previous renderer passed 40/35/35/35/35 and then `cell(0, ...)`: those five
    alone reached 180mm on a 190mm text area, so the zero-width last column was
    left ~10mm and fpdf clipped its header and every value under it.
    """
    available = TEXT_WIDTH_MM if text_width is None else text_width
    total_weight = sum(w for _, w, _ in DAILY_COLUMNS)
    return [available * w / total_weight for _, w, _ in DAILY_COLUMNS]


def _fmt_cell(value, column: str) -> str:
    if column == "l":
        return str(value)
    return f"{value:,.2f}"


def summary_lines(summary: TradingSummary) -> List[tuple[str, str]]:
    """Label/value pairs for the headline block.

    Unknown values are printed as such. A zero here would be a claim, and the
    whole reason this module exists is that claims were being made.
    """
    lines = [
        ("Cash received", kes(summary.cash_received)),
        ("Refunds paid out", kes(summary.refunds)),
        ("Net cash in", kes(summary.net_cash)),
        ("GMV (goods value)", kes(summary.gmv)),
        ("Total transacted", kes(summary.total_transacted)),
        ("Baskets paid", f"{summary.orders:,}"),
        ("Payments received", f"{summary.payments:,}"),
        ("Paying customers", f"{summary.payers:,}"),
        ("Average basket", kes(summary.average_order_value)),
        ("New customers", f"{summary.new_customers:,}"),
    ]
    if summary.commission_rate is not None:
        lines.append(
            (
                f"Platform revenue ({summary.commission_rate * 100:g}% commission)",
                kes(summary.platform_revenue or 0),
            )
        )
    else:
        lines.append(("Platform revenue", "Not set - no commission rate configured"))
    if summary.mpesa_fees is not None:
        lines.append(
            (f"M-Pesa fees ({summary.mpesa_fee_rate * 100:g}%)", kes(summary.mpesa_fees))
        )
    else:
        lines.append(("M-Pesa fees", "Not set - no fee rate configured"))
    if summary.server_costs is not None:
        lines.append(
            (
                f"Server costs (KES {summary.server_cost_per_order}/basket)",
                kes(summary.server_costs),
            )
        )
    else:
        lines.append(("Server costs", "Not set - no per-order cost configured"))
    lines.append(("Net", kes(summary.net) if summary.net is not None else f"Not calculable - {summary.net_note.strip()}"))
    return lines


def render_html(summary: TradingSummary) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{r.label}</td>"
        f"<td class='n'>{r.cash_received:,.2f}</td>"
        f"<td class='n'>{r.refunds:,.2f}</td>"
        f"<td class='n'>{r.cash_received - r.refunds:,.2f}</td>"
        f"<td class='n'>{r.gmv:,.2f}</td>"
        f"<td class='n'>{r.orders}</td>"
        f"<td class='n'>{r.payments}</td>"
        "</tr>"
        for r in summary.daily
    )
    headline = "".join(
        f"<tr><th>{label}</th><td class='n'>{value}</td></tr>"
        for label, value in summary_lines(summary)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Ekshop trading report - {summary.period_label}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif;
         color: #1a1a1a; margin: 24px; }}
  h1 {{ font-size: 20px; margin: 0 0 2px; }}
  .sub {{ color: #666; font-size: 13px; margin: 0 0 16px; }}
  .verdict {{ font-size: 15px; font-weight: 700; padding: 10px 12px;
              border-left: 4px solid #333; background: #f6f6f6; margin: 0 0 20px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px;
           font-size: 13px; table-layout: fixed; }}
  th, td {{ border: 1px solid #ddd; padding: 5px 8px; }}
  thead th {{ background: #f0f0f0; text-align: left; }}
  td.n, th.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tbody th {{ text-align: left; font-weight: 600; width: 46%; background: #fafafa; }}
  .note {{ color: #666; font-size: 12px; }}
</style>
</head>
<body>
  <h1>Ekshop Kenya - trading report</h1>
  <p class="sub">{summary.period_label} &middot; generated {summary.generated_at.astimezone(EAT).strftime('%d %b %Y %H:%M EAT')}</p>
  <p class="verdict">{summary.verdict}</p>
  <h2>Headline figures</h2>
  <table><tbody>{headline}</tbody></table>
  <h2>By day</h2>
  <table>
    <thead><tr>
      <th>Day</th><th class="n">Received</th><th class="n">Refunds</th>
      <th class="n">Net cash</th><th class="n">GMV</th>
      <th class="n">Baskets</th><th class="n">Payments</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="note">Received and refunds come from the payments table by the time the
  money arrived. Baskets and GMV count each order once, so a retried payment
  cannot inflate them. Net is left uncalculated rather than estimated when a rate
  it depends on is not configured.</p>
</body>
</html>"""


def render_pdf(summary: TradingSummary) -> bytes:
    """PDF via fpdf2, with column widths derived from the real page width.

    The previous version passed fixed 40/35/35/35/35mm widths and a final
    `cell(0, ...)`. Those summed past the text area, leaving the last column
    about 10mm wide, and fpdf silently clipped its header and values.
    """
    from fpdf import FPDF

    pdf = FPDF(orientation="P", unit="mm", format="A4", margins=(PAGE_MARGIN_MM, PAGE_MARGIN_MM, PAGE_MARGIN_MM, PAGE_MARGIN_MM))
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    text_width = pdf.w - pdf.l_margin - pdf.r_margin
    widths = column_widths(text_width)
    aligns = [a for _, _, a in DAILY_COLUMNS]
    headers = [h for h, _, _ in DAILY_COLUMNS]

    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, "Ekshop Kenya - trading report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0,
        6,
        f"{summary.period_label}  |  generated "
        f"{summary.generated_at.astimezone(EAT).strftime('%d %b %Y %H:%M')} EAT",
        ln=True,
    )
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, summary.verdict, ln=True)
    pdf.ln(3)

    # Headline block: label column plus one value column, both derived from the
    # page so nothing can run off the edge.
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(text_width, 8, "Headline figures", border=1, ln=True)
    pdf.set_font("Helvetica", "", 10)
    label_w = text_width * 0.58
    value_w = text_width - label_w
    for label, value in summary_lines(summary):
        # multi_cell wraps rather than clipping, which is what a fixed-height
        # cell does when the text does not fit.
        pdf.multi_cell(label_w, 6, label, border=1, align="L")
        pdf.multi_cell(value_w, 6, value, border=1, align="R")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(text_width, 8, "By day", border=1, ln=True)
    pdf.set_font("Helvetica", "B", 9)
    for header, width, align in zip(headers, widths, aligns):
        pdf.cell(width, 7, header, border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for row in summary.daily:
        values = [
            row.label,
            f"{row.cash_received:,.2f}",
            f"{row.refunds:,.2f}",
            f"{row.cash_received - row.refunds:,.2f}",
            f"{row.gmv:,.2f}",
            str(row.orders),
            str(row.payments),
        ]
        for value, width, align in zip(values, widths, aligns):
            pdf.cell(width, 6, str(value), border=1, align="A" + align)
        pdf.ln()

    return bytes(pdf.output())