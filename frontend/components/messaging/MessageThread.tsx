"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Conversation, ConversationSummary, Message, MessageSenderType } from "@/types/interface";

const ROLE_LABELS: Record<MessageSenderType, string> = {
  customer: "Customer",
  seller: "Seller",
  agent: "Rider",
  admin: "Ekshop support",
};

type Props = {
  // Proxy that forwards the viewer's token: /api/agent/conversations for riders.
  apiBase: string;
} & ({ conversationId: string; orderId?: never } | { orderId: string; conversationId?: never });

/**
 * A chat thread. Pass conversationId for an existing chat, or orderId for the
 * chat about an order, which is only created when the first message is sent
 * so nobody gets an empty thread in their inbox.
 */
export default function MessageThread({ apiBase, conversationId, orderId }: Props) {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const orderChatQuery = useQuery({
    queryKey: ["conversations", apiBase],
    queryFn: async () => {
      const res = await fetch(apiBase);
      if (!res.ok) throw new Error();
      return res.json() as Promise<ConversationSummary[]>;
    },
    enabled: Boolean(orderId),
    select: (list) => list.find((c) => c.order_id === orderId)?.id ?? null,
  });
  const activeId = conversationId ?? orderChatQuery.data ?? null;

  const messagesQuery = useQuery({
    queryKey: ["messages", apiBase, activeId],
    queryFn: async () => {
      const res = await fetch(`${apiBase}/${activeId}/messages`);
      if (!res.ok) throw new Error();
      const messages = (await res.json()) as Message[];
      if (messages.some((m) => !m.is_mine && !m.is_read)) {
        fetch(`${apiBase}/${activeId}/read`, { method: "PATCH" }).catch(() => {});
      }
      return messages;
    },
    enabled: Boolean(activeId),
    refetchInterval: 5000,
  });

  const send = useMutation({
    mutationFn: async (body: string) => {
      const res = activeId
        ? await fetch(`${apiBase}/${activeId}/messages`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ body }),
          })
        : await fetch(apiBase, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ order_id: orderId, initial_message: body }),
          });
      if (!res.ok) throw new Error();
      return res.json() as Promise<Message | Conversation>;
    },
    onSuccess: () => {
      setText("");
      queryClient.invalidateQueries({ queryKey: ["conversations", apiBase] });
      queryClient.invalidateQueries({ queryKey: ["messages", apiBase] });
    },
    onError: () => toast.error("Failed to send message"),
  });

  const messages = messagesQuery.data ?? [];

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length]);

  if (orderChatQuery.isLoading || messagesQuery.isLoading) {
    return <p className="text-xs text-muted">Loading chat…</p>;
  }
  if (orderChatQuery.isError || messagesQuery.isError) {
    return <p className="text-xs text-muted">Couldn&apos;t load this chat.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <div ref={scrollRef} className="max-h-80 overflow-y-auto space-y-2 pr-1">
        {messages.length === 0 && (
          <p className="text-xs text-muted text-center py-4">
            {orderId ? "No messages yet. Send one to reach the customer and the seller." : "No messages yet."}
          </p>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.is_mine ? "justify-end" : "justify-start"}`}>
            <div
              className={`rounded-lg px-3 py-2 text-sm max-w-[80%] ${
                msg.is_mine ? "bg-amber text-white" : "bg-surface border border-border"
              }`}
            >
              {!msg.is_mine && (
                <p className="text-[10px] font-semibold uppercase tracking-wide mb-1 opacity-70">
                  {msg.sender_type === "admin" ? ROLE_LABELS.admin : msg.sender_name ?? ROLE_LABELS[msg.sender_type]}
                </p>
              )}
              <p className="whitespace-pre-wrap break-words">{msg.body}</p>
              <p className={`text-[10px] mt-1 ${msg.is_mine ? "text-white/70" : "text-muted"}`}>
                {new Date(msg.created_at).toLocaleTimeString("en-KE", { hour: "2-digit", minute: "2-digit" })}
              </p>
            </div>
          </div>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!text.trim()) return;
          send.mutate(text.trim());
        }}
        className="flex gap-2"
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="input-field flex-1"
          placeholder="Type a message…"
          maxLength={4000}
        />
        <button type="submit" disabled={send.isPending || !text.trim()} className="btn-accent disabled:opacity-50">
          Send
        </button>
      </form>
    </div>
  );
}
