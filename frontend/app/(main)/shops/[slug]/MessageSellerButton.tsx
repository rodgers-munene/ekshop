"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { MessageCircle } from "lucide-react";
import { toast } from "sonner";

export default function MessageSellerButton({ shopId }: { shopId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function startConversation() {
    setLoading(true);
    try {
      const res = await fetch("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shop_id: shopId }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (res.status === 401) {
          router.push(`/login?next=/shops`);
          return;
        }
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
      className="btn-navy flex items-center gap-2 text-sm disabled:opacity-50"
    >
      <MessageCircle size={16} />
      {loading ? "Starting…" : "Message Seller"}
    </button>
  );
}
