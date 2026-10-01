import { serverFetch } from "@/lib/server-api";
import { RevenueBreakdown } from "@/types/interface";
import RevenueBreakdownPanel from "@/components/admin/RevenueBreakdownPanel";

export default async function AdminRevenuePage() {
  const data = await serverFetch<RevenueBreakdown>("/admin/metrics/revenue-breakdown").catch(() => null);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Revenue</h1>
        <p className="text-sm text-muted">
          Paid orders only, grouped by Kenyan calendar day. GMV is goods sold. Total collected adds delivery fees.
        </p>
      </div>
      {data ? (
        <RevenueBreakdownPanel data={data} />
      ) : (
        <p className="text-muted text-sm">Could not load the revenue breakdown.</p>
      )}
    </div>
  );
}
