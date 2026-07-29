import { notFound } from "next/navigation";
import { BadgeCheck, MapPin, Star } from "lucide-react";
import { serverFetch } from "@/lib/server-api";
import { resolveImageUrl, decodeHtml } from "@/lib/utils";
import { Shop, ProductListResponse } from "@/types/interface";
import ProductCard from "@/components/ProductCard";
import MessageSellerButton from "./MessageSellerButton";

interface Props {
  params: Promise<{ slug: string }>;
}

export default async function ShopPage({ params }: Props) {
  const { slug } = await params;

  const [shop, productsRes] = await Promise.all([
    serverFetch<Shop>(`/shops/${slug}`).catch(() => null),
    serverFetch<ProductListResponse>(`/shops/${slug}/products?limit=24`).catch(() => null),
  ]);

  if (!shop) notFound();

  const products = productsRes?.results ?? [];

  return (
    <div className="w-full">

      {/* ── Shop header ──────────────────────────────────────── */}
      <section className="relative h-48 md:h-56 overflow-hidden">
        {shop.banner_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={resolveImageUrl(shop.banner_url)}
            alt=""
            className="absolute inset-0 w-full h-full object-cover"
          />
        ) : (
          <div className="absolute inset-0 bg-gradient-to-br from-navy via-navy-light to-navy overflow-hidden">
            <div
              className="absolute inset-0 opacity-[0.15]"
              style={{
                backgroundImage: "radial-gradient(rgba(255,255,255,0.7) 1px, transparent 1px)",
                backgroundSize: "22px 22px",
              }}
            />
            <div className="absolute -top-12 -right-12 w-64 h-64 rounded-full bg-amber/20 blur-3xl" />
            <div className="absolute -bottom-20 left-1/4 w-72 h-72 rounded-full bg-info/10 blur-3xl" />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-navy/90 via-navy/30 to-transparent" />

        <div className="relative h-full flex items-end px-6 md:px-12 pb-6 gap-4">
          <div className="w-16 h-16 rounded-full bg-white border-2 border-white overflow-hidden shrink-0 flex items-center justify-center shadow-sm">
            {shop.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={resolveImageUrl(shop.logo_url)}
                alt={decodeHtml(shop.name)}
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="text-2xl font-bold text-ink">
                {decodeHtml(shop.name).charAt(0)}
              </span>
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-white">{decodeHtml(shop.name)}</h1>
              {shop.is_verified && <BadgeCheck size={18} className="text-amber" />}
            </div>
            <div className="flex items-center gap-3 mt-1 text-white/80 text-xs">
              {parseFloat(shop.rating_avg) > 0 && (
                <span className="flex items-center gap-1">
                  <Star size={12} className="fill-current" />
                  {parseFloat(shop.rating_avg).toFixed(1)} ({shop.rating_count})
                </span>
              )}
              {shop.county && (
                <span className="flex items-center gap-1">
                  <MapPin size={12} />
                  {shop.county}
                </span>
              )}
            </div>
          </div>
        </div>
      </section>

      <div className="px-6 md:px-12 py-5 border-b border-border flex items-center justify-between gap-4 flex-wrap">
        {shop.description ? (
          <p className="text-sm text-muted max-w-2xl">{shop.description}</p>
        ) : <span />}
        <MessageSellerButton shopId={shop.id} />
      </div>

      {/* ── Products ─────────────────────────────────────────── */}
      <div className="px-4 md:px-6 py-8">
        <div className="card p-5">
          <h2 className="text-lg font-bold mb-5">Products from {decodeHtml(shop.name)}</h2>
          {products.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {products.map((product) => (
                <ProductCard key={product.id} product={product} />
              ))}
            </div>
          ) : (
            <p className="text-muted text-sm">This shop hasn&apos;t listed any products yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
