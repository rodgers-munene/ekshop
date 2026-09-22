"use client";

import React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { AdminProductListResponse, AdminProductRow } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import Pagination from "@/components/admin/Pagination";

const LIMIT = 20;

const STATUS_STYLE: Record<string, string> = {
  active: "bg-success/10 text-success",
  draft: "bg-ink/10 text-ink",
  paused: "bg-amber/15 text-amber",
};

export default function AdminProductsPage() {
  const [page, setPage] = React.useState(1);
  const queryClient = useQueryClient();

  const { data, isPending: loading } = useQuery({
    queryKey: ["admin", "products", page],
    queryFn: () =>
      fetch(`/api/admin/products?page=${page}&limit=${LIMIT}`)
        .then((r) => r.json())
        .then((data): AdminProductListResponse =>
          data && Array.isArray(data.results) ? data : { total: 0, page: 1, limit: LIMIT, results: [] }
        ),
  });

  const products = (data?.results ?? []) as AdminProductRow[];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / LIMIT));

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["admin", "products"] });
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Products</h1>

      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : products.length === 0 ? (
        <div className="card p-10 text-center text-muted text-sm">No products found.</div>
      ) : (
        <div className="card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="px-4 py-3 font-medium">Product</th>
                <th className="px-4 py-3 font-medium">Shop</th>
                <th className="px-4 py-3 font-medium">Price</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {products.map((product) => (
                <tr key={product.id} className="hover:bg-surface/50 transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/products/${product.id}`} className="font-medium hover:text-amber">
                      {product.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted">{product.shop_name ?? "—"}</td>
                  <td className="px-4 py-3">{formatKES(product.price)}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${STATUS_STYLE[product.status] ?? "bg-ink/10 text-ink"}`}>
                      {product.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted">
                    {new Date(product.created_at).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
