"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Zap } from "lucide-react";
import { Promotion } from "@/types/interface";
import { formatKES, resolveImageUrl, decodeHtml } from "@/lib/utils";

function discountPct(p: Promotion): number | null {
  const product = p.product;
  if (!product?.compare_price) return null;
  const comp = parseFloat(product.compare_price);
  const price = parseFloat(product.price);
  if (!comp || !price || comp <= price) return null;
  return Math.round(((comp - price) / comp) * 100);
}

function timeLeft(target: number) {
  const diff = Math.max(0, target - Date.now());
  const totalSeconds = Math.floor(diff / 1000);
  return {
    days: Math.floor(totalSeconds / 86400),
    hours: Math.floor((totalSeconds % 86400) / 3600),
    minutes: Math.floor((totalSeconds % 3600) / 60),
    seconds: totalSeconds % 60,
  };
}

export default function FlashDeals({ deals }: { deals: Promotion[] }) {
  const [now, setNow] = useState(Date.now());

  const target = useMemo(() => {
    const upcoming = deals
      .map((d) => (d.ends_at ? new Date(d.ends_at).getTime() : null))
      .filter((t): t is number => t !== null && t > Date.now());
    return upcoming.length ? Math.min(...upcoming) : Date.now() + 24 * 60 * 60 * 1000;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deals]);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  if (deals.length === 0) return null;

  const { days, hours, minutes, seconds } = timeLeft(target);
  const unit = (v: number) => String(v).padStart(2, "0");

  const pills = [
    { label: "Days", value: unit(days) },
    { label: "Hrs", value: unit(hours) },
    { label: "Min", value: unit(minutes) },
    { label: "Sec", value: unit(seconds) },
  ];

  return (
    <section className="px-4 md:px-6 py-4">
      <div className="card p-5 border-t-4 border-t-amber overflow-hidden">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
          <h2 className="flex items-center gap-2 text-lg font-extrabold">
            <Zap size={20} className="text-amber fill-current" />
            Flash Deals
          </h2>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-widest text-muted">
              Ends in
            </span>
            <div className="flex items-center gap-1.5">
              {pills.map((p) => (
                <div
                  key={p.label}
                  className="flex flex-col items-center min-w-12 px-1.5 py-1 rounded-md bg-navy text-white"
                >
                  <span className="text-sm font-bold tabular-nums leading-none">{p.value}</span>
                  <span className="text-[9px] uppercase tracking-wider text-white/60 mt-0.5">
                    {p.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Deal grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {deals.slice(0, 4).map((deal) => {
            const product = deal.product;
            if (!product) return null;
            const pct = discountPct(deal);
            const image =
              product.images?.find((img) => img.is_primary) ?? product.images?.[0];
            return (
              <Link
                key={deal.id}
                href={`/products/${product.slug}`}
                className="group flex flex-col overflow-hidden rounded-lg border border-border hover:border-amber hover:shadow-sm transition-all"
              >
                <div className="relative aspect-square bg-white overflow-hidden">
                  {image && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={resolveImageUrl(image.url)}
                      alt=""
                      className="w-full h-full object-contain p-3 group-hover:scale-105 transition-transform duration-300"
                    />
                  )}
                  {pct && (
                    <span className="absolute top-2 left-2 bg-danger text-white text-[10px] font-bold px-2 py-1 rounded-full uppercase tracking-wide">
                      -{pct}%
                    </span>
                  )}
                </div>
                <div className="p-3 flex flex-col gap-1 flex-1">
                  <h3 className="text-sm font-medium leading-tight line-clamp-2">
                    {decodeHtml(product.name)}
                  </h3>
                  <div className="flex items-baseline gap-x-2 mt-auto pt-1">
                    <span className="font-bold">{formatKES(product.price)}</span>
                    {product.compare_price &&
                      parseFloat(product.compare_price) > parseFloat(product.price) && (
                        <span className="text-xs text-muted line-through">
                          {formatKES(product.compare_price)}
                        </span>
                      )}
                  </div>
                  <span className="text-xs text-danger font-semibold">
                    {deal.label || "Limited time"}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>

        <div className="mt-4 text-right">
          <Link href="/products" className="text-xs text-amber hover:underline">
            Shop all flash deals →
          </Link>
        </div>
      </div>
    </section>
  );
}