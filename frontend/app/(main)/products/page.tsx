import Link from "next/link";
import { serverFetch } from "@/lib/server-api";
import { Category, ProductListResponse } from "@/types/interface";
import ProductCard from "@/components/ProductCard";

interface Props {
  searchParams: Promise<{ category?: string; q?: string; county?: string; page?: string }>;
}

export default async function ProductsPage({ searchParams }: Props) {
  const { category, q, county, page } = await searchParams;
  const currentPage = parseInt(page ?? "1");

  const params = new URLSearchParams();
  if (category) params.set("category_slug", category);
  if (q) params.set("q", q);
  if (county) params.set("county", county);
  params.set("page", String(currentPage));
  params.set("limit", "20");

  const [data, categories] = await Promise.all([
    serverFetch<ProductListResponse>(`/products/?${params}`).catch((e) => { console.error("PRODUCTS ERROR:", e.message); return null; }),
    serverFetch<Category[]>("/categories/").catch((e) => { console.error("CATEGORIES ERROR:", e.message); return []; }),
  ]);

  const products = data?.results ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  return (
    <div className="w-full px-4 md:px-6 py-4">

      {/* ── Page header ────────────────────────────────────── */}
      <div className="card px-4 md:px-6 py-5 mb-4">
        <div className="flex items-baseline justify-between">
          <h1 className="text-2xl font-bold">
            {q ? `Results for "${q}"` : category ? category.replace(/-/g, " ") : "All Products"}
          </h1>
          <span className="text-sm text-muted">{total} products</span>
        </div>
        {county && (
          <div className="mt-2">
            <Link
              href={`/products?${new URLSearchParams({ ...(category ? { category } : {}), ...(q ? { q } : {}) })}`}
              className="inline-flex items-center gap-1.5 text-xs bg-surface border border-border rounded-full px-3 py-1 hover:border-amber transition-colors"
            >
              Location: {county} ✕
            </Link>
          </div>
        )}
      </div>

      <div className="flex gap-4">

        {/* ── Sidebar filters ─────────────────────────────── */}
        <aside className="hidden md:block w-56 shrink-0">
          <div className="card p-4 mb-4">
            <p className="text-xs font-medium uppercase tracking-widest text-muted mb-3">
              Location
            </p>
            <form action="/products" method="get" className="flex flex-col gap-2">
              {category && <input type="hidden" name="category" value={category} />}
              {q && <input type="hidden" name="q" value={q} />}
              <input
                type="text"
                name="county"
                defaultValue={county ?? ""}
                placeholder="e.g. Nairobi"
                className="input-field text-sm py-1.5"
              />
              <button type="submit" className="text-xs py-1.5 px-3 rounded-md border border-border hover:bg-surface transition-colors">
                Filter by county
              </button>
            </form>
          </div>

          <div className="card p-4">
            <p className="text-xs font-medium uppercase tracking-widest text-muted mb-3">
              Categories
            </p>
            <ul className="space-y-1">
              <li>
                <Link
                  href="/products"
                  className={`block text-sm py-1 hover:text-amber transition-colors ${!category ? "text-amber font-medium" : "text-ink"}`}
                >
                  All
                </Link>
              </li>
              {categories.map((cat) => (
                <li key={cat.id}>
                  <Link
                    href={`/products?category=${cat.slug}`}
                    className={`block text-sm py-1 hover:text-amber transition-colors ${category === cat.slug ? "text-amber font-medium" : "text-ink"}`}
                  >
                    {cat.name}
                  </Link>
                  {cat.children && cat.children.length > 0 && category === cat.slug && (
                    <ul className="ml-3 mt-1 space-y-1">
                      {cat.children.map((child) => (
                        <li key={child.id}>
                          <Link
                            href={`/products?category=${child.slug}`}
                            className="block text-xs py-0.5 text-muted hover:text-amber transition-colors"
                          >
                            {child.name}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </aside>

        {/* ── Product grid ────────────────────────────────── */}
        <div className="flex-1 min-w-0">
          {products.length > 0 ? (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                {products.map((product) => (
                  <ProductCard key={product.id} product={product} />
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-4 card py-6">
                  {currentPage > 1 && (
                    <Link
                      href={`/products?${new URLSearchParams({ ...(category ? { category } : {}), ...(q ? { q } : {}), ...(county ? { county } : {}), page: String(currentPage - 1) })}`}
                      className="px-4 py-2 rounded-full border border-border text-sm hover:bg-navy hover:text-white hover:border-navy transition-colors"
                    >
                      ← Prev
                    </Link>
                  )}
                  <span className="text-sm text-muted">
                    Page {currentPage} of {totalPages}
                  </span>
                  {currentPage < totalPages && (
                    <Link
                      href={`/products?${new URLSearchParams({ ...(category ? { category } : {}), ...(q ? { q } : {}), ...(county ? { county } : {}), page: String(currentPage + 1) })}`}
                      className="px-4 py-2 rounded-full border border-border text-sm hover:bg-navy hover:text-white hover:border-navy transition-colors"
                    >
                      Next →
                    </Link>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="card flex flex-col items-center justify-center py-24 text-center">
              <p className="text-2xl font-bold mb-2">No products found</p>
              <p className="text-muted text-sm mb-6">Try a different category or search term</p>
              <Link href="/products" className="btn-accent">
                Browse all products
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
