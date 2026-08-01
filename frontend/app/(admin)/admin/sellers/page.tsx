"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { BadgeCheck } from "lucide-react";
import { PaginatedResponse, Shop } from "@/types/interface";
import Pagination from "@/components/admin/Pagination";

type Filter = "pending" | "active" | "suspended" | "all";
const LIMIT = 20;

export default function AdminSellersPage() {
  const [filter, setFilter] = useState<Filter>("pending");
  const [page, setPage] = useState(1);
  const queryClient = useQueryClient();

  const { data, isPending: loading } = useQuery({
    queryKey: ["admin", "shops", filter, page],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), limit: String(LIMIT) });
      if (filter !== "all") params.set("status", filter);
      return fetch(`/api/admin/shops?${params}`)
        .then((r) => r.json())
        .then((data): PaginatedResponse<Shop> =>
          data && Array.isArray(data.results) ? data : { total: 0, page: 1, limit: LIMIT, results: [] }
        );
    },
  });
  const shops = data?.results ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / LIMIT));

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["admin", "shops", filter, page] });
  }

  function selectFilter(f: Filter) {
    setPage(1);
    setFilter(f);
  }

  async function verify(shopId: string) {
    const res = await fetch(`/api/admin/shops/${shopId}/verify`, { method: "PATCH" });
    if (!res.ok) { toast.error("Could not verify shop"); return; }
    toast.success("Shop verified");
    refresh();
  }

  async function suspend(shopId: string) {
    if (!confirm("Suspend this shop? The seller will no longer be able to sell.")) return;
    const res = await fetch(`/api/admin/shops/${shopId}/suspend`, { method: "PATCH" });
    if (!res.ok) { toast.error("Could not suspend shop"); return; }
    toast.success("Shop suspended");
    refresh();
  }

  async function feature(shopId: string, currentlyFeatured: boolean) {
    const res = await fetch(`/api/admin/shops/${shopId}/feature`, { method: "PATCH" });
    if (!res.ok) { toast.error("Could not update featured status"); return; }
    toast.success(currentlyFeatured ? "Shop unfeatured" : "Shop featured");
    refresh();
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Sellers</h1>

      <div className="flex gap-2 mb-6">
        {(["pending", "active", "suspended", "all"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => selectFilter(f)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium capitalize transition-colors ${
              filter === f ? "bg-navy text-white" : "bg-surface text-muted hover:bg-ink/10"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : shops.length === 0 ? (
        <div className="card p-10 text-center text-muted text-sm">No shops in this filter.</div>
      ) : (
        <div className="card divide-y divide-border overflow-hidden">
          {shops.map((shop) => (
            <div key={shop.id} className="flex items-center justify-between gap-4 p-4">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <p className="font-medium truncate">{shop.name}</p>
                  {shop.is_verified && <BadgeCheck size={14} className="text-info shrink-0" />}
                </div>
                <p className="text-xs text-muted truncate">{shop.county ?? "Unknown"} · {shop.slug}</p>
              </div>
              <div className="flex gap-2 shrink-0">
                {!shop.is_verified && (
                  <button onClick={() => verify(shop.id)} className="btn-accent text-xs py-1.5 px-3">
                    Verify
                  </button>
                )}
                <button
                  onClick={() => feature(shop.id, shop.is_featured)}
                  className={`text-xs py-1.5 px-3 rounded-md border ${
                    shop.is_featured
                      ? "border-accent text-accent hover:bg-accent/5"
                      : "border-border text-muted hover:bg-ink/5"
                  }`}
                >
                  {shop.is_featured ? "Unfeature" : "Feature"}
                </button>
                <button onClick={() => suspend(shop.id)} className="text-xs py-1.5 px-3 rounded-md border border-danger text-danger hover:bg-danger/5">
                  Suspend
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
