"use client";

import { useState } from "react";
import { Check, Loader2 } from "lucide-react";

type Variant = "accent" | "outline" | "danger";

const VARIANTS: Record<Variant, string> = {
  accent: "btn-accent",
  outline: "rounded-md border border-border text-muted hover:bg-ink/5 hover:text-ink",
  danger: "rounded-md border border-danger text-danger hover:bg-danger/5",
};

/**
 * An admin action button that says what it is doing. Verifying or suspending a
 * seller fires a request and then re-renders the list, which on a slow phone
 * connection is seconds of a button that looks untouched — so the click is
 * acknowledged immediately with a spinner, the button locks while in flight,
 * and a successful action flashes a tick before the list refreshes under it.
 */
export default function ActionButton({
  onAction,
  children,
  pendingLabel,
  variant = "outline",
  className = "",
  confirm,
  disabled,
}: {
  onAction: () => Promise<boolean>;
  children: React.ReactNode;
  /** Shown beside the spinner while the request is in flight. */
  pendingLabel?: string;
  variant?: Variant;
  className?: string;
  /** Shown in a confirm() prompt before anything is sent. */
  confirm?: string;
  disabled?: boolean;
}) {
  const [state, setState] = useState<"idle" | "pending" | "done">("idle");

  async function handleClick() {
    if (state === "pending") return;
    if (confirm && !window.confirm(confirm)) return;

    setState("pending");
    const ok = await onAction().catch(() => false);
    if (!ok) {
      setState("idle");
      return;
    }
    setState("done");
    // Long enough to register as a confirmation, short enough that the button
    // is usable again by the time a refetch has replaced the row.
    setTimeout(() => setState("idle"), 1500);
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled || state === "pending"}
      aria-busy={state === "pending"}
      className={`inline-flex items-center justify-center gap-1.5 text-xs font-medium py-1.5 px-3 transition-all active:scale-95 disabled:opacity-60 disabled:cursor-wait ${VARIANTS[variant]} ${className}`}
    >
      {state === "pending" && <Loader2 size={13} className="animate-spin" />}
      {state === "done" && <Check size={13} />}
      {state === "pending" ? pendingLabel ?? children : children}
    </button>
  );
}
