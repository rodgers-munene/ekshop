import { proxy, proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";
import type { NextResponse } from "next/server";

/**
 * Settlement for a fulfillment: record the money for the current attempt, then
 * roll every attempt up onto the fulfillment.
 *
 * A failed attempt still costs a rider payout and a payment fee, so it can be
 * settled too, and it rolls up with the rest. Recording money also moves the job
 * to `settled` on the backend.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ fulfillmentId: string }> },
): Promise<NextResponse> {
  const { fulfillmentId } = await params;
  return proxyJson("user", `/fulfillments/${fulfillmentId}/settlement`, req, "POST");
}

/** The roll-up, or null when the fulfillment has not been settled yet. */
export async function GET(
  _: Request,
  { params }: { params: Promise<{ fulfillmentId: string }> },
): Promise<NextResponse> {
  const { fulfillmentId } = await params;
  return proxy("user", `/fulfillments/${fulfillmentId}/settlement`);
}