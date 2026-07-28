"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center px-4 py-16">
      <p className="text-5xl mb-4">⚠️</p>
      <h1 className="text-2xl font-bold mb-2">Something went wrong</h1>
      <p className="text-muted text-sm max-w-xs mb-6">
        An unexpected error occurred. You can try again, or head back home.
      </p>
      <div className="flex gap-3">
        <button onClick={() => unstable_retry()} className="btn-accent">
          Try again
        </button>
        <Link href="/" className="btn-navy">
          Back to home
        </Link>
      </div>
    </div>
  );
}
