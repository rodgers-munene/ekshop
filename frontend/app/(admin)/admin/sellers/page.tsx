"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { BadgeCheck, ChevronRight, Star } from "lucide-react";
import { PaginatedResponse, Shop } from "@/types/interface";
import Pagination from "@/components/admin/Pagination";
import ActionButton from "@/components/admin/ActionButton";
import MessageUserButton from "@/components/MessageUserButton";

type Filter = "pending" | "active" | "suspended" | "all";
const LIMIT = 20;

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber/15 text-amber",
  active: "bg-success/10 text-success",
  suspended: "bg-danger/10 text-danger",
};

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
    queryClient.invalidateQueries({ queryKey: ["admin", "shops"] });
  }

  function selectFilter(f: Filter) {
    setPage(1);
    setFilter(f);
  }

  // Each returns whether it succeeded, so ActionButton knows whether to show
  // the confirmation tick or drop straight back to its idle label.
  async function verify(shopId: string) {
    const res = await fetch(`/api/admin/shops/${shopId}/verify`, { method: "PATCH" });
    if (!res.ok) { toast.error("Could not verify shop"); return false; }
    toast.success("Shop verified");
    refresh();
    return true;
  }

  async function suspend(shopId: string) {
    const res = await fetch(`/api/admin/shops/${shopId}/suspend`, { method: "PATCH" });
    if (!res.ok) { toast.error("Could not suspend shop"); return false; }
    toast.success("Shop suspended");
    refresh();
    return true;
  }

  async function feature(shopId: string, currentlyFeatured: boolean) {
    const res = await fetch(`/api/admin/shops/${shopId}/feature`, { method: "PATCH" });
    if (!res.ok) { toast.error("Could not update featured status"); return false; }
    toast.success(currentlyFeatured ? "Shop unfeatured" : "Shop featured");
    refresh();
    return true;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Sellers</h1>

      <div className="flex gap-2 mb-6 overflow-x-auto scrollbar-hide">
        {(["pending", "active", "suspended", "all"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => selectFilter(f)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium capitalize shrink-0 transition-colors ${
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
            <div key={shop.id} className="p-4">
              {/* The name and the actions used to share a row, which on a phone
                  squeezed the shop name down to a few characters. They stack
                  until there is desktop width to put them side by side. */}
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between md:gap-4">
                <Link
                  href={`/admin/sellers/${shop.id}`}
                  className="group min-w-0 flex items-start justify-between gap-2"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <p className="font-medium truncate group-hover:text-amber transition-colors">
                        {shop.name}
                      </p>
                      {shop.is_verified && <BadgeCheck size={14} className="text-info shrink-0" />}
                      {shop.is_featured && <Star size={13} className="text-amber fill-current shrink-0" />}
                    </div>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1 text-xs text-muted">
                      {shop.status && (
                        <span className={`px-1.5 py-0.5 rounded-full font-medium capitalize ${STATUS_STYLES[shop.status] ?? "bg-surface"}`}>
                          {shop.status}
                        </span>
                      )}
                      <span className="truncate">{shop.county ?? "Location not set"}</span>
                      <span className="truncate">· {shop.slug}</span>
                    </div>
                  </div>
                  <ChevronRight size={16} className="text-muted shrink-0 mt-0.5 md:hidden" />
                </Link>

                <div className="flex flex-wrap gap-2 shrink-0">
                  {!shop.is_verified && (
                    <ActionButton
                      variant="accent"
                      pendingLabel="Verifying…"
                      onAction={() => verify(shop.id)}
                    >
                      Verify
                    </ActionButton>
                  )}
                  <ActionButton
                    pendingLabel="Saving…"
                    className={shop.is_featured ? "border-amber! text-amber! hover:bg-amber/5!" : ""}
                    onAction={() => feature(shop.id, shop.is_featured)}
                  >
                    {shop.is_featured ? "Unfeature" : "Feature"}
                  </ActionButton>
                  <ActionButton
                    variant="danger"
                    pendingLabel="Suspending…"
                    confirm="Suspend this shop? The seller will no longer be able to sell."
                    onAction={() => suspend(shop.id)}
                  >
                    Suspend
                  </ActionButton>
                  {shop.seller_id && <MessageUserButton userId={shop.seller_id} userName={shop.name} />}
                  <Link
                    href={`/admin/sellers/${shop.id}`}
                    className="hidden md:inline-flex items-center text-xs font-medium py-1.5 px-3 rounded-md text-amber hover:bg-amber/5"
                  >
                    View details
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
