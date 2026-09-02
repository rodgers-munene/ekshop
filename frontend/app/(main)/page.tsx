import Link from "next/link";
import { cookies } from "next/headers";
import {
  Smartphone,
  Truck,
  ShieldCheck,
  RotateCcw,
  BadgeCheck,
  Star,
} from "lucide-react";
import { serverFetch } from "@/lib/server-api";
import { resolveImageUrl, decodeHtml, seededShuffle, todaysSeed } from "@/lib/utils";
import { Product, Category, ProductListResponse, PaginatedResponse, ShopSummary, HeroSlide, Promotion } from "@/types/interface";
import ProductRail from "@/components/ProductRail";
import HeroSlideshow from "@/components/HeroSlideshow";
import DealsCardSlideshow from "@/components/DealsCardSlideshow";

export default async function HomePage() {
  const cookieStore = await cookies();
  const isLoggedIn = Boolean(cookieStore.get("ekshop_token")?.value);

  const [trending, categories, newArrivalsRes, heroSlides, featuredShopsRes, curatedDeals, activityProducts] = await Promise.all([
    serverFetch<Product[]>("/recommendations/trending?limit=20").catch(() => []),
    serverFetch<Category[]>("/categories/").catch(() => []),
    serverFetch<ProductListResponse>("/products/?limit=8").catch(() => null),
    serverFetch<HeroSlide[]>("/hero-slides").catch(() => []),
    serverFetch<PaginatedResponse<ShopSummary>>("/shops/?featured=true&limit=6").catch(() => null),
    serverFetch<Promotion[]>("/deals/?limit=8").catch(() => []),
    // Personalized picks (weighted by this buyer's views/carts/purchases and, when
    // known, boosted toward their county) — only worth fetching once logged in.
    isLoggedIn ? serverFetch<Product[]>("/recommendations?limit=12").catch(() => []) : Promise.resolve([]),
  ]);

  const featuredProduct = trending[0] ?? null;
  const trendingRail = trending.slice(1, 9);
  const dealProducts = curatedDeals.length > 0
    ? (curatedDeals.map((d) => d.product).filter((p): p is Product => Boolean(p)))
    : trending
        .filter(
          (p) => p.compare_price && parseFloat(p.compare_price) > parseFloat(p.price)
        )
        .slice(0, 8);
  const newArrivals = newArrivalsRes?.results ?? [];
  const featuredShops = featuredShopsRes?.results ?? [];

  const categoryImages = new Map<string, string>();
  for (const product of [...trending, ...newArrivals]) {
    if (!product.category_id || categoryImages.has(product.category_id)) continue;
    const image = product.images?.find((i) => i.is_primary) ?? product.images?.[0];
    if (image) categoryImages.set(product.category_id, image.url);
  }

  const quickCategoriesA = categories.slice(0, 4);
  const quickCategoriesB = categories.length > 4 ? categories.slice(4, 8) : categories.slice(0, 4);
  const dealHighlight = dealProducts[0] ?? featuredProduct;
  const arrivalHighlight = newArrivals[0] ?? trending[1] ?? null;

  // Rotates which categories get a product rail once per day, and which
  // products within them, so the homepage doesn't show the same lineup daily.
  const dailySeed = todaysSeed();
  const candidateCategories = seededShuffle(categories, dailySeed).slice(0, 6);
  const candidateResults = await Promise.all(
    candidateCategories.map((category) =>
      serverFetch<ProductListResponse>(`/products/?category_slug=${category.slug}&limit=16`).catch(() => null)
    )
  );
  const categoryRails = candidateCategories
    .map((category, i) => {
      const results = candidateResults[i]?.results ?? [];
      if (results.length < 4) return null;
      return { category, products: seededShuffle(results, `${dailySeed}:${category.id}`).slice(0, 8) };
    })
    .filter((rail): rail is { category: Category; products: Product[] } => rail !== null)
    .slice(0, 4);

  return (
    <div className="w-full">

      {/* ── Full-bleed hero ─────────────────────────────────── */}
      <HeroSlideshow slides={heroSlides} fallbackImageUrl={featuredProduct?.images?.[0]?.url} />

      {/* ── Quick-link card row (overlaps hero) ──────────────── */}
      <section className="relative z-10 px-4 md:px-6 -mt-10 md:-mt-14 pb-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">

          {/* Card A: category quick grid */}
          {quickCategoriesA.length > 0 && (
            <div className="card p-4 flex flex-col">
              <h3 className="font-bold text-sm mb-3">Keep shopping for...</h3>
              <div className="grid grid-cols-2 gap-2 flex-1">
                {quickCategoriesA.map((category) => {
                  const img = categoryImages.get(category.id) ?? category.icon_url;
                  return (
                    <Link
                      key={category.id}
                      href={`/products?category=${category.slug}`}
                      className="flex flex-col gap-1 group"
                    >
                      <div className="aspect-square bg-surface rounded overflow-hidden">
                        {img ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={resolveImageUrl(img)}
                            alt=""
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                          />
                        ) : null}
                      </div>
                      <span className="text-[11px] text-muted truncate group-hover:text-amber">
                        {category.name}
                      </span>
                    </Link>
                  );
                })}
              </div>
              <Link href="/products" className="text-xs text-amber hover:underline mt-3">
                See more categories
              </Link>
            </div>
          )}

          {/* Card B: deal highlight */}
          {curatedDeals.length > 0 ? (
            <div className="card p-4 flex flex-col">
              <h3 className="font-bold text-sm mb-3">Today&apos;s Deals</h3>
              <DealsCardSlideshow deals={curatedDeals} />
              <Link href="/products" className="text-xs text-amber hover:underline mt-3">
                Shop all deals
              </Link>
            </div>
          ) : dealHighlight ? (
            <div className="card p-4 flex flex-col">
              <h3 className="font-bold text-sm mb-3">Today&apos;s Deals</h3>
              <Link href={`/products/${dealHighlight.slug}`} className="relative block flex-1 bg-surface rounded overflow-hidden min-h-[110px]">
                {dealHighlight.images?.[0] && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={resolveImageUrl(dealHighlight.images[0].url)}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                )}
                <span className="absolute top-2 left-2 bg-danger text-white text-[10px] font-bold px-2 py-1 rounded-full uppercase tracking-wide">
                  Top Deal
                </span>
              </Link>
              <Link href="/products" className="text-xs text-amber hover:underline mt-3">
                Shop all deals
              </Link>
            </div>
          ) : null}

          {/* Card C: second category quick grid */}
          {quickCategoriesB.length > 0 && (
            <div className="card p-4 flex flex-col">
              <h3 className="font-bold text-sm mb-3">Browse Categories</h3>
              <div className="grid grid-cols-2 gap-2 flex-1">
                {quickCategoriesB.map((category) => {
                  const img = categoryImages.get(category.id) ?? category.icon_url;
                  return (
                    <Link
                      key={category.id}
                      href={`/products?category=${category.slug}`}
                      className="flex flex-col gap-1 group"
                    >
                      <div className="aspect-square bg-surface rounded overflow-hidden">
                        {img ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={resolveImageUrl(img)}
                            alt=""
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                          />
                        ) : null}
                      </div>
                      <span className="text-[11px] text-muted truncate group-hover:text-amber">
                        {category.name}
                      </span>
                    </Link>
                  );
                })}
              </div>
              <Link href="/products" className="text-xs text-amber hover:underline mt-3">
                Explore all categories
              </Link>
            </div>
          )}

          {/* Card D: new arrivals highlight */}
          {arrivalHighlight && (
            <div className="card p-4 flex flex-col">
              <h3 className="font-bold text-sm mb-3">New Arrivals</h3>
              <Link href={`/products/${arrivalHighlight.slug}`} className="block flex-1 bg-surface rounded overflow-hidden min-h-[110px]">
                {arrivalHighlight.images?.[0] && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={resolveImageUrl(arrivalHighlight.images[0].url)}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                )}
              </Link>
              <Link href="/products" className="text-xs text-amber hover:underline mt-3">
                View new arrivals
              </Link>
            </div>
          )}

        </div>
      </section>

      {/* ── Trust badges ─────────────────────────────────────── */}
      <section className="px-4 md:px-6 py-2">
        <div className="card px-4 md:px-6 py-6 grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            { icon: Smartphone, label: "Pay with M-Pesa", desc: "Fast, secure checkout" },
            { icon: Truck, label: "Nationwide Delivery", desc: "We deliver across Kenya" },
            { icon: ShieldCheck, label: "Verified Sellers", desc: "Vetted for quality & trust" },
            { icon: RotateCcw, label: "Easy Returns", desc: "Shop with confidence" },
          ].map(({ icon: Icon, label, desc }) => (
            <div key={label} className="flex items-start gap-3">
              <Icon size={22} className="text-amber shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold leading-tight">{label}</p>
                <p className="text-xs text-muted mt-0.5">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Trending Best Sellers ─────────────────────────────── */}
      <ProductRail title="Trending Best Sellers" products={trendingRail} viewAllHref="/products" />

      {/* ── Featured shops ───────────────────────────────────── */}
      {featuredShops.length > 0 && (
        <section className="px-4 md:px-6 py-4">
          <div className="card p-5">
            <h2 className="text-lg font-bold mb-5">Featured Shops</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
              {featuredShops.map((shop) => (
                <Link
                  key={shop.id}
                  href={`/shops/${shop.slug}`}
                  className="group flex flex-col items-center gap-2 rounded-lg border border-border px-4 py-6 hover:border-amber hover:shadow-sm transition-all"
                >
                  <div className="w-14 h-14 rounded-full bg-surface flex items-center justify-center text-xl font-bold text-muted">
                    {decodeHtml(shop.name).charAt(0)}
                  </div>
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      <span className="font-semibold text-sm leading-tight">
                        {decodeHtml(shop.name)}
                      </span>
                      {shop.is_verified && (
                        <BadgeCheck size={14} className="text-amber shrink-0" />
                      )}
                    </div>
                    {parseFloat(shop.rating_avg) > 0 && (
                      <div className="flex items-center justify-center gap-1 mt-1 text-xs text-muted">
                        <Star size={11} className="fill-current text-amber" />
                        <span>
                          {parseFloat(shop.rating_avg).toFixed(1)} ({shop.rating_count})
                        </span>
                      </div>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── Seller promo banner ─────────────────────────────── */}
      <section className="px-4 md:px-6 py-4">
        <div className="rounded-xl bg-navy text-white px-6 md:px-10 py-10 flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <span className="inline-block text-[10px] uppercase tracking-widest font-semibold px-2 py-0.5 bg-amber text-ink rounded-full mb-2">
              Exclusive
            </span>
            <h2 className="text-2xl md:text-3xl font-extrabold mb-2">
              Turn your hustle into a shop.
            </h2>
            <p className="text-white/70 text-sm max-w-md">
              List your products, reach buyers across Kenya, and get paid via M-Pesa, no setup fees.
            </p>
          </div>
          <div className="shrink-0 flex gap-2 sm:gap-3">
            <Link href="/register" className="btn-accent px-4! py-2! text-xs sm:px-6! sm:py-2.5! sm:text-base">
              Start Selling →
            </Link>
            <Link href="/products" className="btn-outline-dark px-4! py-2! text-xs sm:px-6! sm:py-2.5! sm:text-base">
              Learn more
            </Link>
          </div>
        </div>
      </section>

      {/* ── Today's Deals ────────────────────────────────────── */}
      <ProductRail title="Today's Deals" products={dealProducts} viewAllHref="/products" />

      {/* ── Personalized picks, only once we have a buyer to personalize for ── */}
      {activityProducts.length > 0 && (
        <ProductRail title="Based on Your Activity" products={activityProducts} viewAllHref="/products" />
      )}

      {/* ── Shop by Category ─────────────────────────────────── */}
      {categories.length > 0 && (
        <section className="px-4 md:px-6 py-4">
          <div className="card p-5">
            <h2 className="text-lg font-bold mb-5">Shop by Category</h2>
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-4">
              {categories.slice(0, 6).map((category) => {
                const bgImage = categoryImages.get(category.id) ?? category.icon_url;
                return (
                  <Link
                    key={category.id}
                    href={`/products?category=${category.slug}`}
                    className="group flex flex-col gap-2"
                  >
                    <div className="aspect-square rounded-lg overflow-hidden bg-surface border border-border">
                      {bgImage ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={resolveImageUrl(bgImage)}
                          alt=""
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        />
                      ) : null}
                    </div>
                    <span className="text-sm font-medium text-center group-hover:text-amber transition-colors">
                      {category.name}
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* ── Category spotlights (rotate daily) ───────────────── */}
      {categoryRails.map(({ category, products }) => (
        <ProductRail
          key={category.id}
          title={category.name}
          products={products}
          viewAllHref={`/products?category=${category.slug}`}
        />
      ))}

      {/* ── New Arrivals ─────────────────────────────────────── */}
      <ProductRail title="New Arrivals" products={newArrivals} viewAllHref="/products" />

    </div>
  );
}
