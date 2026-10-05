/**
 * Shared delivery status vocabulary for the agent portal.
 *
 * These maps were duplicated across five pages, which is how they drifted. The
 * backend owns the real state machine; this is only what the portal needs to
 * label a status and decide which buttons to offer.
 *
 * The backend refuses any transition not in its own table, so `DELIVERY_TRANSITIONS`
 * here is a UI affordance, not the authority. If the two ever disagree the backend
 * wins and the button will fail -- which is why the error toast matters.
 */

export const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  assigned: "Assigned",
  offered: "Offered",
  accepted: "Accepted",
  at_pickup: "At pickup",
  picked: "Picked up",
  in_transit: "In transit",
  delivered: "Delivered",
  failed: "Failed",
  cancelled: "Cancelled",
  returned: "Returned",
};

/**
 * Tailwind classes per status, matching the admin/dashboard pill convention.
 *
 * `text-gold` rather than `text-amber` for the accent: `amber` is the bright
 * logo yellow (#FCD806), which is unreadable as text on a white card. `gold` is
 * the deep accent (#8A6D00) introduced for exactly that reason. `bg-amber/15`
 * stays, because a translucent yellow wash behind dark gold text is the intended
 * pairing -- the token is right for fills and wrong for type.
 */
export const STATUS_STYLES: Record<string, string> = {
  delivered: "bg-success/10 text-success",
  cancelled: "bg-surface text-muted",
  failed: "bg-danger/10 text-danger",
  returned: "bg-surface text-muted",
  in_transit: "bg-info/10 text-info",
  assigned: "bg-info/10 text-info",
  picked: "bg-amber/15 text-gold",
  picked_up: "bg-amber/15 text-gold",
  at_pickup: "bg-amber/15 text-gold",
  settled: "bg-success/10 text-success",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function statusStyle(status: string): string {
  return STATUS_STYLES[status] ?? "bg-amber/15 text-gold";
}

/** Which statuses the rider may advance to from the current one. */
export const DELIVERY_TRANSITIONS: Record<string, string[]> = {
  assigned: ["picked", "cancelled"],
  picked: ["in_transit"],
  in_transit: ["delivered", "cancelled"],
};

/**
 * The backend rejects a delivery without `otp_code`, so the portal must collect
 * one before allowing the transition. Surfacing this in the button rather than in
 * a 400 afterwards is the difference between a usable form and a dead end.
 */
export function requiresOtpFor(status: string): boolean {
  return status === "delivered";
}

/** The backend issues a six-digit code. */
export const OTP_LENGTH = 6;

/**
 * A rider's own availability status.
 *
 * The backend's `DeliveryAgentStatus` is `active | inactive | busy` -- there is
 * no "available" and no "offline". The portal used to invent its own vocabulary
 * and send it verbatim, so every availability toggle was rejected, and the status
 * shown on the home screen was a hardcoded local guess rather than the server's
 * answer. These helpers keep the two in step.
 */
export type AgentStatus = "active" | "inactive" | "busy";

export const AGENT_STATUS_LABELS: Record<AgentStatus, string> = {
  active: "Available",
  busy: "Busy",
  inactive: "Offline",
};

export function agentStatusLabel(status: string): string {
  return AGENT_STATUS_LABELS[status as AgentStatus] ?? status;
}

/** Is this rider currently taking work? */
export function isOnline(status: string): boolean {
  return status === "active" || status === "busy";
}

/**
 * What the availability button should switch to.
 *
 * `busy` means "on a job", so going offline from there is allowed but coming
 * straight back to available is what the rider means when they tap it.
 */
export function nextAgentStatus(current: string): AgentStatus {
  return isOnline(current) ? "inactive" : "active";
}