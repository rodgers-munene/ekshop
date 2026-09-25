"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Mail, Send, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { AdminEmailStatus } from "@/types/interface";

export default function EmailHealthCard() {
  const [testTo, setTestTo] = useState("");
  const [sending, setSending] = useState(false);

  const { data: status, isPending, error } = useQuery({
    queryKey: ["admin", "email-status"],
    queryFn: () =>
      fetch("/api/admin/email-status").then((r) => r.json()) as Promise<AdminEmailStatus>,
  });

  async function sendTest(e: React.FormEvent) {
    e.preventDefault();
    if (!testTo.trim()) return;
    setSending(true);
    try {
      const res = await fetch("/api/admin/email-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to: testTo.trim() }),
      });
      const data = (await res.json().catch(() => ({}))) as { success: boolean; detail: string };
      if (!res.ok || !data.success) {
        toast.error(data.detail ?? "Test email failed");
        return;
      }
      toast.success(data.detail);
      setTestTo("");
    } finally {
      setSending(false);
    }
  }

  const configured = status?.resend_configured ?? false;
  const verified = status?.from_domain_verified ?? false;

  return (
    <div className="card p-6">
      <div className="flex items-center gap-2 mb-1">
        <Mail size={16} className="text-muted" />
        <h2 className="font-semibold text-sm">Email delivery health</h2>
      </div>
      <p className="text-xs text-muted mb-4">
        Why the new-order / subscription emails may or may not be reaching you. Order emails are
        sent the moment a payment is confirmed.
      </p>

      {isPending ? (
        <p className="text-sm text-muted">Checking…</p>
      ) : error || !status ? (
        <p className="text-sm text-danger">Could not check email status.</p>
      ) : (
        <div className="space-y-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted">Resend API key configured</span>
            {configured ? (
              <span className="flex items-center gap-1 font-semibold text-success">
                <CheckCircle2 size={15} /> Yes
              </span>
            ) : (
              <span className="flex items-center gap-1 font-semibold text-danger">
                <XCircle size={15} /> No
              </span>
            )}
          </div>

          {!configured && (
            <p className="rounded-md bg-amber/10 text-amber px-3 py-2 flex items-start gap-2">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              RESEND_API_KEY is not set on the backend, so emails are skipped (logged to the server
              console only). Add it to the backend environment and restart.
            </p>
          )}

          <div className="flex items-center justify-between gap-3">
            <span className="text-muted">Sending from</span>
            <span className="font-mono text-xs break-all text-right">{status.from_address}</span>
          </div>

          <div className="flex items-center justify-between gap-3">
            <span className="text-muted">Sending domain verified</span>
            {verified && configured ? (
              <span className="flex items-center gap-1 font-semibold text-success">
                <CheckCircle2 size={15} /> Yes — {status.from_domain}
              </span>
            ) : (
              <span className="flex items-center gap-1 font-semibold text-danger">
                <XCircle size={15} /> {configured ? `No` : "Not checkable without a key"}
              </span>
            )}
          </div>

          {status.domains_error && (
            <p className="rounded-md bg-danger/10 text-danger px-3 py-2 text-xs">{status.domains_error}</p>
          )}

          {status.verified_domains.length > 0 && (
            <div className="flex items-start justify-between gap-3">
              <span className="text-muted shrink-0">Verified domains</span>
              <span className="text-right text-xs break-all">{status.verified_domains.join(", ")}</span>
            </div>
          )}

          <div className="flex items-center justify-between gap-3">
            <span className="text-muted">Active order-email recipients</span>
            <span className="font-semibold">{status.active_recipient_count}</span>
          </div>

          {status.active_recipient_count === 0 && configured && (
            <p className="rounded-md bg-amber/10 text-amber px-3 py-2 flex items-start gap-2">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              No active recipients — even with Resend configured, no order emails are sent. Add a
              recipient below and keep it toggled on.
            </p>
          )}

          {configured && !verified && (
            <p className="rounded-md bg-amber/10 text-amber px-3 py-2 flex items-start gap-2">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              The From domain isn&apos;t shown as verified in Resend. Add the domain and confirm its
              DNS (SPF/DKIM) records, otherwise Resend rejects every send.
            </p>
          )}

          <form onSubmit={sendTest} className="flex flex-col sm:flex-row gap-2 pt-2">
            <input
              type="email"
              value={testTo}
              onChange={(e) => setTestTo(e.target.value)}
              placeholder="ops@ekshop.store"
              required
              className="input-field flex-1"
            />
            <button type="submit" disabled={sending || !configured} className="btn-accent disabled:opacity-40">
              <Send size={14} className="mr-1.5 inline -mt-0.5" />
              {sending ? "Sending…" : "Send test email"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}