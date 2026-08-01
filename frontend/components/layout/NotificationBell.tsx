"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { Notification } from "@/types/interface";

interface NotificationsResponse {
  unread_count: number;
  results: Notification[];
}

function timeAgo(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function NotificationBell({ iconClassName = "" }: { iconClassName?: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => fetch("/api/notifications").then((r) => r.json()) as Promise<NotificationsResponse>,
    refetchInterval: 30000,
  });

  const notifications = data?.results ?? [];
  const unreadCount = data?.unread_count ?? 0;

  async function markRead(id: string) {
    await fetch(`/api/notifications/${id}/read`, { method: "PATCH" });
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  async function markAllRead() {
    await fetch("/api/notifications", { method: "POST" });
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} className="relative flex items-center" aria-label="Notifications">
        <Bell size={20} className={`md:w-5.5 md:h-5.5 ${iconClassName}`} />
        {unreadCount > 0 && (
          <span className="absolute -top-2 -right-2 bg-danger text-white text-[10px] font-bold w-4.5 h-4.5 rounded-full flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed inset-x-3 top-16 sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-2 w-auto sm:w-80 max-h-96 overflow-y-auto bg-white text-ink rounded-md shadow-lg border border-border z-50">
          <div className="flex items-center justify-between px-4 py-2 border-b border-border sticky top-0 bg-white">
            <span className="text-sm font-semibold">Notifications</span>
            {unreadCount > 0 && (
              <button onClick={markAllRead} className="text-xs text-amber hover:underline">
                Mark all read
              </button>
            )}
          </div>
          {notifications.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted">No notifications yet</p>
          ) : (
            <ul className="divide-y divide-border">
              {notifications.map((n) => (
                <li key={n.id}>
                  <button
                    onClick={() => !n.is_read && markRead(n.id)}
                    className={`w-full text-left px-4 py-3 hover:bg-surface transition-colors ${!n.is_read ? "bg-amber/5" : ""}`}
                  >
                    <div className="flex items-start gap-2">
                      {!n.is_read && <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-amber shrink-0" />}
                      <div className="min-w-0">
                        <p className="text-sm font-medium leading-tight">{n.title}</p>
                        {n.body && <p className="text-xs text-muted mt-0.5 line-clamp-2">{n.body}</p>}
                        <p className="text-[10px] text-muted mt-1">{timeAgo(n.created_at)}</p>
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
