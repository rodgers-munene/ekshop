import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

/** Forward a presence heartbeat. Returns 204 with no body -- the client sends this
 *  every twenty seconds and should not be parsing anything. */
export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const token =
    cookieStore.get("ekshop_token")?.value ??
    cookieStore.get("ekshop_agent_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  await fetch(`${BASE_URL}/presence/heartbeat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    // Presence is worthless if it is cached: a cached heartbeat reports a user as
    // present after they have gone.
    cache: "no-store",
  }).catch(() => {
    // A failed heartbeat must never surface to the user. Presence is a metric,
    // not something anyone is doing.
  });

  return new NextResponse(null, { status: 204 });
}