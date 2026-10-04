import { proxy, proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";
import type { NextResponse } from "next/server";

/**
 * Quote a delivery (§16).
 *
 * The backend's error text is passed through deliberately: it distinguishes
 * "price exceeds the KES 500 ceiling" and "over 20 kg, needs a manual quote"
 * from a genuine failure, and those need different responses from whoever asked.
 */
export async function POST(req: NextRequest): Promise<NextResponse> {
  return proxyJson("user", "/pricing/quote", req, "POST");
}

/** Every configurable pricing parameter, with the count of placeholders (§15). */
export async function GET(): Promise<NextResponse> {
  return proxy("user", "/pricing/parameters");
}