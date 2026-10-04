import { proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";
import type { NextResponse } from "next/server";

/**
 * Ops override. Admin-only on the backend, which returns 403 for anyone else.
 *
 * A reason is mandatory and is recorded on the job, so an override is never
 * silent.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> },
): Promise<NextResponse> {
  const { jobId } = await params;
  return proxyJson("user", `/fulfillments/jobs/${jobId}/override`, req, "POST");
}