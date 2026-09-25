"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Delivery } from "@/types/interface";
import { formatKES } from "@/lib/utils";
import MessageThread from "@/components/messaging/MessageThread";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  assigned: "Assigned",
  picked: "Picked up",
  in_transit: "In transit",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

const DELIVERY_TRANSITIONS: Record<string, string[]> = {
  assigned: ["picked", "cancelled"],
  picked: ["in_transit"],
  in_transit: ["delivered", "cancelled"],
};

export default function AgentDeliveryDetailPage() {
  const { id: deliveryId } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [showConfirm, setShowConfirm] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [recipientName, setRecipientName] = useState("");
  const [otp, setOtp] = useState("");
  const [notes, setNotes] = useState("");
  const [photoTaken, setPhotoTaken] = useState(false);
  const [sigTaken, setSigTaken] = useState(false);
  const [reportReason, setReportReason] = useState("");
  const [reportText, setReportText] = useState("");

  const { data: delivery, isLoading, isError } = useQuery({
    queryKey: ["agent-delivery", deliveryId],
    queryFn: async () => {
      const res = await fetch(`/api/agent/deliveries/${deliveryId}`);
      if (!res.ok) throw new Error();
      return res.json() as Promise<Delivery>;
    },
    refetchInterval: 15000,
  });

  const updateStatus = useMutation({
    mutationFn: async (status: string) => {
      const res = await fetch(`/api/agent/deliveries/${deliveryId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, notes }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Failed to update delivery");
      return data as Delivery;
    },
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["agent-deliveries"] });
      queryClient.invalidateQueries({ queryKey: ["agent-delivery", deliveryId] });
      toast.success(`Marked as ${STATUS_LABELS[updated.status] ?? "updated"}`);
      setShowConfirm(false);
      setRecipientName("");
      setOtp("");
      setNotes("");
      setPhotoTaken(false);
      setSigTaken(false);
    },
    onError: (err) => toast.error(err.message),
  });

  const submitReport = useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/agent/deliveries/${deliveryId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: reportReason, notes: reportText }),
      });
      if (!res.ok) throw new Error();
      return res.json();
    },
    onSuccess: () => {
      toast.success("Issue sent to dispatch");
      setShowReport(false);
      setReportReason("");
      setReportText("");
    },
    onError: () => toast.error("Failed to send report"),
  });

  if (isError) {
    return (
      <div className="card flex flex-col items-center justify-center py-20 text-center">
        <p className="font-bold mb-1">Delivery not found</p>
        <p className="text-sm text-muted">It may have been reassigned to another rider.</p>
      </div>
    );
  }

  if (isLoading || !delivery) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber" />
      </div>
    );
  }

  const order = delivery.order;
  const address = order?.delivery_address;
  const nextStatuses = DELIVERY_TRANSITIONS[delivery.status] ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="font-mono text-xs text-muted">{delivery.tracking_number}</p>
          <h1 className="text-2xl font-bold">{order?.shop?.name ?? "Order"}</h1>
        </div>
        <span className={`text-xs font-medium px-2 py-1 rounded-full ${
          delivery.status === "delivered" ? "bg-success/10 text-success" :
          delivery.status === "cancelled" ? "bg-danger/10 text-danger" :
          "bg-info/10 text-info"
        }`}>
          {STATUS_LABELS[delivery.status] ?? delivery.status}
        </span>
      </div>

      {address && (
        <div className="card p-5 mb-4">
          <p className="text-xs text-muted mb-1">Deliver to</p>
          <p className="font-semibold">{order?.buyer_name}</p>
          <p className="text-sm text-muted mt-1">
            {address.exact_location || address.town}, {address.county}
          </p>
          {address.phone && (
            <p className="text-sm text-muted mt-1 flex items-center gap-1.5">
              <span className="text-xs">📞</span> {address.phone}
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-3 gap-3 mb-6">
        <button
          onClick={() => window.open(`tel:${address?.phone}`)}
          className="card p-4 flex flex-col items-center gap-2 hover:border-amber transition-colors"
        >
          <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
            <path d="M22 16.9v3a2 2 0 01-2.2 2 19.8 19.8 0 01-8.6-3.1 19.5 19.5 0 01-6-6 19.8 19.8 0 01-3.1-8.7A2 2 0 014.1 2h3a2 2 0 012 1.7c.1 1 .3 2 .7 2.9a2 2 0 01-.4 2.1L8 10.1a16 16 0 006 6l1.4-1.4a2 2 0 012.1-.4c.9.4 1.9.6 2.9.7a2 2 0 011.7 2" />
          </svg>
          <span className="text-xs font-medium">Call</span>
        </button>
        <button
          onClick={() => {
            const dest = address
              ? `${address.exact_location || address.town}, ${address.county}`
              : "Destination";
            window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(dest)}`, "_blank");
          }}
          className="card p-4 flex flex-col items-center gap-2 hover:border-amber transition-colors"
        >
          <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
            <path d="M21 10c0 6-9 12-9 12S3 16 3 10a9 9 0 0118 0z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
          <span className="text-xs font-medium">Navigate</span>
        </button>
        <button
          onClick={() => setShowReport(true)}
          className="card p-4 flex flex-col items-center gap-2 hover:border-amber transition-colors"
        >
          <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
            <path d="M10.3 21.3a2 2 0 003.4 0l8-13.3A2 2 0 0020 5H4a2 2 0 00-1.7 3z" />
          </svg>
          <span className="text-xs font-medium">Report</span>
        </button>
      </div>

      {order?.items && order.items.length > 0 && (
        <div className="card p-5 mb-4">
          <p className="text-xs text-muted mb-3">Package</p>
          <ul className="space-y-2">
            {order.items.map((item) => (
              <li key={item.id} className="text-sm flex justify-between">
                <span>{item.quantity}× {item.product_snapshot.name}</span>
              </li>
            ))}
          </ul>
          <div className="border-t border-border mt-3 pt-3 flex justify-between items-center">
            <span className="text-sm font-medium">Total</span>
            <span className="font-bold">{formatKES(order.total)}</span>
          </div>
        </div>
      )}

      <div className="card p-5 mb-6">
        <p className="text-xs text-muted mb-1">Payment</p>
        <p className="text-lg font-bold text-success">Paid ✓</p>
      </div>

      {/* Chat */}
      {order && (
        <div className="card p-5 mb-6">
          <p className="text-xs text-muted mb-3">Messages</p>
          <MessageThread apiBase="/api/agent/conversations" orderId={order.id} />
        </div>
      )}

      {nextStatuses.length > 0 && (
        <div className="flex gap-3">
          {nextStatuses.map((status) => (
            <button
              key={status}
              onClick={() => {
                if (status === "delivered" && !showConfirm) {
                  setShowConfirm(true);
                  return;
                }
                updateStatus.mutate(status);
              }}
              disabled={updateStatus.isPending}
              className={`flex-1 py-3 rounded-lg font-medium text-sm disabled:opacity-50 ${
                status === "cancelled"
                  ? "border border-danger text-danger hover:bg-danger/10"
                  : "btn-accent"
              }`}
            >
              {updateStatus.isPending ? "..." : `Mark ${STATUS_LABELS[status]}`}
            </button>
          ))}
        </div>
      )}

      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="card w-full max-w-md p-6">
            <h2 className="text-lg font-bold mb-4">Confirm delivery</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-muted mb-1">Recipient name</label>
                <input
                  type="text"
                  value={recipientName}
                  onChange={(e) => setRecipientName(e.target.value)}
                  className="input-field"
                  placeholder="Who received the package?"
                />
              </div>
              <div>
                <label className="block text-xs text-muted mb-1">OTP / PIN from customer</label>
                <input
                  type="text"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  className="input-field"
                  placeholder="4-digit code"
                  inputMode="numeric"
                  maxLength={4}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setPhotoTaken(!photoTaken)}
                  className={`card p-4 flex flex-col items-center gap-2 cursor-pointer ${
                    photoTaken ? "border-success text-success" : ""
                  }`}
                >
                  <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
                    <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" />
                    <circle cx="12" cy="13" r="4" />
                  </svg>
                  <span className="text-xs font-medium">{photoTaken ? "Photo taken" : "Take photo"}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSigTaken(!sigTaken)}
                  className={`card p-4 flex flex-col items-center gap-2 cursor-pointer ${
                    sigTaken ? "border-success text-success" : ""
                  }`}
                >
                  <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
                    <path d="M3 17s3-1 5-3 3-5 5-5 2 4 4 4 3-2 4-2" />
                    <path d="M3 21h18" />
                  </svg>
                  <span className="text-xs font-medium">{sigTaken ? "Signature captured" : "Capture signature"}</span>
                </button>
              </div>
              <div>
                <label className="block text-xs text-muted mb-1">Notes (optional)</label>
                <input
                  type="text"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="input-field"
                  placeholder="Anything dispatch should know"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowConfirm(false)}
                className="flex-1 py-3 rounded-lg border border-border text-sm font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => updateStatus.mutate("delivered")}
                disabled={updateStatus.isPending}
                className="flex-1 btn-accent py-3 rounded-lg text-sm font-medium disabled:opacity-50"
              >
                Confirm delivery
              </button>
            </div>
          </div>
        </div>
      )}

      {showReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="card w-full max-w-md p-6">
            <h2 className="text-lg font-bold mb-4">Report an issue</h2>
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {["Customer unavailable", "Wrong address", "Phone unreachable", "Package damaged", "Other"].map((reason) => (
                  <button
                    key={reason}
                    onClick={() => setReportReason(reason)}
                    className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                      reportReason === reason
                        ? "bg-amber text-white border-amber"
                        : "border-border hover:border-amber"
                    }`}
                  >
                    {reason}
                  </button>
                ))}
              </div>
              <div>
                <label className="block text-xs text-muted mb-1">Describe what&apos;s happening</label>
                <textarea
                  value={reportText}
                  onChange={(e) => setReportText(e.target.value)}
                  className="input-field"
                  rows={4}
                  placeholder="Type here..."
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowReport(false)}
                className="flex-1 py-3 rounded-lg border border-border text-sm font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => submitReport.mutate()}
                disabled={submitReport.isPending || !reportReason}
                className="flex-1 btn-accent py-3 rounded-lg text-sm font-medium disabled:opacity-50"
              >
                Send to dispatch
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
