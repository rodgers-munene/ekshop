"use client";

import { useRef } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Product } from "@/types/interface";
import ProductCard from "@/components/ProductCard";

interface ProductRailProps {
  title: string;
  products: Product[];
  viewAllHref?: string;
}

export default function ProductRail({ title, products, viewAllHref }: ProductRailProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  function scroll(direction: -1 | 1) {
    scrollerRef.current?.scrollBy({ left: direction * 320, behavior: "smooth" });
  }

  if (products.length === 0) return null;

  return (
    <section className="px-4 md:px-6 py-4">
      <div className="card p-5">
        <div className="flex items-baseline justify-between mb-5">
          <h2 className="text-lg font-bold">{title}</h2>
          {viewAllHref && (
            <Link
              href={viewAllHref}
              className="text-sm text-amber hover:underline hover:underline-offset-2"
            >
              Shop all
            </Link>
          )}
        </div>

        <div className="relative group/rail">
          <div
            ref={scrollerRef}
            className="flex gap-3 overflow-x-auto scrollbar-hide scroll-smooth"
          >
            {products.map((product) => (
              <div key={product.id} className="w-36 sm:w-44 shrink-0">
                <ProductCard product={product} />
              </div>
            ))}
          </div>

          <button
            type="button"
            onClick={() => scroll(-1)}
            aria-label="Scroll left"
            className="hidden md:flex absolute -left-3 top-1/2 -translate-y-1/2 items-center justify-center w-9 h-9 rounded-full bg-white border border-border shadow-md opacity-0 group-hover/rail:opacity-100 transition-opacity hover:bg-navy hover:text-white hover:border-navy"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            type="button"
            onClick={() => scroll(1)}
            aria-label="Scroll right"
            className="hidden md:flex absolute -right-3 top-1/2 -translate-y-1/2 items-center justify-center w-9 h-9 rounded-full bg-white border border-border shadow-md opacity-0 group-hover/rail:opacity-100 transition-opacity hover:bg-navy hover:text-white hover:border-navy"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </div>
    </section>
  );
}
