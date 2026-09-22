"use client";

import React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RecentOrderListResponse, RecentOrderRow } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import Pagination from "@/components/admin/Pagination";

const LIMIT = 20;

export default function AdminOrdersPage() {
  const [page, setPage] = React.useState(1);
  const queryClient = useQueryClient();

  const { data, isPending: loading } = useQuery({
    queryKey: ["admin", "orders", page],
    queryFn: () =>
      fetch(`/api/admin/orders?page=${page}&limit=${LIMIT}`)
        .then((r) => r.json())
        .then((data): RecentOrderListResponse =>
          data && Array.isArray(data.results) ? data : { total: 0, page: 1, limit: LIMIT, results: [] }
        ),
  });

  const orders = (data?.results ?? []) as RecentOrderRow[];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / LIMIT));

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["admin", "orders"] });
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Orders</h1>

      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : orders.length === 0 ? (
        <div className="card p-10 text-center text-muted text-sm">No orders found.</div>
      ) : (
        <div className="card divide-y divide-border overflow-hidden">
          {orders.map((order) => (
            <div key={order.id} className="flex items-center justify-between gap-4 p-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-mono text-xs text-muted">
                    #{order.short_id?.toUpperCase()}
                  </p>
                  <span className="text-xs text-muted">
                    {order.shop_count} shop{order.shop_count !== 1 ? "s" : ""} · {order.item_count} item{order.item_count !== 1 ? "s" : ""}
                  </span>
                </div>
                <p className="text-sm font-medium mt-1 truncate">{order.buyer_name}</p>
                <p className="text-xs text-muted">
                  {new Date(order.created_at).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className="font-bold text-ink">{formatKES(order.total)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
