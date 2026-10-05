"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Loader2,
  Send,
  RotateCcw,
  Undo2,
  Ban,
  KeyRound,
  Wallet,
} from "lucide-react";
import {
  FulfillmentDetail,
  FulfillmentStatus,
  DeliveryJobStatus,
} from "@/types/interface";
import { formatKES } from "@/lib/utils";

/**
 * Manage one delivery.
 *
 * Every action here goes through the fulfillment API rather than writing status
 * directly, because the backend owns the transition rules. It refuses an illegal
 * move with a 409 whose message names what *was* allowed, and those messages are
 * surfaced verbatim -- "cannot go back to picked_up, allowed: delivered, failed"
 * tells a merchant what to do next in a way that "request failed" does not.
 *
 * A merchant can dispatch, offer to riders, retry, open a return, close, issue a
 * delivery code and record money. What they cannot do is override: that is
 * admin-only on the backend and requires a logged reason.
 */

const FULFILLMENT_LABELS: Record<FulfillmentStatus, string> = {
  pending: "Preparing",
  assigned: "Rider assigned",
  picked_up: "Picked up",
  in_transit: "On the way",
  delivered: "Delivered",
  collected: "Collected",
  cancelled: "Cancelled",
  returned: "Returned",
  failed: "Needs attention",
};

const JOB_STATUS_LABELS: Record<DeliveryJobStatus, string> = {
  created: "Created",
  dispatch_requested: "Looking for a rider",
  offered: "Offered",
  accepted: "Rider accepted",
  at_pickup: "Rider at the shop",
  picked_up: "Picked up",
  in_transit: "On the way",
  delivered: "Delivered",
  failed: "Failed",
  cancelled: "Cancelled",
  settled: "Settled",
  returned: "Returned",
};

/** Which actions make sense from the current job status. */
function availableActions(status: DeliveryJobStatus) {
  return {
    canDispatch: status === "created",
    // A retry needs the attempt to have ended. The backend also rejects one while
    // an earlier attempt is still in flight, so offering it here is a convenience
    // and not the authority.
    canRetry: ["failed", "cancelled", "returned", "delivered", "settled"].includes(status),
    canReturn: ["delivered", "settled", "failed"].includes(status),
    canClose: ["failed", "cancelled", "returned"].includes(status),
    canSettle: ["delivered", "failed"].includes(status),
    // A code is only useful while the parcel is on its way.
    canIssueCode: !["delivered", "settled", "returned", "cancelled"].includes(status),
  };
}

export default function FulfillmentDetailClient() {
  const params = useParams<{ fulfillmentId: string }>();
  const id = params.fulfillmentId;
  const queryClient = useQueryClient();

  const [dialog, setDialog] = useState<null | "retry" | "return" | "close" | "settle" | "otp">(null);
  const [reason, setReason] = useState("");
  const [issuedCode, setIssuedCode] = useState<{ otp: string; expires_at: string } | null>(null);
  const [settlement, setSettlement] = useState({
    fee_collected: "",
    rider_payout: "",
    incentive_paid: "",
    payment_fee: "",
  });

  const { data: f, isLoading, isError } = useQuery({
    queryKey: ["fulfillment", id],
    queryFn: async () => {
      const res = await fetch(`/api/fulfillments/${id}`);
      if (!res.ok) throw new Error();
      return (await res.json()) as FulfillmentDetail;
    },
    refetchInterval: 20000,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["fulfillment", id] });
    queryClient.invalidateQueries({ queryKey: ["fulfillments"] });
  };

  /** Every action shares this shape: POST, refetch, surface the server's message. */
  const action = useMutation({
    mutationFn: async ({ path, body }: { path: string; body?: unknown }) => {
      const res = await fetch(`/api/fulfillments/${id}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body ?? {}),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail ?? "That did not work");
      return data;
    },
    onSuccess: () => {
      invalidate();
      setDialog(null);
      setReason("");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="animate-spin text-gold" size={24} />
      </div>
    );
  }

  if (isError || !f) {
    return (
      <div className="card flex flex-col items-center justify-center py-16 text-center">
        <p className="font-bold mb-1">Could not load this delivery</p>
        <p className="text-sm text-muted">
          It may belong to another shop, or it may have been removed.
        </p>
      </div>
    );
  }

  const job = f.jobs.length > 0 ? f.jobs[f.jobs.length - 1] : null;
  const actions = job
    ? availableActions(job.status)
    : {
        canDispatch: false,
        canRetry: false,
        canReturn: false,
        canClose: false,
        canSettle: false,
        canIssueCode: false,
      };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-xs text-muted">
            Order #{f.order_id.slice(0, 8).toUpperCase()}
          </p>
          <h1 className="text-2xl font-bold">Delivery</h1>
        </div>
        <span className="text-xs font-medium px-3 py-1.5 rounded-full bg-amber/15 text-gold">
          {FULFILLMENT_LABELS[f.status] ?? f.status}
        </span>
      </div>

      {f.mode === "self" && (
        <div className="card p-4 text-sm">
          <p className="font-medium mb-1">Delivered by your own rider</p>
          <p className="text-muted text-xs">
            {f.self_rider_name} · {f.self_rider_phone}
          </p>
        </div>
      )}

      {/* Money. Gross and net are different numbers and both matter. */}
      <div className="card p-5">
        <p className="text-xs text-muted mb-3">Delivery cost</p>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted">Delivery price</span>
            <span className="font-medium">
              {f.delivery_price_gross != null
                ? formatKES(f.delivery_price_gross)
                : "Not quoted"}
            </span>
          </div>
          {f.merchant_subsidy !== "0" && (
            <div className="flex justify-between">
              <span className="text-muted">Your subsidy</span>
              <span>-{formatKES(f.merchant_subsidy)}</span>
            </div>
          )}
          {f.ekshop_subsidy !== "0" && (
            <div className="flex justify-between">
              <span className="text-muted">Ekshop subsidy</span>
              <span>-{formatKES(f.ekshop_subsidy)}</span>
            </div>
          )}
          <div className="flex justify-between border-t border-border pt-2 font-bold">
            <span>Customer pays</span>
            <span>
              {f.customer_payment != null ? formatKES(f.customer_payment) : "—"}
            </span>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="card p-5">
        <p className="text-xs text-muted mb-3">Actions</p>
        <div className="flex flex-wrap gap-2">
          {actions.canDispatch && (
            <ActionButton
              icon={Send}
              label="Find a rider"
              onClick={() => action.mutate({ path: "/dispatch" })}
              disabled={action.isPending}
            />
          )}
          {actions.canIssueCode && (
            <ActionButton
              icon={KeyRound}
              label="Issue delivery code"
              onClick={() => setDialog("otp")}
              disabled={action.isPending}
            />
          )}
          {actions.canSettle && (
            <ActionButton
              icon={Wallet}
              label="Record payment"
              onClick={() => setDialog("settle")}
              disabled={action.isPending}
            />
          )}
          {actions.canRetry && (
            <ActionButton
              icon={RotateCcw}
              label="Retry delivery"
              onClick={() => setDialog("retry")}
              disabled={action.isPending}
            />
          )}
          {actions.canReturn && (
            <ActionButton
              icon={Undo2}
              label="Open a return"
              onClick={() => setDialog("return")}
              disabled={action.isPending}
            />
          )}
          {actions.canClose && (
            <ActionButton
              icon={Ban}
              label="Close"
              onClick={() => setDialog("close")}
              disabled={action.isPending}
            />
          )}
        </div>
        {issuedCode && (
          <div className="mt-4 p-4 rounded-lg border border-amber">
            <p className="text-xs text-muted mb-1">Delivery code</p>
            <p className="font-mono text-2xl font-bold tracking-[0.25em]">
              {issuedCode.otp}
            </p>
            <p className="text-xs text-muted mt-2">
              Shown once. Share it with the customer, or let them see it on their
              order page. It cannot be retrieved again.
            </p>
          </div>
        )}
      </div>

      {/* Attempts. Every attempt is kept: a retry adds one, it never replaces. */}
      <div className="card p-5">
        <p className="text-xs text-muted mb-3">
          Attempts ({f.jobs.length})
        </p>
        <div className="space-y-4">
          {f.jobs
            .slice()
            .reverse()
            .map((j) => (
              <div key={j.id} className="border-l-2 border-border pl-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">
                    Attempt {j.attempt}
                    <span className="ml-2 text-xs font-normal text-muted capitalize">
                      {j.job_type}
                    </span>
                  </p>
                  <span className="text-xs text-muted">
                    {JOB_STATUS_LABELS[j.status] ?? j.status}
                  </span>
                </div>
                {j.failure_reason && (
                  <p className="text-xs text-danger mt-1">{j.failure_reason}</p>
                )}
                {j.override_reason && (
                  <p className="text-xs text-gold mt-1">
                    Overridden: {j.override_reason}
                  </p>
                )}
                <details className="mt-2">
                  <summary className="text-xs text-muted cursor-pointer">
                    History ({j.events.length})
                  </summary>
                  <div className="mt-2 space-y-1">
                    {j.events
                      .slice()
                      .reverse()
                      .map((e) => (
                        <div
                          key={e.id}
                          className="flex justify-between text-xs text-muted"
                        >
                          <span>{e.event_type}</span>
                          <span>
                            {new Date(e.created_at).toLocaleString("en-KE", {
                              day: "numeric",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                      ))}
                  </div>
                </details>
                {j.assignments.length > 0 && (
                  <p className="text-xs text-muted mt-2">
                    {j.assignments.length} rider offer
                    {j.assignments.length === 1 ? "" : "s"}
                    {j.assignments.some((a) => a.status === "accepted") && (
                      <span className="text-success"> · accepted</span>
                    )}
                  </p>
                )}
              </div>
            ))}
        </div>
      </div>

      {/* Settlement */}
      {f.settlement && (
        <div className="card p-5">
          <p className="text-xs text-muted mb-3">Settlement</p>
          <div className="space-y-2 text-sm">
            <MoneyRow label="Fee collected" value={f.settlement.fee_collected} />
            <MoneyRow label="Rider payout" value={f.settlement.rider_payout} negative />
            {f.settlement.incentive_paid !== "0" && (
              <MoneyRow label="Incentives" value={f.settlement.incentive_paid} negative />
            )}
            <MoneyRow label="Payment fee" value={f.settlement.payment_fee} negative />
            <div className="flex justify-between border-t border-border pt-2 font-bold">
              <span>Your contribution</span>
              <span>{formatKES(f.settlement.contribution)}</span>
            </div>
            {f.settlement.margin_pct != null && (
              <p className="text-xs text-muted text-right">
                {Number(f.settlement.margin_pct) * 100}% margin
              </p>
            )}
          </div>
        </div>
      )}

      {/* Dialogs */}
      {dialog === "otp" && (
        <Dialog title="Issue a delivery code">
          <p className="text-sm text-muted mb-4">
            The rider cannot mark this delivered without it. The code is shown
            once and cannot be retrieved again.
          </p>
          <button
            onClick={() =>
              action.mutate(
                { path: "/otp", body: { ttl_minutes: 30 } },
                {
                  onSuccess: (data: { otp: string; expires_at: string }) =>
                    setIssuedCode(data),
                },
              )
            }
            disabled={action.isPending}
            className="btn-accent w-full py-3 rounded-lg text-sm font-medium disabled:opacity-50"
          >
            {action.isPending ? "Issuing..." : "Issue code"}
          </button>
        </Dialog>
      )}

      {(dialog === "retry" || dialog === "return" || dialog === "close") && (
        <ReasonDialog
          title={
            dialog === "retry"
              ? "Retry this delivery"
              : dialog === "return"
                ? "Open a return"
                : "Close this delivery"
          }
          help={
            dialog === "retry"
              ? "A retry creates a new attempt. The failed one is kept as history, never overwritten."
              : dialog === "return"
                ? "A return is a new job carrying the goods back to you. The outward journey stays on record."
                : "Closing keeps all history. It cannot be undone."
          }
          confirmLabel={dialog === "retry" ? "Start retry" : dialog === "return" ? "Open return" : "Close delivery"}
          reason={reason}
          onReason={setReason}
          onCancel={() => setDialog(null)}
          onConfirm={() => {
            const path =
              dialog === "retry" ? "/retry" : dialog === "return" ? "/return" : "/close";
            action.mutate({ path, body: { reason } });
          }}
          pending={action.isPending}
        />
      )}

      {dialog === "settle" && (
        <Dialog title="Record payment for this attempt">
          <p className="text-sm text-muted mb-4">
            Record what was actually collected and paid out. This also marks the
            attempt settled, so it cannot be recorded twice.
          </p>
          <div className="space-y-3">
            <MoneyField
              label="Collected from customer"
              value={settlement.fee_collected}
              onChange={(v) => setSettlement({ ...settlement, fee_collected: v })}
            />
            <MoneyField
              label="Paid to rider"
              value={settlement.rider_payout}
              onChange={(v) => setSettlement({ ...settlement, rider_payout: v })}
            />
            <MoneyField
              label="Incentives (optional)"
              value={settlement.incentive_paid}
              onChange={(v) => setSettlement({ ...settlement, incentive_paid: v })}
            />
            <MoneyField
              label="Payment processing fee (optional)"
              value={settlement.payment_fee}
              onChange={(v) => setSettlement({ ...settlement, payment_fee: v })}
            />
          </div>
          <div className="flex gap-3 mt-6">
            <button
              onClick={() => setDialog(null)}
              className="flex-1 py-3 rounded-lg border border-border text-sm font-medium"
            >
              Cancel
            </button>
            <button
              onClick={() =>
                action.mutate({
                  path: "/settlement",
                  body: {
                    fee_collected: settlement.fee_collected || "0",
                    rider_payout: settlement.rider_payout || "0",
                    incentive_paid: settlement.incentive_paid || "0",
                    payment_fee: settlement.payment_fee || null,
                  },
                })
              }
              disabled={action.isPending}
              className="flex-1 btn-accent py-3 rounded-lg text-sm font-medium disabled:opacity-50"
            >
              {action.isPending ? "Saving..." : "Save"}
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}

function MoneyRow({ label, value, negative }: { label: string; value: string; negative?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span>{negative ? "-" : ""}{formatKES(value)}</span>
    </div>
  );
}

function ActionButton({
  icon: Icon,
  label,
  onClick,
  disabled,
}: {
  icon: typeof Send;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-xs font-medium hover:border-amber transition-colors disabled:opacity-50"
    >
      <Icon size={14} />
      {label}
    </button>
  );
}

function Dialog({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="card w-full max-w-md p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-bold mb-4">{title}</h2>
        {children}
      </div>
    </div>
  );
}

function ReasonDialog({
  title,
  help,
  confirmLabel,
  reason,
  onReason,
  onCancel,
  onConfirm,
  pending,
}: {
  title: string;
  help: string;
  confirmLabel: string;
  reason: string;
  onReason: (v: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  pending: boolean;
}) {
  const tooShort = reason.trim().length < 3;
  return (
    <Dialog title={title}>
      <p className="text-sm text-muted mb-4">{help}</p>
      <label className="block text-xs text-muted mb-1">Reason</label>
      <textarea
        value={reason}
        onChange={(e) => onReason(e.target.value)}
        className="input-field"
        rows={3}
        placeholder="This is kept on the delivery record"
      />
      <p className="text-xs text-muted mt-1">
        Required. It is the only record of why.
      </p>
      <div className="flex gap-3 mt-6">
        <button
          onClick={onCancel}
          className="flex-1 py-3 rounded-lg border border-border text-sm font-medium"
        >
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={pending || tooShort}
          className="flex-1 btn-accent py-3 rounded-lg text-sm font-medium disabled:opacity-50"
        >
          {pending ? "Working..." : confirmLabel}
        </button>
      </div>
    </Dialog>
  );
}

function MoneyField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-xs text-muted mb-1">{label}</label>
      <input
        type="number"
        step="0.01"
        min="0"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input-field"
        placeholder="0.00"
      />
    </div>
  );
}