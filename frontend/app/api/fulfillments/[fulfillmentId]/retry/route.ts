import { proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";

/**
 * Open a retry after a failed attempt.
 *
 * This creates a NEW job with an incremented attempt number; the failed one is
 * never modified or deleted. The backend requires a reason and rejects a retry
 * while an earlier attempt is still in flight.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ fulfillmentId: string }> },
) {
  const { fulfillmentId } = await params;
  return proxyJson("user", `/fulfillments/${fulfillmentId}/retry`, req, "POST");
}