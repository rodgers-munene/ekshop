"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Truck, PackageCheck, AlertTriangle, Clock } from "lucide-react";
import {
  FulfillmentDetail,
  FulfillmentStatus,
} from "@/types/interface";

/**
 * Customer-facing delivery panel.
 *
 * Two jobs. First, tell the buyer where their parcel is. Second, and the reason
 * this file exists: show them the delivery code.
 *
 * The code has to reach the customer somehow, because the rider cannot complete a
 * delivery without it and the backend rejects the transition otherwise. There is
 * no SMS or WhatsApp integration yet (questionnaire Q11 is unanswered), so this is
 * the channel for now. It is not ideal -- a code on a web page is weaker than one
 * sent to the phone number on the order -- and that is worth revisiting when a
 * messaging provider is chosen.
 *
 * The code is only ever returned once, at the moment it is issued, because the
 * server stores a hash. So it cannot be re-displayed on a later visit: if the
 * buyer closes this panel, the merchant issues a fresh code. That is a real
 * limitation of not having a delivery channel yet, and it is stated in the UI
 * rather than hidden.
 */

const STATUS_LABELS: Record<FulfillmentStatus, string> = {
  pending: "Preparing",
  assigned: "Rider assigned",
  picked_up: "Picked up",
  in_transit: "On the way",
  delivered: "Delivered",
  collected: "Collected",
  cancelled: "Cancelled",
  returned: "Returned",
  failed: "Could not deliver",
};

const STATUS_STYLES: Record<FulfillmentStatus, string> = {
  pending: "bg-amber/15 text-gold",
  assigned: "bg-info/10 text-info",
  picked_up: "bg-info/10 text-info",
  in_transit: "bg-info/10 text-info",
  delivered: "bg-success/10 text-success",
  collected: "bg-success/10 text-success",
  cancelled: "bg-surface text-muted",
  returned: "bg-surface text-muted",
  failed: "bg-danger/10 text-danger",
};

/** The rider's job, if there is one. The last job is the current attempt. */
function currentJob(fulfillment: FulfillmentDetail) {
  return fulfillment.jobs.length > 0 ? fulfillment.jobs[fulfillment.jobs.length - 1] : null;
}

function isComplete(status: FulfillmentStatus) {
  return status === "delivered" || status === "collected";
}

/** Shape of the legacy tracking endpoint, used only as a fallback. */
interface LegacyTrack {
  tracking_number?: string;
  status?: string;
  events?: { id: string; status: string; created_at: string }[];
}

export default function DeliveryPanel({
  orderId,
  /** Issued once by the merchant; passed in so the code can be shown. */
  deliveryCode,
  codeExpiresAt,
}: {
  orderId: string;
  deliveryCode?: string | null;
  codeExpiresAt?: string | null;
}) {
  const [showCode, setShowCode] = useState(true);

  const { data: fulfillment, isLoading } = useQuery({
    queryKey: ["fulfillment", orderId],
    queryFn: async () => {
      // Filtered server-side. Fetching a page and finding the order in the
      // browser silently returns nothing for a buyer with more orders than one
      // page holds.
      const res = await fetch(`/api/fulfillments?order_id=${orderId}&page_size=1`);
      if (!res.ok) return null;
      const body = await res.json();
      return (body.items?.[0] as FulfillmentDetail | undefined) ?? null;
    },
    // The status changes on its own as the rider moves, so poll. Thirty seconds
    // is frequent enough to feel live and rare enough not to hammer the API.
    refetchInterval: 30000,
  });

  /**
   * Fallback for orders dispatched before the fulfillment structure existed.
   *
   * The legacy `deliveries` table is still live and the old admin dispatch path
   * still writes to it, so some orders genuinely have no fulfillment yet. Rather
   * than render a second tracker beside this one, the same panel falls back to the
   * old endpoint and says so. Once the fulfillment backfill runs, this branch
   * simply stops being reached.
   */
  const { data: legacy } = useQuery({
    queryKey: ["legacy-delivery-track", orderId],
    queryFn: async () => {
      if (fulfillment) return null;
      const res = await fetch(`/api/delivery/${orderId}/track`);
      return res.ok ? ((await res.json()) as LegacyTrack) : null;
    },
    enabled: fulfillment === null,
    refetchInterval: 30000,
  });

  if (isLoading) return null;

  // No fulfillment yet: the order is still being prepared, which is normal. The
  // delivery code can still be shown on its own, since it is issued at dispatch
  // and a merchant may issue it before this panel has data.
  const status = fulfillment?.status;
  const job = fulfillment ? currentJob(fulfillment) : null;
  const awaitingCode =
    deliveryCode &&
    (!status ||
      status === "assigned" ||
      status === "picked_up" ||
      status === "in_transit");

  if (!fulfillment && !deliveryCode) return null;

  // No fulfillment yet: fall back to the legacy tracker so an order dispatched
  // before the new structure existed still shows movement.
  if (!fulfillment) {
    if (!legacy) return null;
    return (
      <div className="px-4 py-4 border-t border-border bg-surface/50 space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Truck size={15} className="text-gold" />
          Delivery
          {legacy.tracking_number && (
            <span className="text-xs text-muted font-normal">
              #{legacy.tracking_number}
            </span>
          )}
        </div>
        <div className="space-y-1.5">
          {(legacy.events ?? []).map((event) => (
            <div
              key={event.id}
              className="flex items-center justify-between text-xs"
            >
              <span className="text-ink">
                {LEGACY_EVENT_LABELS[event.status] ?? event.status}
              </span>
              <span className="text-muted">
                {new Date(event.created_at).toLocaleString("en-KE", {
                  day: "numeric",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-4 border-t border-border bg-surface/50 space-y-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Truck size={15} className="text-gold" />
        Delivery
        {fulfillment?.jobs?.[0]?.external_reference && (
          <span className="text-xs text-muted font-normal">
            #{fulfillment.jobs[0].external_reference.slice(0, 8).toUpperCase()}
          </span>
        )}
        {status && (
          <span
            className={`ml-auto text-xs font-medium px-2 py-1 rounded-full ${
              STATUS_STYLES[status] ?? "bg-surface text-muted"
            }`}
          >
            {STATUS_LABELS[status] ?? status}
          </span>
        )}
      </div>

      {fulfillment?.mode === "self" && fulfillment.self_rider_name && (
        <p className="text-xs text-muted">
          Delivered by {fulfillment.self_rider_name} from the shop.
        </p>
      )}

      {/* The delivery code. The single most important thing on this panel. */}
      {deliveryCode && !isComplete(status ?? "pending") && (
        <div className="card p-4 border-amber">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium text-gold mb-1 flex items-center gap-1.5">
                <PackageCheck size={14} />
                Your delivery code
              </p>
              <p className="text-xs text-muted">
                Give this to the rider when your parcel arrives. They cannot mark
                it delivered without it.
              </p>
            </div>
            {codeExpiresAt && <ExpiryNote expiresAt={codeExpiresAt} />}
          </div>

          {showCode ? (
            <>
              <p className="font-mono text-3xl font-bold tracking-[0.3em] my-4 text-center">
                {deliveryCode}
              </p>
              <button
                onClick={() => setShowCode(false)}
                className="w-full py-2 rounded-lg border border-border text-xs font-medium"
              >
                Hide
              </button>
            </>
          ) : (
            <button
              onClick={() => setShowCode(true)}
              className="w-full py-2 rounded-lg border border-border text-xs font-medium mt-3"
            >
              Show code
            </button>
          )}
        </div>
      )}

      {/* A failed attempt is worth explaining, not just colouring red. */}
      {status === "failed" && (
        <div className="card p-3 border-danger flex items-start gap-2">
          <AlertTriangle size={15} className="text-danger mt-0.5 shrink-0" />
          <p className="text-xs">
            The last delivery attempt did not succeed
            {job?.failure_reason ? `: ${job.failure_reason}` : "."} The shop has
            been notified and will arrange another attempt.
          </p>
        </div>
      )}

      {awaitingCode && !deliveryCode && (
        <div className="card p-3 flex items-start gap-2">
          <Clock size={15} className="text-muted mt-0.5 shrink-0" />
          <p className="text-xs text-muted">
            Your delivery code will appear here once the rider is on the way.
          </p>
        </div>
      )}

      {/* Timeline. The event log is append-only, so this is the whole history. */}
      {job && job.events.length > 0 && (
        <div className="space-y-1.5">
          {job.events
            .slice()
            .reverse()
            .map((event) => (
              <div
                key={event.id}
                className="flex items-center justify-between text-xs"
              >
                <span className="text-ink">
                  {eventLabel(event.event_type, event.to_status)}
                </span>
                <span className="text-muted">
                  {new Date(event.created_at).toLocaleString("en-KE", {
                    day: "numeric",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            ))}
        </div>
      )}

      {fulfillment && fulfillment.jobs.length > 1 && (
        <p className="text-xs text-muted">
          Attempt {job?.attempt} of {fulfillment.jobs.length}.
        </p>
      )}
    </div>
  );
}

/**
 * Shows when the code stops working, as an absolute time.
 *
 * Deliberately not a countdown. Reading the clock during render is impure and
 * desynchronises server and client markup, and a ticking countdown that resets
 * on every refetch is worse than a plain time. If the code does expire, the
 * rider's confirmation fails with the backend's own "expired" message and the
 * merchant issues a new one -- the backend is the authority on that, not this
 * label.
 */
function ExpiryNote({ expiresAt }: { expiresAt: string }) {
  return (
    <span className="text-xs text-muted shrink-0">
      Valid until{" "}
      {new Date(expiresAt).toLocaleTimeString("en-KE", {
        hour: "2-digit",
        minute: "2-digit",
      })}
    </span>
  );
}

/**
 * Turn an event into something a customer can read.
 *
 * The raw event types are for the audit log, so they are mapped here rather than
 * shown. Anything unrecognised falls back to the status, and then to the raw
 * value, so a new backend event can never render as a blank line.
 */
function eventLabel(eventType: string, toStatus?: string | null): string {
  const map: Record<string, string> = {
    JOB_CREATED: "Delivery requested",
    DISPATCH_REQUESTED: "Looking for a rider",
    OFFER_SENT: "Offer sent to a rider",
    RIDER_ACCEPTED: "Rider assigned",
    OFFER_DECLINED: "Rider declined, trying another",
    OFFER_WITHDRAWN: "Other offer closed",
    AT_PICKUP: "Rider at the shop",
    PICKED_UP: "Parcel collected",
    IN_TRANSIT: "On the way to you",
    DELIVERED: "Delivered",
    FAILED: "Delivery attempt failed",
    CANCELLED: "Delivery cancelled",
    RETRY_OPENED: "Another attempt arranged",
    OTP_ISSUED: "Delivery code issued",
    SETTLED: "Delivery completed",
    FULFILLMENT_CLOSED: "Delivery closed",
  };
  if (map[eventType]) return map[eventType];
  if (toStatus) return STATUS_LABELS[toStatus as FulfillmentStatus] ?? toStatus;
  return eventType;
}

/** Re-exported so the order page can share the same vocabulary. */
export { STATUS_LABELS as FULFILLMENT_STATUS_LABELS };

const LEGACY_EVENT_LABELS: Record<string, string> = {
  pending: "Preparing",
  assigned: "Rider assigned",
  picked: "Picked up",
  in_transit: "On the way",
  delivered: "Delivered",
  cancelled: "Cancelled",
};