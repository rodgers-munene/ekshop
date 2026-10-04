import { proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";

/** Close a fulfillment. A reason is mandatory -- it is the only record of why. */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ fulfillmentId: string }> },
) {
  const { fulfillmentId } = await params;
  return proxyJson("user", `/fulfillments/${fulfillmentId}/close`, req, "POST");
}