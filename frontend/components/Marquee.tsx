"use client";

interface MarqueeProps {
  items: string[];
}

export default function Marquee({ items }: MarqueeProps) {
  if (items.length === 0) return null;

  const ticker = [...items, ...items];

  return (
    <div className="marquee-wrap w-full overflow-hidden bg-navy text-white">
      <div className="flex w-max animate-marquee gap-0 py-2">
        {ticker.map((item, i) => (
          <span
            key={i}
            className="flex items-center gap-3 text-xs font-medium whitespace-nowrap px-6"
          >
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber shrink-0" />
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}