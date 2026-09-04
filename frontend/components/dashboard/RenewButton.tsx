"use client";

import { useState } from "react";

export default function RenewButton({ label = "Renew now" }: { label?: string }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRenew() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/dashboard/subscription/renew", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.authorization_url) {
        window.location.href = data.authorization_url;
        return;
      }
      setError(data.detail ?? "Couldn't start payment. Please try again.");
    } catch {
      setError("Couldn't start payment. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <button type="button" onClick={handleRenew} disabled={loading} className="btn-accent disabled:opacity-50">
        {loading ? "Please wait..." : label}
      </button>
      {error && <p className="text-danger text-sm mt-2">{error}</p>}
    </div>
  );
}
