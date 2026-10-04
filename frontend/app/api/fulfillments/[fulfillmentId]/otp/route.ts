import { proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";
import type { NextResponse } from "next/server";

/**
 * Mint a delivery code for the current attempt.
 *
 * Only the hash is stored, so the plaintext in this response is the one and only
 * time the code is readable. It exists because there is no SMS or WhatsApp
 * integration yet (questionnaire Q11 is unanswered): the code has to reach the
 * customer some other way for now.
 *
 * Deliberately not reachable with a rider token -- the backend refuses that with
 * an explanation. A rider who can read the code can mark a delivery complete
 * without the customer, which defeats the point of having one.
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ fulfillmentId: string }> },
): Promise<NextResponse> {
  const { fulfillmentId } = await params;
  return proxyJson("user", `/fulfillments/${fulfillmentId}/otp`, req, "POST");
}