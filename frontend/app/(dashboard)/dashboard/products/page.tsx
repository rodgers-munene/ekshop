import Link from "next/link";
import { ChevronLeft, ChevronRight, Plus, Search, Upload } from "lucide-react";
import { serverFetch } from "@/lib/server-api";
import { ProductListResponse } from "@/types/interface";
import ProductBulkList from "@/components/dashboard/ProductBulkList";

const FILTERS = [
  { key: "", label: "All" },
  { key: "active", label: "Live" },
  { key: "draft", label: "Drafts" },
  { key: "paused", label: "Inactive" },
] as const;

// The seller endpoint caps `limit` at 100; 50 keeps the page light on a phone,
// which matters now that a single import can leave thousands of drafts here.
const PER_PAGE = 50;

/** Rebuilds the current URL with one thing changed, so the filters compose
    instead of resetting each other. */
function href(
  current: { status: string; stock: string; q: string; page: number },
  patch: Partial<{ status: string; stock: string; q: string; page: number }>,
) {
  const next = { ...current, ...patch };
  const params = new URLSearchParams();
  if (next.status) params.set("status", next.status);
  if (next.stock) params.set("stock", next.stock);
  if (next.q) params.set("q", next.q);
  // page is reset by every caller that changes a filter, so this only survives
  // where it was asked for.
  if (next.page > 1) params.set("page", String(next.page));
  const query = params.toString();
  return query ? `/dashboard/products?${query}` : "/dashboard/products";
}

export default async function DashboardProductsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; stock?: string; q?: string; page?: string }>;
}) {
  const sp = await searchParams;
  const status = FILTERS.some((f) => f.key === sp.status) ? (sp.status ?? "") : "";
  const stock = sp.stock === "in" || sp.stock === "out" ? sp.stock : "";
  const q = (sp.q ?? "").trim();
  const page = Math.max(1, Number(sp.page) || 1);
  const current = { status, stock, q, page };

  // `/shops/me/products` rather than the public `/shops/{slug}/products`: the
  // public one only ever returns published products on an already-verified
  // shop, so a seller's own drafts never appeared here.
  const params = new URLSearchParams({ limit: String(PER_PAGE), page: String(page) });
  if (status) params.set("status", status);
  if (stock) params.set("in_stock", stock === "in" ? "true" : "false");
  if (q) params.set("q", q);

  const productsRes = await serverFetch<ProductListResponse>(
    `/shops/me/products?${params.toString()}`,
  ).catch(() => null);
  const products = productsRes?.results ?? [];
  const total = productsRes?.total ?? 0;
  const lastPage = Math.max(1, Math.ceil(total / PER_PAGE));
  const filtered = Boolean(status || stock || q);

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-4">
        <h1 className="text-2xl font-bold">Products</h1>
        <div className="flex items-center gap-2">
          <Link href="/dashboard/products/import" className="btn-outline text-sm py-2! px-3! md:px-4!">
            <Upload size={16} /> <span className="hidden sm:inline">Import</span>
          </Link>
          <Link href="/dashboard/products/new" className="btn-accent text-sm py-2! px-3! md:px-4!">
            <Plus size={16} /> <span className="hidden sm:inline">Add product</span>
          </Link>
        </div>
      </div>

      {/* A plain GET form, so searching stays a normal navigation and this page
          stays a server component. */}
      <form action="/dashboard/products" method="get" className="flex gap-2 mb-3">
        {status && <input type="hidden" name="status" value={status} />}
        {stock && <input type="hidden" name="stock" value={stock} />}
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
          <input
            type="search"
            name="q"
            defaultValue={q}
            placeholder="Search your products by name"
            className="input-field pl-9!"
          />
        </div>
        <button type="submit" className="btn-navy text-sm py-2! px-4!">Search</button>
      </form>

      <div className="flex gap-2 mb-6 overflow-x-auto scrollbar-hide">
        {FILTERS.map((f) => (
          <Link
            key={f.key}
            href={href(current, { status: f.key, page: 1 })}
            className={`px-3 py-1.5 rounded-full text-xs font-medium shrink-0 transition-colors ${
              status === f.key ? "bg-navy text-white" : "bg-surface text-muted hover:bg-ink/10"
            }`}
          >
            {f.label}
          </Link>
        ))}
        <span className="w-px bg-border shrink-0 mx-1" aria-hidden />
        {/* Reviewing an import means working through what's actually sellable
            first: a stock export lands thousands of rows, most of them at zero. */}
        <Link
          href={href(current, { stock: stock === "in" ? "" : "in", page: 1 })}
          className={`px-3 py-1.5 rounded-full text-xs font-medium shrink-0 transition-colors ${
            stock === "in" ? "bg-navy text-white" : "bg-surface text-muted hover:bg-ink/10"
          }`}
        >
          In stock
        </Link>
        <Link
          href={href(current, { stock: stock === "out" ? "" : "out", page: 1 })}
          className={`px-3 py-1.5 rounded-full text-xs font-medium shrink-0 transition-colors ${
            stock === "out" ? "bg-navy text-white" : "bg-surface text-muted hover:bg-ink/10"
          }`}
        >
          Out of stock
        </Link>
      </div>

      {products.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-20 text-center px-6">
          <p className="font-bold mb-2">
            {filtered ? "Nothing matches those filters" : "No products yet"}
          </p>
          <p className="text-muted text-sm mb-6">
            {filtered
              ? "Clear a filter or try a different search to see the rest of your products."
              : "List your first product, or import a whole spreadsheet at once."}
          </p>
          {filtered ? (
            <Link href="/dashboard/products" className="btn-outline">Clear filters</Link>
          ) : (
            <div className="flex flex-wrap gap-2 justify-center">
              <Link href="/dashboard/products/new" className="btn-accent">Add product</Link>
              <Link href="/dashboard/products/import" className="btn-outline">Import a spreadsheet</Link>
            </div>
          )}
        </div>
      ) : (
        <>
          <ProductBulkList
            products={products}
            total={total}
            filter={{
              status: status || undefined,
              in_stock: stock ? stock === "in" : undefined,
              q: q || undefined,
            }}
          />

          <div className="flex items-center justify-between gap-3 mt-4">
            <p className="text-xs text-muted tabular-nums">
              {((page - 1) * PER_PAGE + 1).toLocaleString()}–
              {Math.min(page * PER_PAGE, total).toLocaleString()} of {total.toLocaleString()}
            </p>
            {lastPage > 1 && (
              <div className="flex items-center gap-2">
                {page > 1 ? (
                  <Link href={href(current, { page: page - 1 })} className="btn-outline text-sm py-1.5! px-3!">
                    <ChevronLeft size={15} /> Back
                  </Link>
                ) : (
                  <span className="btn-outline text-sm py-1.5! px-3! opacity-40 pointer-events-none">
                    <ChevronLeft size={15} /> Back
                  </span>
                )}
                <span className="text-xs text-muted tabular-nums">
                  {page} / {lastPage}
                </span>
                {page < lastPage ? (
                  <Link href={href(current, { page: page + 1 })} className="btn-outline text-sm py-1.5! px-3!">
                    Next <ChevronRight size={15} />
                  </Link>
                ) : (
                  <span className="btn-outline text-sm py-1.5! px-3! opacity-40 pointer-events-none">
                    Next <ChevronRight size={15} />
                  </span>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
