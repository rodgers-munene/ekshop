"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2, Users, Monitor } from "lucide-react";

/**
 * Who is online right now.
 *
 * Reads the in-memory presence registry rather than the database. The figures
 * are for this API process only, which the panel says out loud -- with several
 * workers behind a load balancer each holds its own registry, and quietly
 * reporting a third of the truth would be worse than admitting the limit.
 */

interface PresenceUser {
  user_id: string;
  role: string;
  display_name: string;
  session_id: string;
  path: string;
  seconds_active: number;
}

interface PresenceResponse {
  active_users: number;
  active_sessions: number;
  active_tabs: number;
  by_role: Record<string, number>;
  top_paths: { path: string; count: number }[];
  users: PresenceUser[];
  ttl_seconds: number;
  scope: string;
}

export default function PresencePanel() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "presence"],
    queryFn: async () => {
      const res = await fetch("/api/admin/presence");
      if (!res.ok) throw new Error();
      return (await res.json()) as PresenceResponse;
    },
    // Five seconds: presence is only interesting while it is fresh.
    refetchInterval: 5000,
  });

  if (isPending) {
    return (
      <div className="card p-5 flex items-center gap-2 text-sm text-muted">
        <Loader2 size={14} className="animate-spin" />
        Checking who is online
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="card p-5">
        <p className="text-sm font-medium mb-1 flex items-center gap-2">
          <Users size={14} /> Active now
        </p>
        <p className="text-xs text-muted">Could not load presence.</p>
      </div>
    );
  }

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium flex items-center gap-2">
          <Users size={14} className="text-gold" />
          Active now
          <span className="text-xs font-normal text-muted">
            someone using the site in the last {data.ttl_seconds}s
          </span>
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <Figure label="Users" value={data.active_users} />
        <Figure label="Sessions" value={data.active_sessions} />
        <Figure label="Tabs" value={data.active_tabs} />
      </div>

      {Object.keys(data.by_role).length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {Object.entries(data.by_role).map(([role, count]) => (
            <span
              key={role}
              className="text-xs px-2 py-1 rounded-full bg-surface text-muted capitalize"
            >
              {role} {count}
            </span>
          ))}
        </div>
      )}

      {data.top_paths.length > 0 && (
        <div className="mb-4">
          <p className="text-xs text-muted mb-1.5">Pages being viewed</p>
          <div className="space-y-1">
            {data.top_paths.map((entry) => (
              <div
                key={entry.path}
                className="flex items-center justify-between text-xs"
              >
                <span className="font-mono truncate">{entry.path}</span>
                <span className="text-muted ml-2 shrink-0">{entry.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.users.length > 0 && (
        <details>
          <summary className="text-xs text-muted cursor-pointer">
            Who ({data.users.length})
          </summary>
          <div className="mt-2 space-y-1.5">
            {data.users.map((user) => (
              <div
                key={`${user.user_id}:${user.session_id}`}
                className="flex items-center justify-between text-xs gap-2"
              >
                <span className="truncate">
                  <Monitor size={11} className="inline mr-1 text-muted" />
                  {user.display_name}
                  <span className="text-muted"> · {user.path}</span>
                </span>
                <span className="text-muted shrink-0 capitalize">{user.role}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      {data.users.length === 0 && (
        <p className="text-xs text-muted">
          Nobody has sent a heartbeat yet. This counts signed-in users with the
          site open -- it is not a page-view counter.
        </p>
      )}

      <p className="text-xs text-muted mt-3 pt-3 border-t border-border">
        Scope: {data.scope.replace(/_/g, " ")}. With more than one API process,
        each counts only its own share.
      </p>
    </div>
  );
}

function Figure({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <p className="text-2xl font-bold tabular-nums">{value}</p>
      <p className="text-xs text-muted">{label}</p>
    </div>
  );
}