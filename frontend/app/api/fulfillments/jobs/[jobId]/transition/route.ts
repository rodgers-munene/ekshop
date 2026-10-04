import { proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";
import type { NextResponse } from "next/server";

/**
 * Advance a job the calling rider is working.
 *
 * The backend owns the transition table and rejects anything illegal with a 409
 * and a message naming what was allowed, so that detail is passed through
 * untouched -- "cannot go back to picked_up" is actionable in a way that "request
 * failed" is not.
 *
 * `validate_otp` with `otp` marks a delivery complete against the customer's
 * code, which is how the rider's confirmation is actually verified.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> },
): Promise<NextResponse> {
  const { jobId } = await params;
  return proxyJson("agent", `/fulfillments/jobs/${jobId}/transition`, req, "POST");
}