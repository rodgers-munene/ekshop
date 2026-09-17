import Link from "next/link";
import { Plus } from "lucide-react";
import { serverFetch } from "@/lib/server-api";
import { ProductListResponse } from "@/types/interface";
import { formatKES, resolveImageUrl, decodeHtml } from "@/lib/utils";

const FILTERS = [
  { key: "", label: "All" },
  { key: "active", label: "Live" },
  { key: "draft", label: "Drafts" },
  { key: "paused", label: "Paused" },
] as const;

const STATUS_STYLES: Record<string, string> = {
  active: "bg-success/10 text-success",
  draft: "bg-amber/15 text-amber",
  paused: "bg-surface text-muted",
};

export default async function DashboardProductsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const { status } = await searchParams;
  const active = FILTERS.some((f) => f.key === status) ? (status ?? "") : "";

  // `/shops/me/products` rather than the public `/shops/{slug}/products`: the
  // public one only ever returns published products on an already-verified
  // shop, so a seller's own drafts never appeared here.
  const query = active ? `?status=${active}&limit=100` : "?limit=100";
  const productsRes = await serverFetch<ProductListResponse>(`/shops/me/products${query}`).catch(() => null);
  const products = productsRes?.results ?? [];

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-4">
        <h1 className="text-2xl font-bold">Products</h1>
        <Link href="/dashboard/products/new" className="btn-accent text-sm py-2! px-4!">
          <Plus size={16} /> Add product
        </Link>
      </div>

      <div className="flex gap-2 mb-6 overflow-x-auto scrollbar-hide">
        {FILTERS.map((f) => (
          <Link
            key={f.key}
            href={f.key ? `/dashboard/products?status=${f.key}` : "/dashboard/products"}
            className={`px-3 py-1.5 rounded-full text-xs font-medium shrink-0 transition-colors ${
              active === f.key ? "bg-navy text-white" : "bg-surface text-muted hover:bg-ink/10"
            }`}
          >
            {f.label}
          </Link>
        ))}
      </div>

      {products.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-20 text-center px-6">
          <p className="font-bold mb-2">
            {active === "draft" ? "No drafts" : active ? `Nothing ${active === "active" ? "live" : active}` : "No products yet"}
          </p>
          <p className="text-muted text-sm mb-6">
            {active ? "Try another tab to see the rest of your products." : "List your first product to start selling."}
          </p>
          <Link href="/dashboard/products/new" className="btn-accent">Add product</Link>
        </div>
      ) : (
        <>
          {/* Cards on a phone, table from tablet up — the table used to scroll
              sideways on the screens most sellers actually use. */}
          <div className="card divide-y divide-border md:hidden">
            {products.map((product) => (
              <Link
                key={product.id}
                href={`/dashboard/products/${product.slug}/edit`}
                className="flex items-center gap-3 p-3 active:bg-surface"
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
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full capitalize shrink-0 ${STATUS_STYLES[product.status] ?? "bg-surface"}`}>
                  {product.status === "active" ? "Live" : product.status}
                </span>
              </Link>
            ))}
          </div>

          <div className="card overflow-hidden hidden md:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="px-4 py-3 font-medium">Product</th>
                  <th className="px-4 py-3 font-medium">Price</th>
                  <th className="px-4 py-3 font-medium">Stock</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {products.map((product) => (
                  <tr key={product.id}>
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
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[product.status] ?? "bg-surface"}`}>
                        {product.status === "active" ? "Live" : product.status}
                      </span>
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
        </>
      )}
    </div>
  );
}
