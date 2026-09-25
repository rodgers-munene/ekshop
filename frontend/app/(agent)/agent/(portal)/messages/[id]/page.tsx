"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Conversation } from "@/types/interface";
import MessageThread from "@/components/messaging/MessageThread";

export default function AgentConversationPage() {
  const { id } = useParams<{ id: string }>();
  const { data: conversation, isPending } = useQuery({
    queryKey: ["conversation", "/api/agent/conversations", id],
    queryFn: async () => {
      const res = await fetch(`/api/agent/conversations/${id}`);
      return res.ok ? ((await res.json()) as Conversation) : null;
    },
  });

  if (isPending) {
    return <p className="text-sm text-muted">Loading…</p>;
  }
  if (!conversation) {
    return (
      <div className="card flex flex-col items-center justify-center py-16 text-center">
        <p className="font-bold mb-3">Conversation not found.</p>
        <Link href="/agent/messages" className="btn-navy">Back to messages</Link>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <Link href="/agent/messages" className="text-xs text-muted hover:text-amber underline">← Messages</Link>
        <h1 className="font-semibold truncate">{conversation.title}</h1>
      </div>
      <div className="card p-5">
        <MessageThread apiBase="/api/agent/conversations" conversationId={conversation.id} />
      </div>
    </div>
  );
}
