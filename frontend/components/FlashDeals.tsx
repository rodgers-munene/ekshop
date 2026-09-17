"use client";

import { useEffect, useMemo, useState } from "react";
import { Zap } from "lucide-react";
import { Promotion } from "@/types/interface";
import ProductCard from "@/components/ProductCard";
import CardRail from "@/components/CardRail";

function discountPct(p: Promotion): number | null {
  const product = p.product;
  if (!product?.compare_price) return null;
  const comp = parseFloat(product.compare_price);
  const price = parseFloat(product.price);
  if (!comp || !price || comp <= price) return null;
  return Math.round(((comp - price) / comp) * 100);
}

// "loading" covers the server render and the first client paint, where there is
// no safe value to show: the server's clock is not the viewer's, so rendering a
// real countdown on both sides guarantees a hydration mismatch.
type Tick =
  | { status: "loading" }
  | { status: "none" }
  | { status: "live"; ms: number };

function Countdown({ endTimes }: { endTimes: number[] }) {
  const [tick, setTick] = useState<Tick>({ status: "loading" });

  useEffect(() => {
    function read(): Tick {
      const now = Date.now();
      // The soonest deadline still ahead of us — so when one deal expires the
      // clock rolls onto the next one instead of sticking at 00:00:00.
      const next = endTimes.find((t) => t > now);
      return next === undefined ? { status: "none" } : { status: "live", ms: next - now };
    }

    setTick(read());
    const id = setInterval(() => setTick(read()), 1000);
    return () => clearInterval(id);
  }, [endTimes]);

  // Nothing in this batch ever expires, so there is no honest deadline to show.
  if (tick.status === "none") return null;

  const totalSeconds = tick.status === "live" ? Math.floor(tick.ms / 1000) : 0;
  const days = Math.floor(totalSeconds / 86400);
  const unit = (v: number) => String(v).padStart(2, "0");

  const pills = [
    ...(days > 0 ? [{ label: "Days", value: unit(days) }] : []),
    { label: "Hrs", value: unit(Math.floor((totalSeconds % 86400) / 3600)) },
    { label: "Min", value: unit(Math.floor((totalSeconds % 3600) / 60)) },
    { label: "Sec", value: unit(totalSeconds % 60) },
  ];

  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-muted">
        Ends in
      </span>
      <div className="flex items-center gap-1">
        {pills.map((p) => (
          <div
            key={p.label}
            className="flex items-baseline gap-0.5 px-1.5 py-0.5 rounded bg-navy text-white"
            // Until the client clock has been read the digits would be a guess,
            // so they are held invisible rather than rendered wrong.
            style={{ visibility: tick.status === "loading" ? "hidden" : undefined }}
          >
            <span className="text-xs font-bold tabular-nums leading-none">{p.value}</span>
            <span className="text-[9px] uppercase text-white/60">{p.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function FlashDeals({ deals }: { deals: Promotion[] }) {
  // Pure derivation — no Date.now() during render, so the server and the client
  // agree on the markup and only the effect above reads a clock.
  const endTimes = useMemo(
    () =>
      deals
        .map((d) => (d.ends_at ? new Date(d.ends_at).getTime() : NaN))
        .filter((t) => Number.isFinite(t))
        .sort((a, b) => a - b),
    [deals],
  );

  const products = deals
    .map((deal) => ({ deal, product: deal.product }))
    .filter((d): d is { deal: Promotion; product: NonNullable<Promotion["product"]> } =>
      Boolean(d.product),
    );

  if (products.length === 0) return null;

  return (
    <CardRail
      title={
        <span className="flex items-center gap-2">
          <Zap size={18} className="text-amber fill-current" />
          Flash Deals
        </span>
      }
      accessory={<Countdown endTimes={endTimes} />}
      viewAllHref="/products"
    >
      {products.map(({ deal, product }) => {
        const pct = discountPct(deal);
        return (
          <div key={deal.id} className="w-36 sm:w-44 shrink-0">
            <ProductCard product={product} badge={pct ? `-${pct}%` : deal.label || undefined} />
          </div>
        );
      })}
    </CardRail>
  );
}
