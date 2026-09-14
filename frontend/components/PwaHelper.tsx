"use client";

import { useEffect } from "react";

declare global {
  interface Window {
    __ekshopInstallPrompt?: Event | null;
  }
}

export default function PwaHelper() {
  useEffect(() => {
    // Capture the install prompt so any "Install App" buttons across the UI
    // (e.g. the footer) can trigger it. Not fired on iOS Safari — those users
    // follow the "Add to Home Screen" instructions instead.
    const onPrompt = (e: Event) => {
      e.preventDefault();
      window.__ekshopInstallPrompt = e;
    };
    window.addEventListener("beforeinstallprompt", onPrompt);

    // Register the service worker only in production; in dev it can serve
    // stale hashed assets and confuse debugging.
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/", updateViaCache: "none" })
        .catch(() => {});
    }

    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
        navigator.serviceWorker.getRegistrations().then((regs) =>
          Promise.all(regs.map((r) => r.unregister()))).catch(() => {});
      }
    };
  }, []);

  return null;
}