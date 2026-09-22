"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

interface Alert {
  level: string;
  metric: string;
  message: string;
}

interface ThresholdCheckResponse {
  alerts: Alert[];
  checked_at: string;
  margin_pct: number;
}

export default function AdminAlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [marginPct, setMarginPct] = useState<number | null>(null);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["admin-alerts"],
    queryFn: async () => {
      const res = await fetch("/api/admin/alerts/check-thresholds", { method: "POST", cache: "no-store" });
      if (!res.ok) throw new Error("Failed to load alerts");
      return res.json() as Promise<ThresholdCheckResponse>;
    },
    refetchInterval: 60000,
  });

  useEffect(() => {
    if (data) {
      setAlerts(data.alerts || []);
      setMarginPct(data.margin_pct ?? null);
      setCheckedAt(data.checked_at || null);
    }
  }, [data]);

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Admin Alerts</h1>
          <p className="text-sm text-muted">
            {checkedAt ? `Last checked: ${new Date(checkedAt).toLocaleString()}` : "Loading..."}
          </p>
        </div>
        <button onClick={() => refetch()} className="text-xs border border-border rounded-md px-3 py-1.5 hover:border-amber transition-colors">
          Refresh
        </button>
      </div>

      {isLoading && <p className="text-sm text-muted">Checking thresholds...</p>}

      {!isLoading && alerts.length === 0 && (
        <div className="card p-6">
          <p className="font-bold text-success">All clear</p>
          <p className="text-sm text-muted mt-1">No threshold breaches detected.</p>
          {marginPct !== null && (
            <p className="text-xs text-muted mt-2">Current gross margin: {marginPct.toFixed(2)}%</p>
          )}
        </div>
      )}

      {alerts.length > 0 && (
        <div className="space-y-3">
          {alerts.map((alert, idx) => (
            <div key={idx} className="card p-4 border-l-4 border-danger">
              <p className="font-bold text-sm">{alert.level.toUpperCase()} — {alert.metric}</p>
              <p className="text-sm text-muted mt-1">{alert.message}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
