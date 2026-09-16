"use client";

import { useQuery } from "@tanstack/react-query";
import { formatKES } from "@/lib/utils";

export default function AgentEarningsPage() {
  const { data: agent, isLoading } = useQuery({
    queryKey: ["agent-profile"],
    queryFn: () => fetch("/api/agent/auth").then((r) => r.json()).then((d) => d.agent),
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
        <p className="font-bold mb-1">Could not load profile</p>
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
            {formatKES((agent.weekly_earnings ?? 0).toString())}
          </p>
        </div>

        <div className="card p-5">
          <p className="text-xs text-muted mb-1">This month</p>
          <p className="text-3xl font-bold">
            {formatKES((agent.monthly_earnings ?? 0).toString())}
          </p>
        </div>
      </div>
    </div>
  );
}
