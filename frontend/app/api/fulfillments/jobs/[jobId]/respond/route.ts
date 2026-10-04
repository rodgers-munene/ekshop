import { proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";
import type { NextResponse } from "next/server";

/**
 * Accept or decline an offer.
 *
 * Accepting claims the job: the backend sets the rider on it and withdraws the
 * other live offers, so after this the job shows up in the rider's own list.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> },
): Promise<NextResponse> {
  const { jobId } = await params;
  return proxyJson("agent", `/fulfillments/jobs/${jobId}/respond`, req, "POST");
}