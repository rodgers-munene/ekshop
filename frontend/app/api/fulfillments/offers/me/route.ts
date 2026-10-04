import { cookies } from "next/headers";
import { proxy } from "@/lib/bff";
import type { NextResponse } from "next/server";

/** The calling rider's offers. Rider token only -- a merchant token gets 401. */
export async function GET(req: Request): Promise<NextResponse> {
  const search = new URL(req.url).search;
  return proxy("agent", `/fulfillments/offers/me`, { search });
}