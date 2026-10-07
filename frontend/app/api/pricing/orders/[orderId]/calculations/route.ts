import { proxy } from "@/lib/bff";
import type { NextResponse } from "next/server";

/**
 * The17 audit trail for one order: every calculation made, newest first.
 *
 * Read-only by construction -- there is no update or delete route, and the table
 * has an append-only trigger behind it as well.
 */
export async function GET(
  _: Request,
  { params }: { params: Promise<{ orderId: string }> },
): Promise<NextResponse> {
  const { orderId } = await params;
  return proxy("user", `/pricing/orders/${orderId}/calculations`);
}