import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { action, email, password } = body;

  if (action === "logout") {
    const cookieStore = await cookies();
    cookieStore.delete("ekshop_agent_token");
    return NextResponse.json({ ok: true });
  }

  const loginRes = await fetch(`${BASE_URL}/delivery/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!loginRes.ok) {
    const error = await loginRes.json().catch(() => ({}));
    return NextResponse.json(
      { detail: error.detail ?? "Invalid credentials" },
      { status: loginRes.status }
    );
  }

  const { access_token } = await loginRes.json();

  const profileRes = await fetch(`${BASE_URL}/delivery/agents/me`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });

  if (!profileRes.ok) {
    return NextResponse.json({ detail: "Failed to load profile" }, { status: 500 });
  }

  const agent = await profileRes.json();

  const cookieStore = await cookies();
  cookieStore.set("ekshop_agent_token", access_token, {
    httpOnly: true,
    sameSite: "strict",
    path: "/",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 12, // 12 hours, matches backend token expiry
  });

  return NextResponse.json({ agent });
}
