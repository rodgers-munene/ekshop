import type { Metadata } from "next";
import Link from "next/link";
import { serverFetch } from "@/lib/server-api";
import { InvestorDailyRevenueResponse, InvestorOverview, InvestorTrendPoint } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import StatCard from "@/components/dashboard/StatCard";
import SalesChart from "@/components/dashboard/SalesChart";
import OrderStatusBreakdown from "@/components/dashboard/OrderStatusBreakdown";
import TopList from "@/components/investor/TopList";
import DailyRevenueTable from "@/components/investor/DailyRevenueTable";

export const metadata: Metadata = {
  title: "Ekshop Store",
  robots: { index: false, follow: false, nocache: true },
};

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

interface Props {
  searchParams: Promise<{ year?: string; month?: string; page?: string }>;
}

export default async function InvestorBriefingPage({ searchParams }: Props) {
  const { year: yearParam, month: monthParam, page: pageParam } = await searchParams;
  const year = yearParam ? parseInt(yearParam) : undefined;
  const month = monthParam ? parseInt(monthParam) : undefined;
  const page = pageParam ? parseInt(pageParam) : 1;

  const trendParams = new URLSearchParams();
  if (year) trendParams.set("year", String(year));
  if (month) trendParams.set("month", String(month));

  const dailyParams = new URLSearchParams(trendParams);
  dailyParams.set("page", String(page));
  dailyParams.set("limit", "15");

  const [overview, trend, dailyRevenue] = await Promise.all([
    serverFetch<InvestorOverview>("/investor/overview").catch(() => null),
    serverFetch<InvestorTrendPoint[]>(`/investor/trend?${trendParams}`).catch(() => [] as InvestorTrendPoint[]),
    serverFetch<InvestorDailyRevenueResponse>(`/investor/daily-revenue?${dailyParams}`).catch(
      () => ({ total: 0, page: 1, limit: 15, results: [] }) as InvestorDailyRevenueResponse
    ),
  ]);

  if (!overview) {
    return <p className="text-muted text-sm p-8">Could not load investor data.</p>;
  }

  const statusTotal = Object.values(overview.order_status_counts).reduce((sum, n) => sum + n, 0);

  const periodLabel = year && month ? `${MONTH_NAMES[month - 1]} ${year}` : year ? `${year}` : "last 30 days";

  function buildHref(overrides: { year?: number; month?: number; page?: number }) {
    const params = new URLSearchParams();
    const y = overrides.year !== undefined ? overrides.year : year;
    const m = overrides.month !== undefined ? overrides.month : month;
    const p = overrides.page !== undefined ? overrides.page : undefined;
    if (y) params.set("year", String(y));
    if (m) params.set("month", String(m));
    if (p && p > 1) params.set("page", String(p));
    const qs = params.toString();
    return qs ? `/ir-f1c04c9098?${qs}` : "/ir-f1c04c9098";
  }

  return (
    <div className="w-full max-w-6xl mx-auto px-4 md:px-8 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Ekshop data</h1>
        <p className="text-xs text-muted mt-1">Confidential - platform performance snapshot</p>
      </div>

      <div className="card p-4 mb-6 flex flex-wrap items-end gap-3">
        <form method="get" className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs text-muted mb-1">Year</label>
            <select name="year" defaultValue={year ?? ""} className="input-field text-sm py-1.5">
              <option value="">All time</option>
              {overview.available_years.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Month</label>
            <select name="month" defaultValue={month ?? ""} className="input-field text-sm py-1.5">
              <option value="">All months</option>
              {MONTH_NAMES.map((name, i) => (
                <option key={name} value={i + 1}>{name}</option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn-navy text-sm py-1.5 px-4">Apply</button>
        </form>
        {(year || month) && (
          <Link href="/ir-f1c04c9098" className="text-xs text-amber underline underline-offset-2">
            Clear filter
          </Link>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Revenue (total)" value={formatKES(overview.revenue_total)} />
        <StatCard label="Revenue (30d)" value={formatKES(overview.revenue_30d)} />
        <StatCard label="Revenue (7d)" value={formatKES(overview.revenue_7d)} />
        <StatCard label="Losses (refunds/cancellations)" value={formatKES(overview.losses_total)} />
        <StatCard label="Paid orders (total)" value={overview.total_orders} />
        <StatCard label="Orders (30d)" value={overview.orders_30d} />
        <StatCard label="Orders (7d)" value={overview.orders_7d} />
        <StatCard label="Lost orders" value={overview.losses_count} />
        <StatCard label="Buyers" value={overview.total_buyers} />
        <StatCard label="Sellers" value={overview.total_sellers} />
        <StatCard label="Shops" value={overview.total_shops} />
        <StatCard label="Products" value={overview.total_products} />
      </div>

      {trend.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <SalesChart
            data={trend.map((p) => ({ label: p.label, value: p.revenue }))}
            title={`Revenue (${periodLabel})`}
          />
          <SalesChart
            data={trend.map((p) => ({ label: p.label, value: p.orders }))}
            title={`Orders (${periodLabel})`}
            formatValue={(v) => `${v} order${v === 1 ? "" : "s"}`}
          />
        </div>
      )}

      <div className="mb-6">
        <DailyRevenueTable
          data={dailyRevenue}
          buildHref={(p) => buildHref({ page: p })}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <OrderStatusBreakdown counts={overview.order_status_counts} total={statusTotal} />
        <TopList
          title="Top sellers"
          items={overview.top_sellers.map((s) => ({ label: s.shop_name, orders: s.orders, revenue: s.revenue }))}
        />
        <TopList
          title="Top buyers"
          items={overview.top_buyers.map((b) => ({ label: b.name, orders: b.orders, revenue: b.revenue }))}
        />
      </div>
    </div>
  );
}
