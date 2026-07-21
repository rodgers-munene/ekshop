"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useCartStore } from "@/store/cartStore";
import { Product } from "@/types/interface";

export default function AddToCart({ product }: { product: Product }) {
  const [quantity, setQuantity] = useState(1);
  const addItem = useCartStore((state) => state.addItem);

  function handleAdd() {
    addItem({
      product_id: product.id,
      product_name: product.name,
      product_slug: product.slug,
      product_image: product.images?.[0]?.url ?? "",
      shop_id: product.shop_id,
      shop_name: product.shop?.name ?? "",
      unit_price: parseFloat(product.price),
      quantity,
    });
    toast.success(`${product.name} added to cart`);
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

      {/* Add to cart */}
      <button
        onClick={handleAdd}
        disabled={product.stock_qty === 0}
        className="btn-accent w-fit px-8 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {product.stock_qty === 0 ? "Out of Stock" : "Add to Cart"}
      </button>
    </div>
  );
}
