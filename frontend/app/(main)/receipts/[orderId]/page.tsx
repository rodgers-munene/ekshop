"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";

export default function ReceiptPage() {
  const params = useParams();
  const orderId = params?.orderId as string;

  useEffect(() => {
    if (!orderId) return;
    window.location.href = `/api/receipts/${orderId}`;
  }, [orderId]);

  return (
    <div className="w-full max-w-2xl mx-auto px-4 md:px-6 py-8 text-center text-sm text-muted">
      Preparing your receipt…
    </div>
  );
}
