import { useMemo, useState } from "react";

/**
 * A smooth line chart with an area fill.
 *
 * Replaces the bar chart on the admin overview. Bars answer "what was the value
 * on that day"; a line answers "which way is it going", which is the question a
 * dashboard is usually being asked. The curve is Catmull-Rom converted to cubic
 * beziers, so it passes through every point rather than smoothing the data away.
 *
 * Deliberate choices worth naming:
 *
 * - It plots whatever series it is given and does not sum them. GMV and total
 *   transacted overlap by design -- one is a subset of the other -- so stacking
 *   them would double-count every shilling.
 * - An all-zero series draws a flat line along the baseline rather than
 *   disappearing or dividing by zero.
 * - Y axis starts at zero. Truncating it would exaggerate small changes, which
 *   is how a dashboard ends up reporting a crisis that is not one.
 */

export interface TrendSeries {
  key: string;
  label: string;
  /** CSS colour class for the stroke and its legend swatch. */
  color: string;
  values: (number | null)[];
}

export interface TrendPoint {
  label: string;
}

interface TrendChartProps {
  points: TrendPoint[];
  series: TrendSeries[];
  height?: number;
  formatValue?: (value: number) => string;
  /** Rendered under the plot, e.g. a note about an unconfigured rate. */
  footnote?: string;
}

const PADDING = { top: 12, right: 12, bottom: 22, left: 46 };

export default function TrendChart({
  points,
  series,
  height = 200,
  formatValue = (v) => String(Math.round(v)),
  footnote,
}: TrendChartProps) {
  const [hover, setHover] = useState<number | null>(null);

  const width = 640;
  const plotW = width - PADDING.left - PADDING.right;
  const plotH = height - PADDING.top - PADDING.bottom;

  const max = useMemo(() => {
    const all = series.flatMap((s) => s.values.filter((v): v is number => v != null));
    return all.length ? Math.max(...all) : 0;
  }, [series]);

  const count = points.length;
  const xAt = (i: number) =>
    PADDING.left + (count <= 1 ? plotW / 2 : (i / (count - 1)) * plotW);
  const yAt = (v: number) => {
    if (max <= 0) return PADDING.top + plotH;
    return PADDING.top + plotH - (v / max) * plotH;
  };

  const ticks = useMemo(() => {
    if (max <= 0) return [0];
    const step = niceStep(max / 4);
    const out: number[] = [];
    for (let v = 0; v <= max + step / 2; v += step) out.push(Math.round(v * 100) / 100);
    return out;
  }, [max]);

  // Show at most six labels so the axis does not turn into a smear.
  const labelEvery = Math.max(1, Math.ceil(count / 6));

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
        <p className="text-sm font-semibold">Trend</p>
        <div className="flex flex-wrap gap-3">
          {series.map((s) => (
            <span key={s.key} className="flex items-center gap-1.5 text-xs text-muted">
              <span className={`w-3 h-[3px] rounded ${s.color}`} />
              {s.label}
            </span>
          ))}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height }}
        role="img"
        aria-label={`Trend chart: ${series.map((s) => s.label).join(", ")}`}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          {series.map((s) => (
            <linearGradient
              key={s.key}
              id={`fill-${s.key}`}
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.16" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>

        {/* gridlines and y labels */}
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PADDING.left}
              x2={width - PADDING.right}
              y1={yAt(t)}
              y2={yAt(t)}
              stroke="currentColor"
              className="text-border"
              strokeWidth="1"
              vectorEffect="non-scaling-stroke"
            />
            <text
              x={PADDING.left - 6}
              y={yAt(t) + 3}
              textAnchor="end"
              className="fill-muted"
              style={{ fontSize: 9 }}
            >
              {formatValue(t)}
            </text>
          </g>
        ))}

        {/* hover guide */}
        {hover != null && (
          <line
            x1={xAt(hover)}
            x2={xAt(hover)}
            y1={PADDING.top}
            y2={PADDING.top + plotH}
            stroke="currentColor"
            className="text-muted"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
            strokeDasharray="3 3"
          />
        )}

        {series.map((s) => {
          const pts = s.values
            .map((v, i) => (v == null ? null : { x: xAt(i), y: yAt(v) }))
            .filter((p): p is { x: number; y: number } => p !== null);
          if (pts.length === 0) return null;

          const line = smoothPath(pts);
          const area = `${line} L ${pts[pts.length - 1].x} ${PADDING.top + plotH} L ${pts[0].x} ${PADDING.top + plotH} Z`;

          return (
            <g key={s.key} className={s.color}>
              <path d={area} fill={`url(#fill-${s.key})`} />
              <path
                d={line}
                fill="none"
                stroke="currentColor"
                /* 1 user unit, held at 1 physical pixel regardless of the
                   viewBox scale, so the line never thickens as the chart
                   resizes. Well under 1mm on any display. */
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {pts.map((p, i) => (
                <circle
                  key={i}
                  cx={p.x}
                  cy={p.y}
                  r={hover === i ? 3.5 : 0}
                  fill="currentColor"
                />
              ))}
            </g>
          );
        })}

        {/* x labels */}
        {points.map((p, i) =>
          i % labelEvery === 0 || i === count - 1 ? (
            <text
              key={i}
              x={xAt(i)}
              y={height - 6}
              textAnchor="middle"
              className="fill-muted"
              style={{ fontSize: 9 }}
            >
              {p.label}
            </text>
          ) : null,
        )}

        {/* invisible hit areas */}
        {points.map((p, i) => (
          <rect
            key={i}
            x={xAt(i) - plotW / Math.max(count, 1) / 2}
            y={PADDING.top}
            width={plotW / Math.max(count, 1)}
            height={plotH}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}
      </svg>

      {hover != null && (
        <div className="mt-1 text-xs">
          <span className="font-medium">{points[hover].label}</span>
          {series.map((s) => (
            <span key={s.key} className="ml-3 text-muted">
              {s.label}:{" "}
              <span className="text-ink tabular-nums">
                {s.values[hover] == null ? "—" : formatValue(s.values[hover]!)}
              </span>
            </span>
          ))}
        </div>
      )}

      {footnote && <p className="text-xs text-muted mt-2">{footnote}</p>}
    </div>
  );
}

/**
 * Catmull-Rom to cubic bezier, so the curve passes through every data point.
 *
 * Tension 0 gives the standard Catmull-Rom curve. A value slightly under 1
 * flattens the joins very slightly, which stops a sharp spike overshooting
 * above its own peak -- an overshoot would draw a value the data does not have.
 */
function smoothPath(pts: { x: number; y: number }[], tension = 0.9): string {
  if (pts.length === 0) return "";
  if (pts.length === 1) return `M ${pts[0].x} ${pts[0].y}`;
  if (pts.length === 2) {
    return `M ${pts[0].x} ${pts[0].y} L ${pts[1].x} ${pts[1].y}`;
  }

  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;

    const c1x = p1.x + ((p2.x - p0.x) / 6) * tension;
    const c1y = p1.y + ((p2.y - p0.y) / 6) * tension;
    const c2x = p2.x - ((p3.x - p1.x) / 6) * tension;
    const c2y = p2.y - ((p3.y - p1.y) / 6) * tension;

    d += ` C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`;
  }
  return d;
}

/** A round axis step (1, 2, 5, 10, 20, 50, ...) so labels read cleanly. */
function niceStep(raw: number): number {
  if (raw <= 0) return 1;
  const exp = Math.floor(Math.log10(raw));
  const base = Math.pow(10, exp);
  const norm = raw / base;
  const step = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
  return step * base;
}