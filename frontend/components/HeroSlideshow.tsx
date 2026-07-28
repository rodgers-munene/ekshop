"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { HeroSlide } from "@/types/interface";
import { resolveImageUrl } from "@/lib/utils";

const ROTATE_MS = 7000;

interface HeroSlideshowProps {
  slides: HeroSlide[];
  fallbackImageUrl?: string;
}

export default function HeroSlideshow({ slides, fallbackImageUrl }: HeroSlideshowProps) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (slides.length <= 1 || paused) return;
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % slides.length);
    }, ROTATE_MS);
    return () => clearInterval(id);
  }, [slides.length, paused]);

  const slide = slides[index] ?? null;

  return (
    <section
      className="relative h-[360px] md:h-[420px] overflow-hidden"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {slides.length > 0 ? (
        slides.map((s, i) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={s.id}
            src={resolveImageUrl(s.image_url)}
            alt=""
            loading={i === 0 ? "eager" : "lazy"}
            decoding="async"
            className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-700 ${
              i === index ? "opacity-100" : "opacity-0"
            }`}
          />
        ))
      ) : fallbackImageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={resolveImageUrl(fallbackImageUrl)}
          alt=""
          loading="eager"
          decoding="async"
          className="absolute inset-0 w-full h-full object-cover"
        />
      ) : (
        <div className="absolute inset-0 bg-navy" />
      )}

      {/* Full-bleed click target for the active slide's link, sits behind the text/CTA */}
      {slide?.link_url && (
        <Link href={slide.link_url} aria-label={slide.title || "View offer"} className="absolute inset-0" />
      )}

      <div className="absolute inset-0 bg-gradient-to-t from-navy/95 via-navy/40 to-transparent pointer-events-none" />

      <div className="relative h-full flex flex-col justify-center px-6 md:px-12 max-w-xl">
        <span className="text-xs font-medium tracking-widest uppercase text-white/70 mb-3">
          Kenya&apos;s Marketplace
        </span>
        <h1 className="text-4xl md:text-5xl font-extrabold leading-tight mb-4 text-white">
          {slide?.title ? (
            slide.title
          ) : (
            <>
              Everything you need, <span className="text-amber">delivered.</span>
            </>
          )}
        </h1>
        <p className="text-white/80 text-sm mb-6 max-w-xs">
          Thousands of verified sellers. One seamless experience.
        </p>
        <div>
          <Link href="/products" className="btn-accent">
            Shop Deals →
          </Link>
        </div>
      </div>
    </section>
  );
}
