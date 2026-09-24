"use client";

import { useEffect, useState } from "react";

interface AutomationSettings {
  id: string;
  webhook_url: string | null;
  webhook_secret: string | null;
  alert_min_gross_margin_pct: number;
  alert_max_mpesa_latency_seconds: number;
  alert_max_hosting_cost_per_order: number;
  alert_max_order_cancellation_rate: number;
  alert_min_on_time_delivery_rate: number;
  alert_max_cart_abandonment_rate: number;
  alert_gross_margin_enabled: boolean;
  alert_order_cancellation_enabled: boolean;
  alert_cart_abandonment_enabled: boolean;
  alert_on_time_delivery_enabled: boolean;
  daily_admin_report_enabled: boolean;
  daily_admin_report_email: string | null;
  weekly_insight_digest_enabled: boolean;
  weekly_insight_digest_email: string | null;
  updated_at: string;
}

export default function AutomationSettingsPage() {
  const [settings, setSettings] = useState<AutomationSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/automation-settings")
      .then((res) => res.ok ? res.json() : Promise.reject(res.status))
      .then(setSettings)
      .catch(() => setMessage("Failed to load settings"));
  }, []);

  const update = (patch: Partial<AutomationSettings>) => {
    setSettings((prev) => prev ? { ...prev, ...patch } : prev);
  };

  const save = async () => {
    if (!settings) return;
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch("/api/admin/automation-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (!res.ok) throw new Error("Save failed");
      setMessage("Settings saved");
    } catch {
      setMessage("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (!settings) {
    return <div className="max-w-3xl mx-auto text-sm text-muted">Loading automation settings...</div>;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Automation Settings</h1>
        <p className="text-sm text-muted">Manage webhooks, alert thresholds, and scheduled reports.</p>
      </div>

      {message && (
        <div className="card p-4 text-sm">{message}</div>
      )}

      <div className="card p-5 space-y-4">
        <h2 className="font-bold">Webhooks</h2>
        <label className="block space-y-1">
          <span className="text-sm font-medium">Webhook URL</span>
          <input
            type="url"
            className="w-full border border-border rounded-md px-3 py-2 text-sm"
            placeholder="https://hook.us.make.com/..."
            value={settings.webhook_url || ""}
            onChange={(e) => update({ webhook_url: e.target.value })}
          />
        </label>
        <label className="block space-y-1">
          <span className="text-sm font-medium">Webhook secret</span>
          <input
            type="text"
            className="w-full border border-border rounded-md px-3 py-2 text-sm"
            placeholder="Optional shared secret"
            value={settings.webhook_secret || ""}
            onChange={(e) => update({ webhook_secret: e.target.value })}
          />
        </label>
      </div>

      <div className="card p-5 space-y-4">
        <h2 className="font-bold">Alert Thresholds</h2>
        <div className="space-y-3">
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={settings.alert_gross_margin_enabled}
              onChange={(e) => update({ alert_gross_margin_enabled: e.target.checked })}
            />
            <span className="text-sm font-medium">Gross margin alerts</span>
          </label>
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={settings.alert_order_cancellation_enabled}
              onChange={(e) => update({ alert_order_cancellation_enabled: e.target.checked })}
            />
            <span className="text-sm font-medium">Order cancellation alerts</span>
          </label>
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={settings.alert_cart_abandonment_enabled}
              onChange={(e) => update({ alert_cart_abandonment_enabled: e.target.checked })}
            />
            <span className="text-sm font-medium">Cart abandonment alerts</span>
          </label>
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={settings.alert_on_time_delivery_enabled}
              onChange={(e) => update({ alert_on_time_delivery_enabled: e.target.checked })}
            />
            <span className="text-sm font-medium">On-time delivery alerts</span>
          </label>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Min gross margin %</span>
            <input
              type="number"
              className="w-full border border-border rounded-md px-3 py-2 text-sm"
              value={settings.alert_min_gross_margin_pct}
              onChange={(e) => update({ alert_min_gross_margin_pct: parseFloat(e.target.value) })}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Max order cancellation rate %</span>
            <input
              type="number"
              className="w-full border border-border rounded-md px-3 py-2 text-sm"
              value={settings.alert_max_order_cancellation_rate}
              onChange={(e) => update({ alert_max_order_cancellation_rate: parseFloat(e.target.value) })}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Min on-time delivery rate %</span>
            <input
              type="number"
              className="w-full border border-border rounded-md px-3 py-2 text-sm"
              value={settings.alert_min_on_time_delivery_rate}
              onChange={(e) => update({ alert_min_on_time_delivery_rate: parseFloat(e.target.value) })}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Max cart abandonment rate %</span>
            <input
              type="number"
              className="w-full border border-border rounded-md px-3 py-2 text-sm"
              value={settings.alert_max_cart_abandonment_rate}
              onChange={(e) => update({ alert_max_cart_abandonment_rate: parseFloat(e.target.value) })}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Max M-Pesa latency (seconds)</span>
            <input
              type="number"
              className="w-full border border-border rounded-md px-3 py-2 text-sm"
              value={settings.alert_max_mpesa_latency_seconds}
              onChange={(e) => update({ alert_max_mpesa_latency_seconds: parseFloat(e.target.value) })}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Max hosting cost per order (KES)</span>
            <input
              type="number"
              className="w-full border border-border rounded-md px-3 py-2 text-sm"
              value={settings.alert_max_hosting_cost_per_order}
              onChange={(e) => update({ alert_max_hosting_cost_per_order: parseFloat(e.target.value) })}
            />
          </label>
        </div>
      </div>

      <div className="card p-5 space-y-4">
        <h2 className="font-bold">Scheduled Reports</h2>
        <div className="space-y-3">
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={settings.daily_admin_report_enabled}
              onChange={(e) => update({ daily_admin_report_enabled: e.target.checked })}
            />
            <div>
              <span className="text-sm font-medium">Daily admin report</span>
              <p className="text-xs text-muted">Sent each morning with margin leakage summary.</p>
            </div>
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Daily report email</span>
            <input
              type="email"
              className="w-full border border-border rounded-md px-3 py-2 text-sm"
              value={settings.daily_admin_report_email || ""}
              onChange={(e) => update({ daily_admin_report_email: e.target.value })}
            />
          </label>
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={settings.weekly_insight_digest_enabled}
              onChange={(e) => update({ weekly_insight_digest_enabled: e.target.checked })}
            />
            <div>
              <span className="text-sm font-medium">Weekly insight digest</span>
              <p className="text-xs text-muted">Weekly top merchants, churn risks, and anomalies.</p>
            </div>
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Weekly digest email</span>
            <input
              type="email"
              className="w-full border border-border rounded-md px-3 py-2 text-sm"
              value={settings.weekly_insight_digest_email || ""}
              onChange={(e) => update({ weekly_insight_digest_email: e.target.value })}
            />
          </label>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving}
          className="px-4 py-2 text-sm font-medium bg-amber text-white rounded-md hover:bg-amber/90 disabled:opacity-60"
        >
          {saving ? "Saving..." : "Save settings"}
        </button>
        {settings.updated_at && (
          <span className="text-xs text-muted">Last updated: {new Date(settings.updated_at).toLocaleString()}</span>
        )}
      </div>
    </div>
  );
}
