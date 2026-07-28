"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { useAuthStore } from "@/store/authStore";
import { Conversation } from "@/types/interface";

export default function ConversationPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: conversation = null, isPending: loading } = useQuery({
    queryKey: ["conversation", params.id],
    queryFn: async () => {
      const res = await fetch(`/api/conversations/${params.id}`);
      if (!res.ok) return null;
      const data: Conversation = await res.json();
      fetch(`/api/conversations/${params.id}/read`, { method: "PATCH" }).catch(() => {});
      return data;
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages.length]);

  async function sendMessage(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    setSending(true);
    try {
      const res = await fetch(`/api/conversations/${params.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: draft.trim() }),
      });
      if (!res.ok) {
        toast.error("Could not send message");
        return;
      }
      setDraft("");
      await queryClient.invalidateQueries({ queryKey: ["conversation", params.id] });
    } finally {
      setSending(false);
    }
  }

  if (loading) {
    return <div className="w-full max-w-2xl mx-auto px-4 md:px-6 py-8 text-muted text-sm">Loading…</div>;
  }

  if (!conversation) {
    return (
      <div className="w-full max-w-2xl mx-auto px-4 md:px-6 py-16 text-center">
        <p className="text-muted mb-4">Conversation not found.</p>
        <button onClick={() => router.push("/messages")} className="btn-navy">Back to messages</button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-2xl mx-auto px-4 md:px-6 py-6 flex flex-col h-[80vh]">
      <div className="flex items-center gap-3 mb-4">
        <Link href="/messages" className="text-xs text-muted hover:text-amber underline">← Messages</Link>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {conversation.messages.map((m) => {
          const mine = m.sender_id === user?.id;
          return (
            <div key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[75%] rounded-lg px-4 py-2 text-sm ${
                  mine ? "bg-amber text-ink" : "bg-surface text-ink border border-border"
                }`}
              >
                {m.body}
                <p className={`text-[10px] mt-1 ${mine ? "text-ink/60" : "text-muted"}`}>
                  {new Date(m.created_at).toLocaleTimeString("en-KE", { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={sendMessage} className="flex gap-2 pt-4 border-t border-border mt-4">
        <input
          className="input-field flex-1"
          placeholder="Type a message…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button type="submit" disabled={sending || !draft.trim()} className="btn-accent shrink-0 disabled:opacity-50">
          Send
        </button>
      </form>
    </div>
  );
}
