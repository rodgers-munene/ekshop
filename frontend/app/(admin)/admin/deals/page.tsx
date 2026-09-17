"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { RotateCcw, Trash2 } from "lucide-react";
import { Promotion, Product, ProductListResponse } from "@/types/interface";
import { resolveImageUrl, decodeHtml } from "@/lib/utils";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

/**
 * Where a deal sits relative to today.
 *
 * Deals run midnight to midnight in Kenyan time and the backend stamps that
 * window on create, so the admin never picks a date. This only reads the window
 * back to say whether a deal is on today's list, already spent, or queued for a
 * later day.
 */
function dealDay(deal: Promotion): { text: string; tone: string; expired: boolean } {
  if (!deal.is_active) return { text: "Paused — not on the homepage", tone: "text-muted", expired: false };

  const now = Date.now();
  const ends = deal.ends_at ? new Date(deal.ends_at).getTime() : null;
  const starts = deal.starts_at ? new Date(deal.starts_at).getTime() : null;

  if (starts !== null && starts > now) {
    return { text: `Scheduled for ${new Date(starts).toLocaleDateString()}`, tone: "text-info", expired: false };
  }
  if (ends === null) return { text: "Runs until removed — no countdown shown", tone: "text-muted", expired: false };
  if (ends <= now) return { text: "Ran on an earlier day", tone: "text-muted", expired: true };

  const minutesLeft = Math.floor((ends - now) / 60_000);
  const hours = Math.floor(minutesLeft / 60);
  return {
    text: `Live today — ${hours > 0 ? `${hours}h ${minutesLeft % 60}m` : `${minutesLeft}m`} until midnight`,
    tone: "text-success",
    expired: false,
  };
}

export default function AdminDealsPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [label, setLabel] = useState("");
  const [sortOrder, setSortOrder] = useState("0");
  const [sortDrafts, setSortDrafts] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
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
    // The "until midnight" reading goes stale on its own; a slow refetch keeps
    // it roughly honest without the page needing its own clock.
    refetchInterval: 60_000,
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
    toast.success("Added to today's deals");
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

  async function runToday(deal: Promotion) {
    setBusyId(deal.id);
    const res = await fetch(`/api/admin/deals/${deal.id}/run-today`, { method: "POST" });
    setBusyId(null);
    if (!res.ok) { toast.error("Could not run this deal today"); return; }
    toast.success("Running again today");
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
    setSortDrafts((d) => { const next = { ...d }; delete next[deal.id]; return next; });
    refresh();
  }

  async function remove(dealId: string) {
    if (!confirm("Remove this product from the deals list?")) return;
    const res = await fetch(`/api/admin/deals/${dealId}`, { method: "DELETE" });
    if (!res.ok) { toast.error("Could not remove deal"); return; }
    toast.success("Deal removed");
    refresh();
  }

  // Today's list first, then whatever ran on earlier days and can be reused.
  const today = deals.filter((d) => !dealDay(d).expired);
  const earlier = deals.filter((d) => dealDay(d).expired);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Today&apos;s Deals</h1>
      <p className="text-sm text-muted mb-6 max-w-2xl">
        Deals run from midnight to midnight. Add the products you want featured today —
        the homepage countdown is the time left in the day, and the list clears itself at
        midnight, so there are no end dates to set.
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
        <>
          {today.length === 0 ? (
            <div className="card p-8 text-center text-sm">
              <p className="font-medium mb-1">Nothing is running today</p>
              <p className="text-muted">
                The Flash Deals section is hidden until you add a product, or run an earlier one again.
              </p>
            </div>
          ) : (
            <div className="card divide-y divide-border overflow-hidden">
              {today.map((deal) => (
                <DealRow
                  key={deal.id}
                  deal={deal}
                  sortDraft={sortDrafts[deal.id]}
                  busy={busyId === deal.id}
                  onSortChange={(v) => setSortDrafts((d) => ({ ...d, [deal.id]: v }))}
                  onSaveSort={() => saveSortOrder(deal)}
                  onToggle={() => toggleActive(deal)}
                  onRunToday={() => runToday(deal)}
                  onRemove={() => remove(deal.id)}
                />
              ))}
            </div>
          )}

          {earlier.length > 0 && (
            <>
              <h2 className="text-sm font-bold text-muted mt-8 mb-2">Earlier days</h2>
              <p className="text-xs text-muted mb-3">
                These aren&apos;t showing on the homepage. Run one again to put it back on today&apos;s list.
              </p>
              <div className="card divide-y divide-border overflow-hidden">
                {earlier.map((deal) => (
                  <DealRow
                    key={deal.id}
                    deal={deal}
                    sortDraft={sortDrafts[deal.id]}
                    busy={busyId === deal.id}
                    onSortChange={(v) => setSortDrafts((d) => ({ ...d, [deal.id]: v }))}
                    onSaveSort={() => saveSortOrder(deal)}
                    onToggle={() => toggleActive(deal)}
                    onRunToday={() => runToday(deal)}
                    onRemove={() => remove(deal.id)}
                  />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

function DealRow({
  deal,
  sortDraft,
  busy,
  onSortChange,
  onSaveSort,
  onToggle,
  onRunToday,
  onRemove,
}: {
  deal: Promotion;
  sortDraft?: string;
  busy: boolean;
  onSortChange: (value: string) => void;
  onSaveSort: () => void;
  onToggle: () => void;
  onRunToday: () => void;
  onRemove: () => void;
}) {
  const day = dealDay(deal);

  return (
    <div className="flex items-center gap-3 p-4 flex-wrap">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={resolveImageUrl(deal.product?.images?.[0]?.url ?? "")}
        alt=""
        className="w-14 h-14 object-cover rounded-md bg-surface shrink-0"
      />
      <div className="min-w-0 flex-1">
        <p className="font-medium truncate">{deal.product ? decodeHtml(deal.product.name) : "(product removed)"}</p>
        <p className="text-xs text-muted truncate">{deal.label || "No label"}</p>
        <p className={`text-xs mt-0.5 ${day.tone}`}>{day.text}</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {day.expired ? (
          <button
            onClick={onRunToday}
            disabled={busy}
            className="inline-flex items-center gap-1.5 text-xs py-1.5 px-3 rounded-md border border-amber text-amber hover:bg-amber/5 disabled:opacity-60 disabled:cursor-wait transition-all active:scale-95"
          >
            <RotateCcw size={13} className={busy ? "animate-spin" : ""} />
            {busy ? "Adding…" : "Run again today"}
          </button>
        ) : (
          <>
            <input
              type="number"
              className="input-field w-16 text-sm py-1.5"
              value={sortDraft ?? String(deal.sort_order)}
              onChange={(e) => onSortChange(e.target.value)}
            />
            <button
              onClick={onSaveSort}
              disabled={sortDraft === undefined}
              className="text-xs py-1.5 px-3 rounded-md border border-border hover:bg-surface disabled:opacity-40 disabled:hover:bg-transparent"
            >
              Save
            </button>
            <button onClick={onToggle} className="text-xs py-1.5 px-3 rounded-md border border-border hover:bg-surface">
              {deal.is_active ? "Deactivate" : "Activate"}
            </button>
          </>
        )}
        <button onClick={onRemove} aria-label="Remove deal" className="p-1.5 rounded-md border border-danger text-danger hover:bg-danger/5">
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}
