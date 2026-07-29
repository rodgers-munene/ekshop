"use client";

import Link from "next/link";
import { useState } from "react";
import { Star } from "lucide-react";
import { Product } from "@/types/interface";
import { formatKES, resolveImageUrl, decodeHtml } from "@/lib/utils";

function ProductImage({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  const resolvedSrc = resolveImageUrl(src);

  if (failed || !resolvedSrc) {
    return (
      <div className="w-full h-full bg-surface flex flex-col items-center justify-center text-muted">
        <span className="text-3xl mb-1">🛍️</span>
        <span className="text-xs">No image</span>
      </div>
    );
  }

  return (
    <img
      src={resolvedSrc}
      alt={alt}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      className="w-full h-full object-contain p-3 group-hover:scale-105 transition-transform duration-300 will-change-transform"
    />
  );
}

export default function ProductCard({ product }: { product: Product }) {
  const primaryImage = product.images?.find((i) => i.is_primary) ?? product.images?.[0];
  const hasDiscount =
    product.compare_price &&
    parseFloat(product.compare_price) > parseFloat(product.price);
  const ratingAvg = product.rating_avg ? parseFloat(product.rating_avg) : 0;

  return (
    <Link
      href={`/products/${product.slug}`}
      className="group flex flex-col card overflow-hidden hover:shadow-md transition-shadow duration-200 min-w-0"
    >
      {/* Image */}
      <div className="relative w-full aspect-square overflow-hidden bg-white border-b border-border">
        <ProductImage
          src={primaryImage?.url ?? ""}
          alt={product.name}
        />

        {hasDiscount && (
          <span className="absolute top-2 left-2 bg-danger text-white text-[10px] font-bold px-2 py-1 rounded-full uppercase tracking-wide">
            Deal
          </span>
        )}
      </div>

      {/* Details */}
      <div className="p-3 flex flex-col gap-1 flex-1 min-w-0">
        {product.shop?.name && (
          <p className="text-xs text-muted truncate">{decodeHtml(product.shop.name)}</p>
        )}
        <h3 className="text-sm font-medium leading-tight line-clamp-2">
          {decodeHtml(product.name)}
        </h3>

        {ratingAvg > 0 && (
          <div className="flex items-center gap-1 text-xs text-muted">
            <div className="flex items-center text-amber">
              {Array.from({ length: 5 }).map((_, i) => (
                <Star
                  key={i}
                  size={12}
                  className={i < Math.round(ratingAvg) ? "fill-current" : "fill-none"}
                />
              ))}
            </div>
            <span>{(product.rating_count ?? 0).toLocaleString()}</span>
          </div>
        )}

        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0 mt-auto pt-2 min-w-0">
          <span className="text-ink font-bold text-base whitespace-nowrap">
            {formatKES(product.price)}
          </span>
          {hasDiscount && (
            <span className="text-muted text-xs line-through whitespace-nowrap">
              {formatKES(product.compare_price!)}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
