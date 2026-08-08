import type { MetadataRoute } from "next";
import { Product, ShopSummary, ProductListResponse, PaginatedResponse } from "@/types/interface";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL!;
const API_URL = process.env.NEXT_PUBLIC_API_URL;
const PAGE_SIZE = 100;

async function fetchAllProducts(): Promise<Product[]> {
  const all: Product[] = [];
  let page = 1;

  while (true) {
    const res = await fetch(`${API_URL}/products/?page=${page}&limit=${PAGE_SIZE}`, {
      next: { revalidate: 3600 },
    })
      .then((r) => (r.ok ? (r.json() as Promise<ProductListResponse>) : null))
      .catch(() => null);

    if (!res || res.results.length === 0) break;
    all.push(...res.results);
    if (page * PAGE_SIZE >= res.total) break;
    page++;
  }

  return all;
}

async function fetchAllShops(): Promise<ShopSummary[]> {
  const all: ShopSummary[] = [];
  let page = 1;

  while (true) {
    const res = await fetch(`${API_URL}/shops/?page=${page}&limit=${PAGE_SIZE}`, {
      next: { revalidate: 3600 },
    })
      .then((r) => (r.ok ? (r.json() as Promise<PaginatedResponse<ShopSummary>>) : null))
      .catch(() => null);

    if (!res || res.results.length === 0) break;
    all.push(...res.results);
    if (page * PAGE_SIZE >= res.total) break;
    page++;
  }

  return all;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [products, shops] = await Promise.all([fetchAllProducts(), fetchAllShops()]);

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, changeFrequency: "daily", priority: 1 },
    { url: `${SITE_URL}/products`, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/blog`, changeFrequency: "weekly", priority: 0.5 },
    { url: `${SITE_URL}/about`, changeFrequency: "monthly", priority: 0.3 },
    { url: `${SITE_URL}/careers`, changeFrequency: "monthly", priority: 0.3 },
    { url: `${SITE_URL}/privacy`, changeFrequency: "yearly", priority: 0.1 },
    { url: `${SITE_URL}/terms`, changeFrequency: "yearly", priority: 0.1 },
    { url: `${SITE_URL}/refund-policy`, changeFrequency: "yearly", priority: 0.1 },
  ];

  const productRoutes: MetadataRoute.Sitemap = products.map((product) => ({
    url: `${SITE_URL}/products/${product.slug}`,
    lastModified: product.created_at,
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  const shopRoutes: MetadataRoute.Sitemap = shops.map((shop) => ({
    url: `${SITE_URL}/shops/${shop.slug}`,
    changeFrequency: "weekly",
    priority: 0.6,
  }));

  return [...staticRoutes, ...productRoutes, ...shopRoutes];
}
