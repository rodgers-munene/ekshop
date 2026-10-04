import { proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";

/**
 * Open a return leg carrying goods back to the merchant.
 *
 * Also a new job, not a reversal of the forward one: the physical movement
 * happened and the record of it should stay.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ fulfillmentId: string }> },
) {
  const { fulfillmentId } = await params;
  return proxyJson("user", `/fulfillments/${fulfillmentId}/return`, req, "POST");
}