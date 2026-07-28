"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { PaginatedResponse, User } from "@/types/interface";
import Pagination from "@/components/admin/Pagination";

const LIMIT = 20;

const STATUS_STYLE: Record<string, string> = {
  active: "bg-success/10 text-success",
  pending: "bg-amber/15 text-amber",
  suspended: "bg-danger/10 text-danger",
};

export default function AdminUsersPage() {
  const [q, setQ] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [page, setPage] = useState(1);
  const queryClient = useQueryClient();

  const { data, isPending: loading } = useQuery({
    queryKey: ["admin", "users", activeQuery, page],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), limit: String(LIMIT) });
      if (activeQuery) params.set("q", activeQuery);
      return fetch(`/api/admin/users?${params}`)
        .then((r) => r.json())
        .then((data): PaginatedResponse<User> =>
          data && Array.isArray(data.results) ? data : { total: 0, page: 1, limit: LIMIT, results: [] }
        );
    },
  });
  const users = data?.results ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / LIMIT));

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["admin", "users", activeQuery, page] });
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setActiveQuery(q);
  }

  async function suspend(userId: string) {
    if (!confirm("Suspend this user? They will be logged out and unable to sign in.")) return;
    const res = await fetch(`/api/admin/users/${userId}/suspend`, { method: "PATCH" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { toast.error(data.detail ?? "Could not suspend user"); return; }
    toast.success("User suspended");
    refresh();
  }

  async function reactivate(userId: string) {
    const res = await fetch(`/api/admin/users/${userId}/reactivate`, { method: "PATCH" });
    if (!res.ok) { toast.error("Could not reactivate user"); return; }
    toast.success("User reactivated");
    refresh();
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Users</h1>

      <form onSubmit={handleSearch} className="flex gap-2 mb-6 max-w-sm">
        <input
          className="input-field"
          placeholder="Search by name or email…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button type="submit" className="btn-navy shrink-0">Search</button>
      </form>

      {loading ? (
        <p className="text-muted text-sm">Loading…</p>
      ) : users.length === 0 ? (
        <div className="card p-10 text-center text-muted text-sm">No users found.</div>
      ) : (
        <div className="card divide-y divide-border overflow-hidden">
          {users.map((u) => (
            <div key={u.id} className="flex items-center justify-between gap-4 p-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-medium truncate">{u.first_name} {u.last_name}</p>
                  <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full capitalize ${STATUS_STYLE[u.status] ?? "bg-ink/10 text-ink"}`}>
                    {u.status}
                  </span>
                  <span className="text-[10px] text-muted uppercase">{u.role}</span>
                </div>
                <p className="text-xs text-muted truncate">{u.email}</p>
              </div>
              <div className="shrink-0">
                {u.status === "suspended" ? (
                  <button onClick={() => reactivate(u.id)} className="btn-accent text-xs py-1.5 px-3">
                    Reactivate
                  </button>
                ) : (
                  <button onClick={() => suspend(u.id)} className="text-xs py-1.5 px-3 rounded-md border border-danger text-danger hover:bg-danger/5">
                    Suspend
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
