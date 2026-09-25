import type { MetadataRoute } from "next";
import { Product, ShopSummary, ProductListResponse, PaginatedResponse } from "@/types/interface";
import { SITE_URL } from "@/lib/site";

// The sitemap hits the products/shops API to enumerate slugs. Generating it at
// build time makes deploys depend on the backend being reachable + fast from
// the build runner (a cold or slow API pushes past Next's prerender budget and
// fails the whole deploy), so the route is rendered on demand instead.
export const dynamic = "force-dynamic";

const API_URL = process.env.NEXT_PUBLIC_API_URL;
const PAGE_SIZE = 100;
const FETCH_TIMEOUT_MS = 15000;

async function safeFetch<T>(url: string): Promise<T | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, { signal: controller.signal, next: { revalidate: 3600 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

async function fetchAllProducts(): Promise<Product[]> {
  const all: Product[] = [];
  let page = 1;

  while (true) {
    const res = await safeFetch<ProductListResponse>(`${API_URL}/products/?page=${page}&limit=${PAGE_SIZE}`);
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
    const res = await safeFetch<PaginatedResponse<ShopSummary>>(`${API_URL}/shops/?page=${page}&limit=${PAGE_SIZE}`);
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
