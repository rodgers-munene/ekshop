"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ConversationSummary } from "@/types/interface";

export default function MessagesPage() {
  const { data: conversations = [], isPending: loading } = useQuery({
    queryKey: ["conversations"],
    queryFn: () =>
      fetch("/api/conversations")
        .then((r) => r.json())
        .then((data) => (Array.isArray(data) ? (data as ConversationSummary[]) : [])),
  });

  if (loading) {
    return (
      <div className="w-full max-w-2xl mx-auto px-4 md:px-6 py-8">
        <div className="h-7 w-32 bg-ink/10 rounded animate-pulse mb-6" />
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card p-4 h-16 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-2xl mx-auto px-4 md:px-6 py-8">
      <h1 className="text-2xl font-bold mb-6 border-b border-border pb-4">Messages</h1>

      {conversations.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-24 text-center">
          <p className="text-2xl font-extrabold mb-2">No conversations yet</p>
          <p className="text-muted text-sm">Messages with sellers will show up here.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {conversations.map((c) => (
            <Link
              key={c.id}
              href={`/messages/${c.id}`}
              className="card flex items-center justify-between gap-3 p-4 hover:border-amber/50 transition-colors"
            >
              <div className="min-w-0">
                <p className="font-medium truncate">{c.shop_name ?? "Shop"}</p>
                <p className="text-sm text-muted truncate">{c.last_message_body ?? "No messages yet"}</p>
              </div>
              {c.unread_count > 0 && (
                <span className="shrink-0 bg-amber text-ink text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                  {c.unread_count}
                </span>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
