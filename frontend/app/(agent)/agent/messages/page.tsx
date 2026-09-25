"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ConversationSummary } from "@/types/interface";
import MessageAdminButton from "@/components/MessageAdminButton";

export default function AgentMessagesPage() {
  const { data: conversations = [], isPending } = useQuery({
    queryKey: ["conversations", "/api/agent/conversations"],
    queryFn: () =>
      fetch("/api/agent/conversations")
        .then((r) => r.json())
        .then((data) => (Array.isArray(data) ? (data as ConversationSummary[]) : [])),
    refetchInterval: 15000,
  });

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-6">
        <h1 className="text-2xl font-bold">Messages</h1>
        <MessageAdminButton />
      </div>

      {isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="card p-4 h-16 animate-pulse" />
          ))}
        </div>
      ) : conversations.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-16 text-center">
          <p className="font-bold mb-1">No conversations yet</p>
          <p className="text-sm text-muted">Chats with customers about your deliveries and with Ekshop support show up here.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {conversations.map((c) => (
            <Link
              key={c.id}
              href={`/agent/messages/${c.id}`}
              className="card flex items-center justify-between gap-3 p-4 hover:border-amber/50 transition-colors"
            >
              <div className="min-w-0">
                <p className="font-medium truncate">{c.title}</p>
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
