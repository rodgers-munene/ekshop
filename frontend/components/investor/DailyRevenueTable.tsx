import Link from "next/link";
import { formatKES } from "@/lib/utils";
import { InvestorDailyRevenueResponse } from "@/types/interface";

export default function DailyRevenueTable({
  data,
  buildHref,
}: {
  data: InvestorDailyRevenueResponse;
  buildHref: (page: number) => string;
}) {
  const totalPages = Math.max(1, Math.ceil(data.total / data.limit));

  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <p className="text-sm font-semibold">Daily revenue</p>
        <span className="text-xs text-muted">{data.total} day{data.total === 1 ? "" : "s"} with sales</span>
      </div>
      {data.results.length === 0 ? (
        <p className="text-sm text-muted px-4 py-6">No sales in this period.</p>
      ) : (
        <div className="divide-y divide-border">
          {data.results.map((row) => (
            <div key={row.date} className="flex items-center justify-between px-4 py-3 text-sm">
              <span>
                {new Date(row.date).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" })}
              </span>
              <span className="text-xs text-muted">{row.orders} order{row.orders === 1 ? "" : "s"}</span>
              <span className="font-bold">{formatKES(row.revenue)}</span>
            </div>
          ))}
        </div>
      )}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 px-4 py-3 border-t border-border">
          {data.page > 1 ? (
            <Link href={buildHref(data.page - 1)} className="text-xs px-3 py-1.5 rounded-md border border-border hover:bg-surface transition-colors">
              ← Prev
            </Link>
          ) : (
            <span className="text-xs px-3 py-1.5 rounded-md border border-border opacity-40">← Prev</span>
          )}
          <span className="text-xs text-muted">Page {data.page} of {totalPages}</span>
          {data.page < totalPages ? (
            <Link href={buildHref(data.page + 1)} className="text-xs px-3 py-1.5 rounded-md border border-border hover:bg-surface transition-colors">
              Next →
            </Link>
          ) : (
            <span className="text-xs px-3 py-1.5 rounded-md border border-border opacity-40">Next →</span>
          )}
        </div>
      )}
    </div>
  );
}
