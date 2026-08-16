"use client";

import { useEffect } from "react";
import { trackEvent } from "@/lib/track";

export default function ViewTracker({ productId, categoryId }: { productId: string; categoryId?: string | null }) {
  useEffect(() => {
    trackEvent("view", { product_id: productId, category_id: categoryId ?? undefined });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  return null;
}
