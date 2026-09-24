"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { BulkStatusResult, Product } from "@/types/interface";
import { formatKES, resolveImageUrl, decodeHtml } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  active: "bg-success/10 text-success",
  draft: "bg-amber/15 text-amber",
  paused: "bg-surface text-muted",
};

const STATUS_LABELS: Record<string, string> = {
  active: "Live",
  draft: "Draft",
  paused: "Inactive",
};

/** The filter that produced this page, so "select all matching" can be sent as
    a description instead of thousands of ids. */
export interface ProductFilter {
  status?: string;
  in_stock?: boolean;
  q?: string;
}

type Target = "active" | "paused" | "draft";

const ACTIONS: { target: Target; label: string; className: string }[] = [
  { target: "active", label: "Publish", className: "btn-accent" },
  { target: "paused", label: "Set inactive", className: "btn-outline" },
  { target: "draft", label: "Back to drafts", className: "btn-outline" },
];

function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={`text-[10px] md:text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ${
        STATUS_STYLES[status] ?? "bg-surface"
      }`}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

export default function ProductBulkList({
  products,
  total,
  filter,
}: {
  products: Product[];
  total: number;
  filter: ProductFilter;
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // "Everything matching the filter", not just the ids on screen.
  const [allMatching, setAllMatching] = useState(false);
  const [busy, setBusy] = useState<Target | null>(null);

  const pageIds = products.map((p) => p.id);
  // A new page of products makes the old selection meaningless — and acting on
  // ids that are no longer on screen is the kind of surprise that loses trust.
  // Keyed on the ids rather than the array, which arrives with a fresh identity
  // on every server render and would clear the selection mid-click. Adjusted
  // during render rather than in an effect, so the stale selection never reaches
  // the DOM and the extra pass costs nothing.
  const pageKey = pageIds.join(",");
  const [renderedKey, setRenderedKey] = useState(pageKey);
  if (renderedKey !== pageKey) {
    setRenderedKey(pageKey);
    setSelected(new Set());
    setAllMatching(false);
  }

  const allOnPage = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const count = allMatching ? total : selected.size;

  function toggle(id: string) {
    setAllMatching(false);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function togglePage() {
    setAllMatching(false);
    setSelected(allOnPage ? new Set() : new Set(pageIds));
  }

  async function apply(target: Target) {
    if (count === 0) return;
    setBusy(target);
    try {
      const res = await fetch("/api/dashboard/products/bulk-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          allMatching
            ? { status: target, filter }
            : { status: target, product_ids: [...selected] },
        ),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.detail ?? "Could not update those products");
        return;
      }

      const result = data as BulkStatusResult;
      // The plan cap can stop a publish short, and the API says so in `detail` —
      // surfacing that as a warning rather than a success is the whole point.
      if (result.skipped_over_limit > 0) {
        toast.warning(result.detail ?? `${result.skipped_over_limit} stayed as drafts`);
      } else if (result.updated === 0) {
        toast.info(result.detail ?? "Nothing to change");
      } else {
        toast.success(
          `${result.updated.toLocaleString()} ${result.updated === 1 ? "product" : "products"} ${
            target === "active" ? "published" : target === "paused" ? "set inactive" : "moved to drafts"
          }`,
        );
      }

      setSelected(new Set());
      setAllMatching(false);
      router.refresh();
    } catch {
      toast.error("Could not reach the server. Try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <div className="flex items-center gap-2.5 mb-3 px-1">
        <input
          type="checkbox"
          checked={allOnPage}
          onChange={togglePage}
          aria-label="Select every product on this page"
          className="accent-amber size-4"
        />
        <span className="text-xs text-muted">
          {count > 0 ? `${count.toLocaleString()} selected` : "Select all on this page"}
        </span>
        {allOnPage && !allMatching && total > products.length && (
          <button
            type="button"
            onClick={() => setAllMatching(true)}
            className="text-xs text-amber underline underline-offset-2"
          >
            Select all {total.toLocaleString()} matching
          </button>
        )}
        {allMatching && (
          <button
            type="button"
            onClick={() => {
              setAllMatching(false);
              setSelected(new Set());
            }}
            className="text-xs text-amber underline underline-offset-2"
          >
            Clear selection
          </button>
        )}
      </div>

      {/* Cards on a phone, table from tablet up — the table used to scroll
          sideways on the screens most sellers actually use. */}
      <div className="card divide-y divide-border md:hidden">
        {products.map((product) => (
          <div key={product.id} className="flex items-center gap-3 p-3">
            <input
              type="checkbox"
              checked={allMatching || selected.has(product.id)}
              onChange={() => toggle(product.id)}
              aria-label={`Select ${decodeHtml(product.name)}`}
              className="accent-amber size-4 shrink-0"
            />
            <Link
              href={`/dashboard/products/${product.slug}/edit`}
              className="flex items-center gap-3 min-w-0 flex-1 active:opacity-70"
            >
              <div className="w-14 h-14 rounded bg-surface overflow-hidden shrink-0">
                {product.images[0] && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={resolveImageUrl(product.images[0].url)} alt="" className="w-full h-full object-cover" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-sm truncate">{decodeHtml(product.name)}</p>
                <p className="text-xs text-muted mt-0.5">
                  {formatKES(product.price)} · {product.stock_qty} in stock
                </p>
              </div>
              <StatusPill status={product.status} />
            </Link>
          </div>
        ))}
      </div>

      <div className="card overflow-hidden hidden md:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted">
              <th className="pl-4 pr-2 py-3 w-4"></th>
              <th className="px-4 py-3 font-medium">Product</th>
              <th className="px-4 py-3 font-medium">Price</th>
              <th className="px-4 py-3 font-medium">Stock</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {products.map((product) => (
              <tr key={product.id} className={selected.has(product.id) || allMatching ? "bg-amber/5" : undefined}>
                <td className="pl-4 pr-2 py-3">
                  <input
                    type="checkbox"
                    checked={allMatching || selected.has(product.id)}
                    onChange={() => toggle(product.id)}
                    aria-label={`Select ${decodeHtml(product.name)}`}
                    className="accent-amber size-4"
                  />
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded bg-surface overflow-hidden shrink-0">
                      {product.images[0] && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={resolveImageUrl(product.images[0].url)}
                          alt=""
                          className="w-full h-full object-cover"
                        />
                      )}
                    </div>
                    <span className="font-medium">{decodeHtml(product.name)}</span>
                  </div>
                </td>
                <td className="px-4 py-3">{formatKES(product.price)}</td>
                <td className="px-4 py-3">{product.stock_qty}</td>
                <td className="px-4 py-3">
                  <StatusPill status={product.status} />
                </td>
                <td className="px-4 py-3 text-right">
                  <Link href={`/dashboard/products/${product.slug}/edit`} className="text-amber text-sm underline underline-offset-2">
                    Edit
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {count > 0 && (
        <div className="sticky bottom-4 mt-4 card p-3 flex flex-wrap items-center gap-2 shadow-lg">
          <span className="text-sm font-medium mr-auto">
            {count.toLocaleString()} selected
          </span>
          {ACTIONS.map((action) => (
            <button
              key={action.target}
              type="button"
              disabled={busy !== null}
              onClick={() => apply(action.target)}
              className={`${action.className} text-sm py-2! px-4! disabled:opacity-50`}
            >
              {busy === action.target && <Loader2 size={14} className="animate-spin" />}
              {action.label}
            </button>
          ))}
        </div>
      )}
    </>
  );
}
