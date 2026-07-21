"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { resolveImageUrl as resolveUrl } from "@/lib/utils";

interface ProductImage {
  id: string;
  url: string;
  is_primary: boolean;
}

export default function ProductImageGallery({
  images,
  productName,
}: {
  images: ProductImage[];
  productName: string;
}) {
  const [current, setCurrent] = useState(0);
  const [direction, setDirection] = useState(0);

  function goTo(index: number) {
    setDirection(index > current ? 1 : -1);
    setCurrent(index);
  }

  useEffect(() => {
    if (images.length <= 1) return;
    const timer = setInterval(() => {
      setCurrent((prev) => {
        const next = (prev + 1) % images.length;
        setDirection(1);
        return next;
      });
    }, 3500);
    return () => clearInterval(timer);
  }, [images.length]);

  const variants = {
    enter: (dir: number) => ({ x: dir > 0 ? "100%" : "-100%", opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (dir: number) => ({ x: dir > 0 ? "-100%" : "100%", opacity: 0 }),
  };

  if (images.length === 0) {
    return (
      <div className="w-full h-[360px] md:h-[480px] bg-surface flex items-center justify-center text-muted text-sm">
        No image
      </div>
    );
  }

  return (
    <div>
      {/* Main image */}
      <div className="relative w-full h-[360px] md:h-[480px] overflow-hidden bg-surface">
        <AnimatePresence custom={direction} mode="popLayout">
          <motion.img
            key={current}
            custom={direction}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ type: "tween", duration: 0.3, ease: "easeInOut" }}
            src={resolveUrl(images[current]?.url ?? "")}
            alt={productName}
            className="absolute inset-0 w-full h-full object-cover"
          />
        </AnimatePresence>

        {/* Dot indicators */}
        {images.length > 1 && (
          <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5 z-10">
            {images.map((_, i) => (
              <button
                key={i}
                onClick={() => goTo(i)}
                className={`w-2 h-2 rounded-full transition-colors ${
                  i === current ? "bg-ink" : "bg-ink/30 hover:bg-ink/60"
                }`}
              />
            ))}
          </div>
        )}
      </div>

      {/* Thumbnail strip */}
      {images.length > 1 && (
        <div className="flex gap-2 p-3 border-t border-border overflow-x-auto scrollbar-hide">
          {images.slice(0, 6).map((img, i) => (
            <button
              key={img.id}
              onClick={() => goTo(i)}
              className={`w-16 h-16 shrink-0 rounded-md overflow-hidden border-2 transition-colors ${
                i === current
                  ? "border-amber"
                  : "border-transparent opacity-70 hover:opacity-100"
              }`}
            >
              <img
                src={resolveUrl(img.url)}
                alt={`${productName} ${i + 1}`}
                className="w-full h-full object-cover"
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
