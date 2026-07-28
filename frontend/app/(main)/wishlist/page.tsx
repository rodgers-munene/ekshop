"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { X } from "lucide-react";
import { toast } from "sonner";
import { Product } from "@/types/interface";
import { useCartStore } from "@/store/cartStore";
import ProductCard from "@/components/ProductCard";

export default function WishlistPage() {
  const queryClient = useQueryClient();
  const addItem = useCartStore((s) => s.addItem);

  const { data: items = [], isPending: loading } = useQuery({
    queryKey: ["wishlist"],
    queryFn: () =>
      fetch("/api/wishlist")
        .then((r) => r.json())
        .then((data) => (Array.isArray(data) ? (data as Product[]) : [])),
  });

  async function removeFromWishlist(productId: string) {
    await fetch(`/api/wishlist/${productId}`, { method: "DELETE" });
    queryClient.setQueryData<Product[]>(["wishlist"], (prev) => (prev ?? []).filter((p) => p.id !== productId));
    toast.success("Removed from wishlist");
  }

  function addToCart(product: Product) {
    const img = product.images?.find((i) => i.is_primary) ?? product.images?.[0];
    addItem({
      product_id: product.id,
      product_name: product.name,
      product_slug: product.slug,
      product_image: img?.url ?? "",
      shop_id: product.shop_id,
      shop_name: product.shop?.name ?? "",
      unit_price: parseFloat(product.price),
      quantity: 1,
    });
    toast.success(`${product.name} added to cart`);
  }

  if (loading) {
    return (
      <div className="w-full max-w-5xl mx-auto px-4 md:px-8 py-8">
        <div className="h-7 w-32 bg-ink/10 rounded animate-pulse mb-6" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="card overflow-hidden">
              <div className="aspect-square bg-surface animate-pulse" />
              <div className="p-3 space-y-2">
                <div className="h-3 bg-ink/10 rounded animate-pulse" />
                <div className="h-4 w-2/3 bg-ink/10 rounded animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-5xl mx-auto px-4 md:px-8 py-8">
      <h1 className="text-2xl font-bold mb-6 border-b border-border pb-4">
        Wishlist {items.length > 0 && <span className="text-muted font-normal text-lg">({items.length})</span>}
      </h1>

      {items.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-24 text-center">
          <p className="text-2xl font-extrabold mb-2">Your wishlist is empty</p>
          <p className="text-muted text-sm mb-6">Save products you love by clicking the heart icon.</p>
          <Link href="/products" className="btn-accent">
            Browse Products
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {items.map((product) => (
            <div key={product.id} className="relative flex flex-col gap-2">
              <button
                onClick={() => removeFromWishlist(product.id)}
                title="Remove from wishlist"
                className="absolute top-2 right-2 z-10 w-7 h-7 flex items-center justify-center rounded-full bg-white/90 border border-border text-muted hover:text-danger hover:border-danger transition-colors shadow-sm"
              >
                <X size={14} />
              </button>
              <ProductCard product={product} />
              <button
                onClick={() => addToCart(product)}
                className="btn-accent w-full text-xs py-2"
              >
                Add to Cart
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
