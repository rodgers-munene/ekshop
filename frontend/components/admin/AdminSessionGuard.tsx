"use client";

import { useEffect, useRef } from "react";

import { ADMIN_IDLE_MINUTES } from "@/lib/session";

const IDLE_MS = ADMIN_IDLE_MINUTES * 60_000;
const PROBE_MS = 60_000;
const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "wheel"] as const;

/**
 * Ends an admin session the two ways it can end outside of signing out.
 *
 * Two clocks run at once:
 *  - inactivity: no input for ADMIN_IDLE_MINUTES signs the admin out.
 *  - expiry: the token issued at login dies at the end of the session window and
 *    is never silently renewed, so the probe below reports the cookie as gone and
 *    the admin is sent back to sign in.
 *
 * Neither clock is the security boundary -- the backend refuses to extend a
 * session past its window and every request re-checks the token. They exist so
 * the admin is told *why* they must sign in again instead of walking into a wall
 * of 401s.
 */
export default function AdminSessionGuard() {
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const leaving = useRef(false);

  useEffect(() => {
    const signOut = (reason: "idle" | "expired") => {
      if (leaving.current) return;
      leaving.current = true;
      const next = `${window.location.pathname}${window.location.search}`;
      // Clear the cookies server-side first: an expired token cannot authorise
      // anything, and a stale cookie would only confuse the next request.
      fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "logout" }),
      })
        .catch(() => {})
        .finally(() => {
          window.location.assign(`/login?reason=${reason}&next=${encodeURIComponent(next)}`);
        });
    };

    const resetIdle = () => {
      if (idleTimer.current) clearTimeout(idleTimer.current);
      idleTimer.current = setTimeout(() => signOut("idle"), IDLE_MS);
    };

    ACTIVITY_EVENTS.forEach((event) => window.addEventListener(event, resetIdle, { passive: true }));
    document.addEventListener("visibilitychange", resetIdle);
    resetIdle();

    const probe = setInterval(async () => {
      try {
        const res = await fetch("/api/auth", { cache: "no-store" });
        if (res.status === 401) signOut("expired");
      } catch {
        // A network blip is not proof the session ended; wait for the next probe.
      }
    }, PROBE_MS);

    return () => {
      if (idleTimer.current) clearTimeout(idleTimer.current);
      clearInterval(probe);
      ACTIVITY_EVENTS.forEach((event) => window.removeEventListener(event, resetIdle));
      document.removeEventListener("visibilitychange", resetIdle);
    };
  }, []);

  return null;
}
