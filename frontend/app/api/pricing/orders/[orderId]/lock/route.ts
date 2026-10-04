import { proxy } from "@/lib/bff";
import type { NextResponse } from "next/server";

/**
 * Confirm and lock the delivery price at checkout (§14).
 *
 * After this the price cannot change because assignment was slow, the rider moved
 * further away, or supply changed. The backend measures real road distance here
 * rather than accepting one from the client, because a client-supplied distance is
 * exactly how an undercharge gets in.
 */
export async function POST(
  _: Request,
  { params }: { params: Promise<{ orderId: string }> },
): Promise<NextResponse> {
  const { orderId } = await params;
  return proxy("user", `/pricing/orders/${orderId}/lock`, { method: "POST" });
}