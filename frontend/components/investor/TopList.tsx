import { formatKES } from "@/lib/utils";

export default function TopList({
  title,
  items,
}: {
  title: string;
  items: { label: string; orders: number; revenue: string }[];
}) {
  return (
    <div className="card p-5">
      <p className="text-sm font-semibold mb-4">{title}</p>
      {items.length === 0 ? (
        <p className="text-sm text-muted">No data yet.</p>
      ) : (
        <div className="space-y-3">
          {items.map((item, i) => (
            <div key={`${item.label}-${i}`} className="flex items-center gap-3">
              <span className="w-5 text-xs font-bold text-muted shrink-0">{i + 1}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{item.label}</p>
                <p className="text-xs text-muted">{item.orders} order{item.orders === 1 ? "" : "s"}</p>
              </div>
              <p className="text-sm font-bold shrink-0">{formatKES(parseFloat(item.revenue))}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
