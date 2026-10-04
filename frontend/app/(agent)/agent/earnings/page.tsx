"use client";

import { useQuery } from "@tanstack/react-query";
import { formatKES } from "@/lib/utils";

export default function AgentEarningsPage() {
  // Was fetching `/api/agent/auth`, which only exports POST -- a GET there can
  // never succeed. `/api/agent/earnings` is the endpoint that actually returns
  // these totals, and its response is flat rather than wrapped in `.agent`.
  const { data: earnings, isLoading, isError } = useQuery({
    queryKey: ["agent-earnings"],
    queryFn: async () => {
      const res = await fetch("/api/agent/earnings");
      if (!res.ok) throw new Error();
      return res.json() as Promise<{
        total_deliveries: number;
        weekly_deliveries: number;
        monthly_deliveries: number;
        weekly_earnings: string;
        monthly_earnings: string;
        wallet_balance: string;
      }>;
    },
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber" />
      </div>
    );
  }

  if (isError || !earnings) {
    return (
      <div className="card flex flex-col items-center justify-center py-20 text-center">
        <p className="font-bold mb-1">Could not load earnings</p>
        <p className="text-sm text-muted">Please try signing in again.</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Earnings</h1>
      <p className="text-sm text-muted mb-6">Your pay for completed deliveries</p>

      <div className="space-y-3">
        <div className="card p-5">
          <p className="text-xs text-muted mb-1">Wallet balance</p>
          <p className="text-3xl font-bold">{formatKES(earnings.wallet_balance ?? "0")}</p>
        </div>

        <div className="card p-5">
          <p className="text-xs text-muted mb-1">Total deliveries</p>
          <p className="text-3xl font-bold">{earnings.total_deliveries ?? 0}</p>
        </div>

        <div className="card p-5">
          <p className="text-xs text-muted mb-1">This week</p>
          <p className="text-3xl font-bold">{formatKES(earnings.weekly_earnings ?? "0")}</p>
          <p className="text-xs text-muted mt-1">
            {earnings.weekly_deliveries ?? 0} delivered
          </p>
        </div>

        <div className="card p-5">
          <p className="text-xs text-muted mb-1">This month</p>
          <p className="text-3xl font-bold">{formatKES(earnings.monthly_earnings ?? "0")}</p>
          <p className="text-xs text-muted mt-1">
            {earnings.monthly_deliveries ?? 0} delivered
          </p>
        </div>
      </div>
    </div>
  );
}
