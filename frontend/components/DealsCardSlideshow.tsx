"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Promotion } from "@/types/interface";
import { resolveImageUrl } from "@/lib/utils";

const ROTATE_MS = 4000;

interface DealsCardSlideshowProps {
  deals: Promotion[];
}

export default function DealsCardSlideshow({ deals }: DealsCardSlideshowProps) {
  const [index, setIndex] = useState(0);
  const slides = deals.filter((d) => d.product?.images?.[0]);

  useEffect(() => {
    if (slides.length <= 1) return;
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % slides.length);
    }, ROTATE_MS);
    return () => clearInterval(id);
  }, [slides.length]);

  if (slides.length === 0) return null;
  const active = slides[index];

  return (
    <Link
      href={`/products/${active.product!.slug}`}
      className="relative block flex-1 bg-surface rounded overflow-hidden min-h-[110px]"
    >
      {slides.map((s, i) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={s.id}
          src={resolveImageUrl(s.product!.images[0].url)}
          alt=""
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-700 ${
            i === index ? "opacity-100" : "opacity-0"
          }`}
        />
      ))}
      <span className="absolute top-2 left-2 bg-danger text-white text-[10px] font-bold px-2 py-1 rounded-full uppercase tracking-wide">
        {active.label || "Top Deal"}
      </span>
    </Link>
  );
}
