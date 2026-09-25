"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

// Delivery agents only: opens (or resumes) their chat with Ekshop support.
export default function MessageAdminButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function startConversation() {
    setLoading(true);
    try {
      const adminRes = await fetch("/api/agent/conversations/support-admin");
      const admin = await adminRes.json().catch(() => ({}));
      if (!adminRes.ok || !admin.id) {
        toast.error("Support isn't available right now. Please try again later.");
        return;
      }
      const res = await fetch("/api/agent/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_id: admin.id }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(data.detail ?? "Could not start conversation");
        return;
      }
      router.push(`/agent/messages/${data.id}`);
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
      {loading ? "Opening…" : "Message support"}
    </button>
  );
}
