import { formatKES } from "@/lib/utils";

export default function TopProducts({ products }: { products: { name: string; qty: number; revenue: number }[] }) {
  return (
    <div className="card p-5">
      <p className="text-sm font-semibold mb-4">Top products</p>
      {products.length === 0 ? (
        <p className="text-sm text-muted">No sales yet.</p>
      ) : (
        <div className="space-y-3">
          {products.map((p, i) => (
            <div key={p.name} className="flex items-center gap-3">
              <span className="w-5 text-xs font-bold text-muted shrink-0">{i + 1}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{p.name}</p>
                <p className="text-xs text-muted">{p.qty} sold</p>
              </div>
              <p className="text-sm font-bold shrink-0">{formatKES(p.revenue)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
