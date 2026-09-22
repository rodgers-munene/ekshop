"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

export default function MessageAgentButton({ agentId, agentName }: { agentId: string; agentName?: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function startConversation() {
    setLoading(true);
    try {
      const res = await fetch("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agentId }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.detail ?? "Could not start conversation");
        return;
      }
      router.push(`/messages/${data.id}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={startConversation}
      disabled={loading}
      className="text-xs text-amber underline underline-offset-2 disabled:opacity-50"
      type="button"
    >
      {loading ? "Starting…" : `Message ${agentName ? agentName.split(" ")[0] : "agent"}`}
    </button>
  );
}
