import Link from "next/link";
import { notFound } from "next/navigation";
import { serverFetch } from "@/lib/server-api";
import { Product } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import AddToCart from "./AddToCart";
import ProductCard from "@/components/ProductCard";
import ProductImageGallery from "./ProductImageGallery";

function decodeHtml(str: string): string {
  return str
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

interface Props {
  params: Promise<{ slug: string }>;
}

export default async function ProductDetailPage({ params }: Props) {
  const { slug } = await params;

  const product = await serverFetch<Product>(`/products/${slug}`)
    .catch(() => null);

  if (!product) notFound();

  // Fetch related products from same category
  const related = await serverFetch<{ results: Product[] }>(
    `/products/?limit=4&category_id=${product.category_id ?? ""}`
  ).catch(() => ({ results: [] }));

  const relatedProducts = related.results.filter((p) => p.id !== product.id).slice(0, 4);

  return (
    <div className="w-full mx-auto px-4 md:px-6 py-4">

      {/* Breadcrumb */}
      <div className="py-3 text-xs text-muted flex gap-2">
        <Link href="/" className="hover:text-amber">Home</Link>
        <span>/</span>
        <Link href="/products" className="hover:text-amber">Products</Link>
        <span>/</span>
        <span className="text-ink truncate max-w-50">{decodeHtml(product.name)}</span>
      </div>

      {/* Main product section */}
      <div className="card grid grid-cols-1 md:grid-cols-2 gap-0 md:items-start overflow-hidden">

        {/* Images — sticky on desktop */}
        <div className="border-b md:border-b-0 md:border-r border-border md:sticky md:top-20">
          <ProductImageGallery
            images={product.images ?? []}
            productName={product.name}
          />
        </div>

        {/* Product info */}
        <div className="p-6 md:p-10 flex flex-col gap-5">

          {/* Shop */}
          {product.shop && (
            <Link
              href={`/shops/${product.shop.slug}`}
              className="text-xs text-muted hover:text-amber transition-colors"
            >
              {decodeHtml(product.shop.name)}
              {product.shop.is_verified && (
                <span className="ml-1 text-amber">✓</span>
              )}
            </Link>
          )}

          {/* Name */}
          <h1 className="text-3xl md:text-4xl font-extrabold leading-tight">
            {decodeHtml(product.name)}
          </h1>

          {/* Price */}
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-bold text-ink">
              {formatKES(product.price)}
            </span>
            {product.compare_price &&
              parseFloat(product.compare_price) > parseFloat(product.price) && (
                <span className="text-muted line-through text-sm">
                  {formatKES(product.compare_price)}
                </span>
              )}
          </div>

          {/* Stock status */}
          <p className={`text-sm font-medium ${product.stock_qty > 0 ? "text-emerald-600" : "text-danger"}`}>
            {product.stock_qty > 0 ? `${product.stock_qty} in stock` : "Out of stock"}
          </p>

          {/* Description */}
          {product.description && (
            <p className="text-sm text-muted leading-relaxed border-t border-border pt-4">
              {product.description}
            </p>
          )}

          {/* Add to cart */}
          <div className="border-t border-border pt-4">
            <AddToCart product={product} />
          </div>

          {/* Tags */}
          {product.tags && product.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-2">
              {product.tags.map((tag) => (
                <span key={tag} className="text-xs px-2 py-1 bg-surface text-muted rounded-full">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Related products */}
      {relatedProducts.length > 0 && (
        <div className="py-8">
          <h2 className="text-xl font-bold mb-5">You may also like</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {relatedProducts.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </div>
      )}

    </div>
  );
}
