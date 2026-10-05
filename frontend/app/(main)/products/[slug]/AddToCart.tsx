"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { CartItem, useCartStore } from "@/store/cartStore";
import { Product } from "@/types/interface";
import { trackEvent } from "@/lib/track";

export default function AddToCart({ product }: { product: Product }) {
  const [quantity, setQuantity] = useState(1);
  const router = useRouter();
  const addItem = useCartStore((state) => state.addItem);
  const setBuyNowItem = useCartStore((state) => state.setBuyNowItem);
  const outOfStock = product.stock_qty === 0;

  function toCartItem(): CartItem {
    return {
      product_id: product.id,
      product_name: product.name,
      product_slug: product.slug,
      product_image: product.images?.[0]?.url ?? "",
      shop_id: product.shop_id,
      shop_name: product.shop?.name ?? "",
      unit_price: parseFloat(product.price),
      quantity,
    };
  }

  function handleAdd() {
    addItem(toCartItem());
    trackEvent("add_to_cart", { product_id: product.id, category_id: product.category_id ?? undefined });
    toast.success(`${product.name} added to cart`);
  }

  function handleBuyNow() {
    setBuyNowItem(toCartItem());
    trackEvent("add_to_cart", { product_id: product.id, category_id: product.category_id ?? undefined });
    router.push("/checkout?buy=now");
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Quantity selector */}
      <div className="flex items-center border border-border rounded-full w-fit overflow-hidden">
        <button
          onClick={() => setQuantity((q) => Math.max(1, q - 1))}
          className="px-4 py-2 text-lg hover:bg-surface transition-colors"
        >
          −
        </button>
        <span className="px-5 py-2 text-sm font-medium border-x border-border min-w-[3rem] text-center">
          {quantity}
        </span>
        <button
          onClick={() => setQuantity((q) => Math.min(product.stock_qty, q + 1))}
          className="px-4 py-2 text-lg hover:bg-surface transition-colors"
        >
          +
        </button>
      </div>

      {outOfStock ? (
        <button disabled className="btn-accent w-fit px-8 opacity-40 cursor-not-allowed">
          Out of Stock
        </button>
      ) : (
        <div className="flex flex-wrap gap-3">
          <button onClick={handleBuyNow} className="btn-accent px-8">
            Buy Now
          </button>
          <button onClick={handleAdd} className="btn-outline px-8">
            Add to Cart
          </button>
        </div>
      )}
    </div>
  );
}
