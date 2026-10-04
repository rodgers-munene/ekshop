import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function bearer() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return null;
  return `Bearer ${token}`;
}

/** Create a fulfillment for an order, or list the caller's fulfillments. */
export async function GET(req: NextRequest) {
  const auth = await bearer();
  if (!auth) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  // Forward the merchant's filters rather than inventing a second set here, so
  // the backend stays the single authority on what a seller may see.
  const search = new URL(req.url).search;
  const res = await fetch(`${BASE_URL}/fulfillments${search}`, {
    headers: { Authorization: auth },
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
  const auth = await bearer();
  if (!auth) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const body = await req.json();
  const res = await fetch(`${BASE_URL}/fulfillments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: auth },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}