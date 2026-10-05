"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

/**
 * Tells the backend this browser is open, and what page it is on.
 *
 * Mounted once in the root layout for signed-in users. The server keeps the
 * record in memory for a minute, so this only has to beat often enough to stay
 * inside that window -- every twenty seconds leaves room for two misses.
 *
 * Deliberately silent. Presence is a metric, not something a person is doing, so
 * a failed heartbeat is swallowed rather than surfaced as an error. The worst
 * case of a dropped beat is that the admin under-reports presence by twenty
 * seconds, which is the right way for this to fail.
 */

const BEAT_MS = 20_000;
/** Tab identity, stable per tab so two tabs read as two sessions. */
const SESSION_KEY = "ekshop_presence_session";

function sessionId(): string {
  if (typeof window === "undefined") return "server";
  let id = window.sessionStorage.getItem(SESSION_KEY);
  if (!id) {
    // crypto.randomUUID is available in every browser this app supports, and
    // sessionStorage keeps it per-tab, which is exactly the granularity wanted.
    id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    window.sessionStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export default function PresenceHeartbeat({ enabled = true }: { enabled?: boolean }) {
  const pathname = usePathname();
  const lastPath = useRef<string>("");

  useEffect(() => {
    if (!enabled) return;

    const beat = () => {
      const target = window.location.pathname + window.location.search;
      lastPath.current = target;
      fetch("/api/presence", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId(), path: target.slice(0, 200) }),
        keepalive: true,
      }).catch(() => {
        // Intentionally ignored -- see the note above.
      });
    };

    // Beat immediately so someone who has just loaded the page is visible now,
    // rather than up to twenty seconds later.
    beat();
    const id = window.setInterval(beat, BEAT_MS);

    // Stop on hide and resume on show. A backgrounded tab is not "using" the
    // site, and a throttled interval would otherwise send a stale page path.
    const onVisibility = () => {
      if (document.visibilityState === "visible") beat();
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [enabled, pathname]);

  return null;
}