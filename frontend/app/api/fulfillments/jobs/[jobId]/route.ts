import { proxy } from "@/lib/bff";
import type { NextResponse } from "next/server";

/**
 * A job the calling rider owns.
 *
 * Uses the rider token, and the backend returns 404 for a job that is not this
 * rider's -- including one they have been offered but not yet accepted. A rider
 * cannot read a job before they claim it.
 */
export async function GET(
  _: Request,
  { params }: { params: Promise<{ jobId: string }> },
): Promise<NextResponse> {
  const { jobId } = await params;
  return proxy("agent", `/fulfillments/jobs/${jobId}`);
}