"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Headset, MessageCircle, Loader2 } from "lucide-react";
import { ConversationSummary } from "@/types/interface";

const SUPPORT_EMAIL = "supportteam@ekshop.store";

export default function MessagesPage() {
  const router = useRouter();
  const [supportLoading, setSupportLoading] = useState(false);

  const { data: conversations = [], isPending: loading } = useQuery({
    queryKey: ["conversations"],
    queryFn: () =>
      fetch("/api/conversations")
        .then((r) => r.json())
        .then((data) => (Array.isArray(data) ? (data as ConversationSummary[]) : [])),
    refetchInterval: 15000,
  });

  async function openSupport() {
    setSupportLoading(true);
    try {
      const res = await fetch("/api/conversations/support", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (res.status === 401) {
          router.push(`/login?next=/messages`);
          return;
        }
        toast.error(data.detail ?? `Email us at ${SUPPORT_EMAIL} instead`);
        return;
      }
      router.push(`/messages/${data.id}`);
    } catch {
      toast.error(`Something went wrong. Email ${SUPPORT_EMAIL}`);
    } finally {
      setSupportLoading(false);
    }
  }

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
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6 border-b border-border pb-4">
        <h1 className="text-2xl font-bold">Messages</h1>
        <div className="flex flex-wrap items-center gap-2">
          {/* Contact Ekshop support */}
          <button
            onClick={openSupport}
            disabled={supportLoading}
            className="btn-navy flex items-center gap-2 text-sm disabled:opacity-50"
          >
            {supportLoading ? <Loader2 size={15} className="animate-spin" /> : <Headset size={15} />}
            {supportLoading ? "Starting…" : "Contact Support"}
          </button>
          {/* Start a chat with a seller */}
          <Link href="/shops" className="btn-outline flex items-center gap-2 text-sm">
            <MessageCircle size={15} />
            Message a Seller
          </Link>
        </div>
      </div>

      {conversations.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-24 text-center">
          <p className="text-2xl font-extrabold mb-2">No conversations yet</p>
          <p className="text-muted text-sm mb-6">
            Message a seller to ask about a product, or reach our support team.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <button
              onClick={openSupport}
              disabled={supportLoading}
              className="btn-navy flex items-center gap-2 text-sm disabled:opacity-50"
            >
              {supportLoading ? <Loader2 size={15} className="animate-spin" /> : <Headset size={15} />}
              {supportLoading ? "Starting…" : "Message Support"}
            </button>
            <Link href="/shops" className="btn-outline flex items-center gap-2 text-sm">
              <MessageCircle size={15} />
              Browse Shops
            </Link>
          </div>
          <p className="text-xs text-muted mt-6">
            Prefer email?{" "}
            <a href={`mailto:${SUPPORT_EMAIL}`} className="text-amber underline underline-offset-2">
              {SUPPORT_EMAIL}
            </a>
          </p>
        </div>
      ) : (
        <>
          <p className="text-xs text-muted mb-3">
            Starting a conversation with a shop or Ekshop Support is one tap away.
          </p>
          <div className="space-y-2">
            {conversations.map((c) => (
              <Link
                key={c.id}
                href={`/messages/${c.id}`}
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
        </>
      )}
    </div>
  );
}
