import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function authHeader() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return null;
  return `Bearer ${token}`;
}

/**
 * A single fulfillment, with every job, event and offer attached.
 *
 * The backend returns 404 rather than 403 for another merchant's fulfillment,
 * because a 403 would confirm the id exists and leak order volume. That status is
 * passed through unchanged.
 */
export async function GET(
  _: Request,
  { params }: { params: Promise<{ fulfillmentId: string }> },
) {
  const auth = await authHeader();
  if (!auth) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { fulfillmentId } = await params;
  const res = await fetch(`${BASE_URL}/fulfillments/${fulfillmentId}`, {
    headers: { Authorization: auth },
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}