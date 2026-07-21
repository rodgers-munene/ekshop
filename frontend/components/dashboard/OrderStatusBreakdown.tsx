const STATUS_COLOR: Record<string, string> = {
  pending: "bg-amber",
  confirmed: "bg-info",
  processing: "bg-info",
  shipped: "bg-progress",
  delivered: "bg-success",
  cancelled: "bg-danger",
  refunded: "bg-danger",
};

export default function OrderStatusBreakdown({ counts, total }: { counts: Record<string, number>; total: number }) {
  const entries = Object.entries(counts).filter(([, count]) => count > 0);

  return (
    <div className="card p-5">
      <p className="text-sm font-semibold mb-4">Orders by status</p>
      {entries.length === 0 ? (
        <p className="text-sm text-muted">No orders yet.</p>
      ) : (
        <div className="space-y-3">
          {entries.map(([status, count]) => (
            <div key={status}>
              <div className="flex justify-between text-xs mb-1">
                <span className="capitalize font-medium">{status}</span>
                <span className="text-muted">{count}</span>
              </div>
              <div className="h-1.5 rounded-full bg-surface overflow-hidden">
                <div
                  className={`h-full rounded-full ${STATUS_COLOR[status] ?? "bg-ink"}`}
                  style={{ width: `${total ? (count / total) * 100 : 0}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
