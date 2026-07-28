import { formatKES } from "@/lib/utils";

interface SalesChartProps {
  data: { label: string; value: number }[];
  title?: string;
  formatValue?: (value: number) => string;
}

export default function SalesChart({ data, title = "Sales (last 14 days)", formatValue = formatKES }: SalesChartProps) {
  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="card p-5">
      <p className="text-sm font-semibold mb-5">{title}</p>
      <div className="flex items-end gap-1.5 h-36">
        {data.map((d, i) => (
          <div key={i} className="group relative flex-1 h-full flex flex-col justify-end items-center">
            <div
              className="absolute -top-1 -translate-y-full left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-navy text-white text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap pointer-events-none"
            >
              {formatValue(d.value)}
            </div>
            <div
              className="w-full rounded-t bg-amber/70 group-hover:bg-amber transition-colors min-h-[3px]"
              style={{ height: `${(d.value / max) * 100}%` }}
            />
          </div>
        ))}
      </div>
      <div className="flex gap-1.5 mt-2">
        {data.map((d, i) => (
          <span key={i} className="flex-1 text-center text-[9px] text-muted truncate">
            {d.label}
          </span>
        ))}
      </div>
    </div>
  );
}
