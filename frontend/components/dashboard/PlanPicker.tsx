"use client";

import { useState } from "react";
import { BillingInterval, SubscriptionPlan } from "@/types/interface";
import { formatKES } from "@/lib/utils";

function planPrice(plan: SubscriptionPlan, interval: BillingInterval): string {
  if (interval === "annual" && plan.price_yearly) return plan.price_yearly;
  return plan.price_monthly;
}

export default function PlanPicker({
  plans,
  currentPlanCode,
  currentInterval,
  defaultLabel,
}: {
  plans: SubscriptionPlan[];
  currentPlanCode: string;
  currentInterval: BillingInterval;
  defaultLabel: string;
}) {
  const [planCode, setPlanCode] = useState(currentPlanCode);
  const [interval, setInterval] = useState<BillingInterval>(currentInterval);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isSwitching = planCode !== currentPlanCode || interval !== currentInterval;
  const buttonLabel = isSwitching ? "Switch plan & pay" : defaultLabel;

  async function handleSubmit() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/dashboard/subscription/renew", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_code: planCode, billing_interval: interval }),
      });
      const data = await res.json();
      if (res.ok && data.authorization_url) {
        window.location.href = data.authorization_url;
        return;
      }
      setError(data.detail ?? "Couldn't start payment. Please try again.");
    } catch {
      setError("Couldn't start payment. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="inline-flex rounded-lg border border-border p-1 bg-surface">
        {(["monthly", "annual"] as const).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setInterval(option)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              interval === option ? "bg-amber text-ink font-semibold" : "text-muted"
            }`}
          >
            {option === "monthly" ? "Billed monthly" : "Billed annually"}
          </button>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {plans.map((plan) => {
          const selected = plan.code === planCode;
          const isCurrent = plan.code === currentPlanCode;
          return (
            <button
              key={plan.code}
              type="button"
              onClick={() => setPlanCode(plan.code)}
              className={`text-left rounded-lg border p-4 transition-colors ${
                selected ? "border-amber ring-1 ring-amber" : "border-border"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold">{plan.name}</span>
                {isCurrent && <span className="text-xs text-muted">Current plan</span>}
              </div>
              <div className="text-lg font-bold">
                {formatKES(planPrice(plan, interval))}
                <span className="text-sm font-normal text-muted"> / {interval === "annual" ? "year" : "month"}</span>
              </div>
              <div className="text-sm text-muted mt-1">
                {plan.max_products ? `Up to ${plan.max_products} products` : "Unlimited products"}
              </div>
            </button>
          );
        })}
      </div>

      <div>
        <button type="button" onClick={handleSubmit} disabled={loading} className="btn-accent disabled:opacity-50">
          {loading ? "Please wait..." : buttonLabel}
        </button>
        {error && <p className="text-danger text-sm mt-2">{error}</p>}
      </div>
    </div>
  );
}
