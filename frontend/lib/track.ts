const SESSION_KEY = "ekshop_session_id";

export type TrackableEvent =
  | "view"
  | "click"
  | "add_to_cart"
  | "remove_from_cart"
  | "wishlist"
  | "purchase"
  | "search"
  | "review";

function getSessionId(): string {
  if (typeof window === "undefined") return "server";
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

interface TrackPayload {
  product_id?: string;
  category_id?: string;
  query?: string;
  meta?: Record<string, unknown>;
}

// Fire-and-forget: feeds the recommendation engine's per-user category weights
// and per-product trending score. Never blocks or surfaces errors to the buyer.
export function trackEvent(eventType: TrackableEvent, payload: TrackPayload = {}) {
  if (typeof window === "undefined") return;
  fetch("/api/recommendations/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: getSessionId(),
      event_type: eventType,
      ...payload,
    }),
    keepalive: true,
  }).catch(() => {});
}
