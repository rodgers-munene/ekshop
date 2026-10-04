import { proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";

/** Ask dispatch to find a rider for the current attempt. */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ fulfillmentId: string }> },
) {
  const { fulfillmentId } = await params;
  return proxyJson("user", `/fulfillments/${fulfillmentId}/dispatch`, req, "POST");
}