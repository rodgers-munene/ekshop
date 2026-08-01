"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { Promotion, Product, ProductListResponse } from "@/types/interface";
import { resolveImageUrl, decodeHtml } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function AdminDealsPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [label, setLabel] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [sortDrafts, setSortDrafts] = useState<Record<string, string>>({});
  const searchRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(timeout);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const { data: suggestions = [] } = useQuery({
    queryKey: ["admin-deal-product-search", debouncedQuery],
    queryFn: () =>
      fetch(`${API_URL}/products/?q=${encodeURIComponent(debouncedQuery)}&limit=6`)
        .then((r) => r.json())
        .then((data: ProductListResponse) => data.results ?? []),
    enabled: debouncedQuery.length >= 2,
    staleTime: 60_000,
  });

  const { data: deals = [], isPending: loading } = useQuery({
    queryKey: ["admin", "deals"],
    queryFn: () =>
      fetch("/api/admin/deals")
        .then((r) => r.json())
        .then((data) => (Array.isArray(data) ? (data as Promotion[]) : [])),
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["admin", "deals"] });
  }

  async function addDeal(product: Product) {
    const res = await fetch("/api/admin/deals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_id: product.id,
        label: label.trim() || undefined,
        sort_order: parseInt(sortOrder, 10) || 0,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { toast.error(data.detail ?? "Could not add deal"); return; }
    toast.success("Deal added");
    setQuery("");
    setLabel("");
    setSortOrder("0");
    setShowSuggestions(false);
    refresh();
  }

  async function toggleActive(deal: Promotion) {
    const res = await fetch(`/api/admin/deals/${deal.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !deal.is_active }),
    });
    if (!res.ok) { toast.error("Could not update deal"); return; }
    refresh();
  }

  async function saveSortOrder(deal: Promotion) {
    const value = sortDrafts[deal.id];
    if (value === undefined) return;
    const parsed = parseInt(value, 10);
    if (Number.isNaN(parsed)) { toast.error("Sort order must be a number"); return; }
    const res = await fetch(`/api/admin/deals/${deal.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sort_order: parsed }),
    });
    if (!res.ok) { toast.error("Could not update sort order"); return; }
    toast.success("Sort order updated");
    refresh();
  }

  async function remove(dealId: string) {
    if (!confirm("Remove this product from Today's Deals?")) return;
    const res = await fetch(`/api/admin/deals/${dealId}`, { method: "DELETE" });
    if (!res.ok) { toast.error("Could not remove deal"); return; }
    toast.success("Deal removed");
    refresh();
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Today&apos;s Deals</h1>
      <p className="text-sm text-muted mb-6">
        Curate the products shown in the homepage &quot;Today&apos;s Deals&quot; rail and deal highlight.
      </p>

      <div className="card p-4 flex flex-wrap gap-3 items-end mb-6">
        <div className="flex-1 min-w-[220px] relative" ref={searchRef}>
          <label className="block text-xs font-medium mb-1">Product</label>
          <input
            className="input-field"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setShowSuggestions(true); }}
            onFocus={() => setShowSuggestions(true)}
            placeholder="Search products by name…"
          />
          {showSuggestions && debouncedQuery.length >= 2 && suggestions.length > 0 && (
            <div className="absolute z-10 mt-1 w-full card p-1 max-h-72 overflow-y-auto">
              {suggestions.map((product) => (
                <button
                  key={product.id}
                  onClick={() => addDeal(product)}
                  className="w-full flex items-center gap-2 p-2 rounded-md hover:bg-surface text-left"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={resolveImageUrl(product.images?.[0]?.url ?? "")}
                    alt=""
                    className="w-10 h-10 object-cover rounded bg-surface shrink-0"
                  />
                  <span className="text-sm truncate">{decodeHtml(product.name)}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs font-medium mb-1">Label (optional)</label>
          <input className="input-field" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Flash Sale" />
        </div>
        <div className="w-24">
          <label className="block text-xs font-medium mb-1">Sort order</label>
          <input type="number" className="input-field" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} />
        </div>
      </div>

      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : deals.length === 0 ? (
        <div className="card p-10 text-center text-muted text-sm">No deals yet. Search for a product above to add one.</div>
      ) : (
        <div className="card divide-y divide-border overflow-hidden">
          {deals.map((deal) => (
            <div key={deal.id} className="flex items-center gap-4 p-4 flex-wrap">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={resolveImageUrl(deal.product?.images?.[0]?.url ?? "")}
                alt=""
                className="w-14 h-14 object-cover rounded-md bg-surface shrink-0"
              />
              <div className="min-w-0 flex-1">
                <p className="font-medium truncate">{deal.product ? decodeHtml(deal.product.name) : "(product removed)"}</p>
                <p className="text-xs text-muted truncate">{deal.label || "No label"}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <input
                  type="number"
                  className="input-field w-16 text-sm py-1.5"
                  value={sortDrafts[deal.id] ?? String(deal.sort_order)}
                  onChange={(e) => setSortDrafts((s) => ({ ...s, [deal.id]: e.target.value }))}
                />
                <button onClick={() => saveSortOrder(deal)} className="text-xs py-1.5 px-3 rounded-md border border-border hover:bg-surface">
                  Save
                </button>
                <button onClick={() => toggleActive(deal)} className="text-xs py-1.5 px-3 rounded-md border border-border hover:bg-surface">
                  {deal.is_active ? "Deactivate" : "Activate"}
                </button>
                <button onClick={() => remove(deal.id)} className="p-1.5 rounded-md border border-danger text-danger hover:bg-danger/5">
                  <Trash2 size={14} />
                </button>
              </div>
              {!deal.is_active && (
                <span className="text-[10px] bg-ink/10 text-muted px-2 py-0.5 rounded-full">inactive</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
