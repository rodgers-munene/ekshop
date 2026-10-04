import { proxy, proxyJson } from "@/lib/bff";
import type { NextRequest } from "next/server";
import type { NextResponse } from "next/server";

/**
 * Read or change one pricing parameter (§15).
 *
 * The backend validates the new value before saving it, so a typo is rejected
 * here rather than becoming a mysterious pricing failure later. It also refuses
 * an unrecognised key, so a misspelling cannot create a parameter the engine
 * silently ignores.
 */
export async function GET(
  _: Request,
  { params }: { params: Promise<{ key: string }> },
): Promise<NextResponse> {
  const { key } = await params;
  return proxy("user", `/pricing/parameters/${key}/history`);
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ key: string }> },
): Promise<NextResponse> {
  const { key } = await params;
  return proxyJson("user", `/pricing/parameters/${key}`, req, "PATCH");
}