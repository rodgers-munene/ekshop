"use client";

import { useMemo, useState } from "react";
import StatCard from "@/components/dashboard/StatCard";
import MarketExpansionMap from "@/components/admin/MarketExpansionMap";
import { MarketExpansionReport, MarketExpansionSublocation } from "@/types/interface";

/** How many coverage rows to show before asking, since the county has almost
 * two hundred sublocations and the long tail is not a decision. */
const PAGE = 25;

function people(value: number): string {
  return value.toLocaleString();
}

export default function MarketExpansionClient({
  report,
  error,
}: {
  report: MarketExpansionReport | null;
  error: string | null;
}) {
  if (!report) return <MissingStudy detail={error} />;
  return <Report report={report} />;
}

function MissingStudy({ detail }: { detail: string | null }) {
  return (
    <div className="card p-6">
      <h1 className="text-xl font-bold text-ink mb-2">Market Expansion</h1>
      <p className="text-sm text-ink mb-2">The expansion study could not be loaded.</p>
      <p className="text-sm text-muted">
        {detail ??
          "The study bundle is not on the server. Generate it with backend/scripts/export_market_expansion.py and reload."}
      </p>
    </div>
  );
}

function Report({ report }: { report: MarketExpansionReport }) {
  const { study, coverage, candidates } = report;
  const summary = coverage.summary;
  const [onlyUnserved, setOnlyUnserved] = useState(true);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(PAGE);

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return coverage.sublocations.filter((row) => {
      if (onlyUnserved && !row.unserved) return false;
      if (needle && !row.name.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [coverage.sublocations, onlyUnserved, query]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-bold text-ink">Market Expansion</h1>
        <p className="text-sm text-muted mt-1">
          {study.county} county scored cell by cell for e-commerce demand, next to what Ekshop sells
          there today. The study is a fixed analysis; the coverage figures are live.
        </p>
        {study.source && <p className="text-xs text-muted mt-1">{study.source}</p>}
      </header>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Population in the study area"
          value={people(study.population)}
          hint={`Across ${study.sublocations} sub-locations.`}
        />
        <StatCard
          label="Unserved areas"
          value={summary.unserved_sublocations}
          hint="At least 2,000 residents and no Ekshop shop."
        />
        <StatCard
          label="Population in unserved areas"
          value={people(summary.unserved_population)}
          hint="The addressable market with no local seller."
        />
        <StatCard
          label="Candidate sites"
          value={candidates.length}
          hint="The study's top cells, at least 3 km apart."
        />
        <StatCard
          label="Ekshop shops in the area"
          value={`${summary.shops_pinned} (${summary.shops_active} active)`}
          hint="Pinned to a sub-location by coordinates."
        />
        <StatCard
          label="Paid orders attributed"
          value={`${summary.paid_orders_attributed} of ${summary.paid_orders}`}
          hint="Orders whose address names a sub-location in the study."
        />
        <StatCard label="Demand anchors mapped" value={summary.anchor_count} />
        <StatCard
          label="Scored grid"
          value={`${study.scored_cells} cells`}
          hint="Cells at or above the suitability floor the exporter keeps."
        />
      </div>

      <section className="card p-4">
        <h2 className="font-bold text-ink mb-1">Where the demand is</h2>
        <p className="text-sm text-muted mb-3">
          Shaded by how many people live in each sub-location; candidate sites are numbered, and the
          optional 3 km reach is the same locality the storefront ranks stock within.
        </p>
        <MarketExpansionMap report={report} />
      </section>

      <section className="card p-4">
        <h2 className="font-bold text-ink mb-3">Candidate sites</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="py-2 pr-3">#</th>
                <th className="py-2 pr-3">Score</th>
                <th className="py-2 pr-3">People within 1 km</th>
                <th className="py-2 pr-3">Anchors within 1.5 km</th>
                <th className="py-2 pr-3">Nearest road</th>
                <th className="py-2 pr-3">Nearest anchor</th>
                <th className="py-2 pr-3">Coordinates</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((site, index) => (
                <tr key={`${site.lat},${site.lng}`} className="border-t border-border">
                  <td className="py-2 pr-3 font-medium">{index + 1}</td>
                  <td className="py-2 pr-3 font-bold text-ink">{site.suitability}</td>
                  <td className="py-2 pr-3">{site.pop_1km?.toLocaleString()}</td>
                  <td className="py-2 pr-3">{site.poi_count_1_5km}</td>
                  <td className="py-2 pr-3">{site.road_m} m</td>
                  <td className="py-2 pr-3">{site.anchor_m} m</td>
                  <td className="py-2 pr-3 text-muted">
                    {site.lat.toFixed(3)}, {site.lng.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {study.weights && (
          <p className="text-xs text-muted mt-3">
            Score ={" "}
            {Object.entries(study.weights)
              .map(([factor, weight]) => `${weight} × ${factor}`)
              .join(" + ")}
            , each factor normalised across the county&apos;s scored cells.
          </p>
        )}
      </section>

      <section className="card p-4">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h2 className="font-bold text-ink">Sub-locations</h2>
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setLimit(PAGE);
              }}
              placeholder="Filter by name"
              className="px-3 py-1.5 text-sm border border-border rounded bg-cream"
            />
            <label className="flex items-center gap-1.5 text-xs text-ink">
              <input
                type="checkbox"
                className="accent-amber"
                checked={onlyUnserved}
                onChange={(event) => {
                  setOnlyUnserved(event.target.checked);
                  setLimit(PAGE);
                }}
              />
              Only areas with no shop
            </label>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="py-2 pr-3">Sub-location</th>
                <th className="py-2 pr-3">People</th>
                <th className="py-2 pr-3">Per km²</th>
                <th className="py-2 pr-3">Shops</th>
                <th className="py-2 pr-3">Paid orders</th>
                <th className="py-2 pr-3" />
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, limit).map((row) => (
                <Row key={row.name} row={row} />
              ))}
            </tbody>
          </table>
        </div>
        {rows.length === 0 && (
          <p className="text-sm text-muted py-2">No sub-location matches.</p>
        )}
        {rows.length > limit && (
          <button
            type="button"
            onClick={() => setLimit((current) => current + PAGE * 2)}
            className="mt-3 text-sm text-gold hover:underline"
          >
            Show {Math.min(PAGE * 2, rows.length - limit)} more of {rows.length}
          </button>
        )}
      </section>
    </div>
  );
}

function Row({ row }: { row: MarketExpansionSublocation }) {
  return (
    <tr className="border-t border-border">
      <td className="py-2 pr-3">
        {row.name}
        {row.polygons > 1 && (
          <span className="text-xs text-muted"> ({row.polygons} polygons)</span>
        )}
      </td>
      <td className="py-2 pr-3">{row.population?.toLocaleString()}</td>
      <td className="py-2 pr-3">{row.density?.toLocaleString()}</td>
      <td className="py-2 pr-3">{row.shops}</td>
      <td className="py-2 pr-3">{row.orders}</td>
      <td className="py-2 pr-3">
        {row.unserved && (
          <span className="text-xs font-medium text-gold whitespace-nowrap">no shop</span>
        )}
      </td>
    </tr>
  );
}
