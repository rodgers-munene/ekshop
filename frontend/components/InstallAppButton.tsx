"use client";

import { useEffect, useState } from "react";
import { Download, Plus } from "lucide-react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export default function InstallAppButton() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isStandalone, setIsStandalone] = useState(false);
  const [isIOS, setIsIOS] = useState(false);

  useEffect(() => {
    const isIos =
      /iPad|iPhone|iPod/.test(navigator.userAgent) && !(window as { MSStream?: unknown }).MSStream;
    setIsIOS(isIos);
    setIsStandalone(window.matchMedia("(display-mode: standalone)").matches);

    const onPrompt = (e: Event) => setDeferredPrompt(e as BeforeInstallPromptEvent);
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  if (isStandalone) return null;

  async function handleInstall() {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") setDeferredPrompt(null);
  }

  if (deferredPrompt) {
    return (
      <button
        onClick={handleInstall}
        className="inline-flex items-center gap-1.5 text-xs hover:text-white transition-colors"
      >
        <Download size={14} /> Install App
      </button>
    );
  }

  if (isIOS) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-white/50" title="Tap the Share button, then 'Add to Home Screen'">
        <Plus size={14} /> Get the app: Share → Add to Home Screen
      </span>
    );
  }

  return null;
}