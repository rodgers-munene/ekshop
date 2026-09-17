"use client";

import { useRef } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface CardRailProps {
  title: React.ReactNode;
  viewAllHref?: string;
  viewAllLabel?: string;
  /** Rendered in the header, between the title and the "shop all" link. */
  accessory?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * The shared homepage section shell: a card with a title row and a horizontally
 * scrolling track of fixed-width cards, with hover arrows on desktop. Every rail
 * on the homepage goes through this so the sections stay the same size and shape.
 */
export default function CardRail({
  title,
  viewAllHref,
  viewAllLabel = "Shop all",
  accessory,
  children,
}: CardRailProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  function scroll(direction: -1 | 1) {
    scrollerRef.current?.scrollBy({ left: direction * 320, behavior: "smooth" });
  }

  return (
    <section className="px-4 md:px-6 py-4">
      <div className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 mb-5">
          <h2 className="text-lg font-bold">{title}</h2>
          {accessory}
          {viewAllHref && (
            <Link
              href={viewAllHref}
              className="text-sm text-amber hover:underline hover:underline-offset-2 ml-auto"
            >
              {viewAllLabel}
            </Link>
          )}
        </div>

        <div className="relative group/rail">
          <div
            ref={scrollerRef}
            className="flex gap-3 overflow-x-auto scrollbar-hide scroll-smooth"
          >
            {children}
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
