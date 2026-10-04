import { proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";

/**
 * Offer the current job to a specific rider.
 *
 * The backend refuses this before the job is dispatched, and rejects a repeat
 * offer to the same rider in the same wave. Both come back as 409 with a message
 * worth showing, so the detail is passed through rather than flattened.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ fulfillmentId: string }> },
) {
  const { fulfillmentId } = await params;
  return proxyJson("user", `/fulfillments/${fulfillmentId}/offers`, req, "POST");
}