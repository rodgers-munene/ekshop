"use client";

import { Product } from "@/types/interface";
import ProductCard from "@/components/ProductCard";
import CardRail from "@/components/CardRail";

interface ProductRailProps {
  title: string;
  products: Product[];
  viewAllHref?: string;
}

export default function ProductRail({ title, products, viewAllHref }: ProductRailProps) {
  if (products.length === 0) return null;

  return (
    <CardRail title={title} viewAllHref={viewAllHref}>
      {products.map((product) => (
        <div key={product.id} className="w-36 sm:w-44 shrink-0">
          <ProductCard product={product} />
        </div>
      ))}
    </CardRail>
  );
}
