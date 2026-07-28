"use client";

import "./globals.css";

export default function GlobalError({
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col antialiased">
        <div className="min-h-screen flex flex-col items-center justify-center text-center px-4 py-16">
          <p className="text-5xl mb-4">⚠️</p>
          <h1 className="text-2xl font-bold mb-2">Something went wrong</h1>
          <p className="text-muted text-sm max-w-xs mb-6">
            Ekshop hit an unexpected error. Please try again.
          </p>
          <button onClick={() => unstable_retry()} className="btn-accent">
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
