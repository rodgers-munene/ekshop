import type { Metadata } from "next";
import Link from "next/link";
import { Star, ShieldCheck } from "lucide-react";
import { serverFetch } from "@/lib/server-api";
import { ProductListResponse } from "@/types/interface";
import ProductCard from "@/components/ProductCard";

interface Props {
  searchParams: Promise<{ page?: string }>;
}

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: "Top Rated Products",
    description:
      "Shop the highest-rated products from verified sellers across Kenya, as reviewed by real buyers.",
  };
}

export default async function RatingsPage({ searchParams }: Props) {
  const { page } = await searchParams;
  const currentPage = parseInt(page ?? "1", 10);

  const data = await serverFetch<ProductListResponse>(
    `/products/?sort=rating&page=${currentPage}&limit=24`,
  ).catch(() => null);

  const products = data?.results ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 24));

  return (
    <div className="w-full px-4 md:px-6 py-4">
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="rounded-xl bg-navy text-white px-6 md:px-10 py-8 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-amber text-ink shrink-0">
            <Star size={24} className="fill-current" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl md:text-3xl font-extrabold">Top Rated</h1>
            <p className="text-white/70 text-sm mt-1">
              The best of Ekshop&mdash;products rated highest by real verified buyers.
            </p>
          </div>
          <span className="text-sm text-white/60 shrink-0">
            {total.toLocaleString()} products
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 mt-5">
          {[
            { icon: ShieldCheck, label: "Rated by verified buyers" },
            { icon: Star, label: "Sorted by average rating" },
          ].map(({ icon: Icon, label }) => (
            <span
              key={label}
              className="inline-flex items-center gap-1.5 text-xs bg-white/10 rounded-full px-3 py-1.5"
            >
              <Icon size={13} className="text-amber" />
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* ── Product grid ───────────────────────────────────── */}
      {products.length > 0 ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {products.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4 card py-6">
              {currentPage > 1 && (
                <Link
                  href={`/ratings?${new URLSearchParams({ page: String(currentPage - 1) })}`}
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
                  href={`/ratings?${new URLSearchParams({ page: String(currentPage + 1) })}`}
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
          <p className="text-2xl font-bold mb-2">No reviewed products yet</p>
          <p className="text-muted text-sm mb-6">
            Check back soon—top-rated picks will appear here.
          </p>
          <Link href="/products" className="btn-accent">
            Browse all products
          </Link>
        </div>
      )}
    </div>
  );
}