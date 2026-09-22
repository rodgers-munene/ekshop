"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

export default function MessageAdminButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [adminId, setAdminId] = useState<string | null>(null);
  const [adminName, setAdminName] = useState<string>("admin");

  useEffect(() => {
    fetch("/api/conversations/support-admin")
      .then((r) => (r.ok ? r.json() : Promise.resolve(null)))
      .then((data) => {
        if (data?.id) {
          setAdminId(data.id);
          setAdminName([data.first_name, data.last_name].filter(Boolean).join(" ") || "admin");
        }
      })
      .catch(() => {});
  }, []);

  async function startConversation() {
    if (!adminId) {
      toast.error("Support admin not available");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_id: adminId }),
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
      disabled={loading || !adminId}
      className="text-xs text-amber underline underline-offset-2 disabled:opacity-50"
      type="button"
    >
      {loading ? "Starting…" : `Message ${adminName}`}
    </button>
  );
}
