"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Package } from "lucide-react";
import { toast } from "sonner";
import { AssignmentRead } from "@/types/interface";
import { formatKES } from "@/lib/utils";

/**
 * A rider's offer inbox.
 *
 * This is how the dispatch loop closes: a merchant offers a job, it appears here,
 * and the rider accepts or declines. Without it a rider never learns they were
 * offered anything.
 *
 * Offers carry an expiry window (the SLA matrix gives wave 1 sixty to ninety
 * seconds). The countdown is deliberately coarse -- a rider watching seconds tick
 * is a rider making a worse decision than one reading 'expires soon'.
 *
 * Accepting claims the job: the backend sets the rider on it and withdraws the
 * other live offers for the same job, so the job then appears under Deliveries.
 */

export default function OfferInbox() {
  const queryClient = useQueryClient();
  const [busyId, setBusyId] = useState<string | null>(null);

  const { data: offers, isLoading, isError, dataUpdatedAt } = useQuery({
    queryKey: ["agent-offers"],
    queryFn: async () => {
      const res = await fetch("/api/fulfillments/offers/me");
      if (!res.ok) throw new Error();
      return (await res.json()) as AssignmentRead[];
    },
    // Offers expire in about ninety seconds, so polling has to be brisk or the
    // list is stale before it renders.
    refetchInterval: 15000,
  });

  const respond = useMutation({
    mutationFn: async ({
      jobId,
      status,
      reason,
    }: {
      jobId: string;
      status: "accepted" | "declined";
      reason?: string;
    }) => {
      const res = await fetch(`/api/fulfillments/jobs/${jobId}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, decline_reason: reason ?? null }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail ?? "Could not send your answer");
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-offers"] });
      queryClient.invalidateQueries({ queryKey: ["agent-deliveries"] });
    },
    onError: (error: Error) => toast.error(error.message),
    onSettled: () => setBusyId(null),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="card flex flex-col items-center justify-center py-16 text-center">
        <p className="font-bold mb-1">Could not load offers</p>
        <p className="text-sm text-muted">Pull down to try again.</p>
      </div>
    );
  }

  const open = (offers ?? []).filter((o) => o.status === "offered");
  const accepted = (offers ?? []).filter((o) => o.status === "accepted");

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-sm font-bold mb-3">
          New offers
          {open.length > 0 && (
            <span className="ml-2 text-xs font-normal text-muted">
              {open.length} waiting
            </span>
          )}
        </h2>

        {open.length === 0 ? (
          <div className="card flex flex-col items-center justify-center py-12 text-center">
            <Package size={24} className="text-muted mb-2" />
            <p className="text-sm font-medium">No offers right now</p>
            <p className="text-xs text-muted mt-1">
              Keep your status on Available and offers will appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {open.map((offer) => (
              <OfferCard
                key={offer.id}
                offer={offer}
                sampledAt={dataUpdatedAt}
                busy={busyId === offer.job_id}
                onAccept={() => {
                  setBusyId(offer.job_id);
                  respond.mutate({ jobId: offer.job_id, status: "accepted" });
                }}
                onDecline={() => {
                  setBusyId(offer.job_id);
                  respond.mutate({
                    jobId: offer.job_id,
                    status: "declined",
                    reason: "Too far",
                  });
                }}
              />
            ))}
          </div>
        )}
      </section>

      {accepted.length > 0 && (
        <section>
          <h2 className="text-sm font-bold mb-3">Accepted</h2>
          <div className="space-y-3">
            {accepted.map((offer) => (
              <Link
                key={offer.id}
                href={`/agent/deliveries/${offer.job_id}`}
                className="card p-4 flex items-center justify-between hover:border-amber transition-colors"
              >
                <div>
                  <p className="text-sm font-medium">Job accepted</p>
                  {offer.payout_estimate && (
                    <p className="text-xs text-muted mt-0.5">
                      {formatKES(offer.payout_estimate)} estimated
                    </p>
                  )}
                </div>
                <span className="text-xs text-amber">Open →</span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function OfferCard({
  offer,
  sampledAt,
  busy,
  onAccept,
  onDecline,
}: {
  offer: AssignmentRead;
  sampledAt: number;
  busy: boolean;
  onAccept: () => void;
  onDecline: () => void;
}) {
  return (
    <div className="card p-4 border-amber">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium">New delivery offer</p>
          <p className="text-xs text-muted mt-0.5">
            Wave {offer.wave}
            {offer.distance_km && ` · ${offer.distance_km} km away`}
          </p>
        </div>
        <ExpiryPill expiresAt={offer.expires_at} sampledAt={sampledAt} />
      </div>

      {offer.payout_estimate && (
        <p className="text-lg font-bold mt-3">
          {formatKES(offer.payout_estimate)}
          <span className="text-xs font-normal text-muted ml-1.5">estimated</span>
        </p>
      )}

      <div className="flex gap-2 mt-4">
        <button
          onClick={onAccept}
          disabled={busy}
          className="flex-1 btn-accent py-2.5 rounded-lg text-sm font-medium disabled:opacity-50"
        >
          {busy ? (
            <Loader2 size={15} className="animate-spin mx-auto" />
          ) : (
            "Accept"
          )}
        </button>
        <button
          onClick={onDecline}
          disabled={busy}
          className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium disabled:opacity-50"
        >
          Decline
        </button>
      </div>
    </div>
  );
}

/**
 * Coarse expiry label.
 *
 * No per-second countdown, and no clock read during render -- that is impure and
 * desynchronises server and client markup. Instead the clock is sampled once
 * per poll cycle and passed down, so the label advances every fifteen seconds
 * alongside the refetch that brings any state change. A rider watching seconds
 * tick makes a worse decision than one reading "expiring", and the backend
 * refuses a genuinely expired offer with a 409 regardless of what this says.
 */
function ExpiryPill({
  expiresAt,
  sampledAt,
}: {
  expiresAt?: string | null;
  sampledAt: number;
}) {
  if (!expiresAt) return null;
  const remainingMs = new Date(expiresAt).getTime() - sampledAt;

  if (remainingMs <= 0) {
    return (
      <span className="text-xs text-danger px-2 py-1 rounded-full bg-danger/10 shrink-0">
        Expired
      </span>
    );
  }
  if (remainingMs < 30_000) {
    return (
      <span className="text-xs text-amber px-2 py-1 rounded-full bg-amber/15 shrink-0">
        Expiring
      </span>
    );
  }
  return (
    <span className="text-xs text-muted px-2 py-1 rounded-full bg-surface shrink-0">
      Expires soon
    </span>
  );
}