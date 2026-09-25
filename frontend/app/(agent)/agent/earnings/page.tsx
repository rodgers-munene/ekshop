"use client";

import { useQuery } from "@tanstack/react-query";
import { formatKES } from "@/lib/utils";

type AgentEarnings = {
  total_deliveries: number;
  weekly_deliveries: number;
  monthly_deliveries: number;
  weekly_earnings: string;
  monthly_earnings: string;
};

export default function AgentEarningsPage() {
  const { data: agent, isLoading } = useQuery({
    queryKey: ["agent-earnings"],
    queryFn: async () => {
      const res = await fetch("/api/agent/earnings");
      if (!res.ok) return null;
      return res.json() as Promise<AgentEarnings>;
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

  if (!agent) {
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
          <p className="text-xs text-muted mb-1">Total deliveries</p>
          <p className="text-3xl font-bold">{agent.total_deliveries ?? 0}</p>
        </div>

        <div className="card p-5">
          <p className="text-xs text-muted mb-1">This week</p>
          <p className="text-3xl font-bold">
            {formatKES(agent.weekly_earnings)}
          </p>
        </div>

        <div className="card p-5">
          <p className="text-xs text-muted mb-1">This month</p>
          <p className="text-3xl font-bold">
            {formatKES(agent.monthly_earnings)}
          </p>
        </div>
      </div>
    </div>
  );
}
