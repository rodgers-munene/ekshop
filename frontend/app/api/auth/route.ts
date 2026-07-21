import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { action, email, password } = body;

  // logout
  if (action === "logout") {
    const cookieStore = await cookies();
    cookieStore.delete("ekshop_token");
    cookieStore.delete("ekshop_refresh");
    return NextResponse.json({ ok: true });
  }

  // register
  if (action === "register") {
    const { first_name, last_name, phone, county, role } = body;
    const registerRes = await fetch(`${BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, first_name, last_name, phone, county, role }),
    });
    if (!registerRes.ok) {
      const error = await registerRes.json().catch(() => ({}));
      return NextResponse.json({ detail: error.detail ?? "Registration failed" }, { status: registerRes.status });
    }
    // auto-login after register
  }

  // login
  const fastapiRes = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!fastapiRes.ok) {
    const error = await fastapiRes.json().catch(() => ({}));
    return NextResponse.json(
      { detail: error.detail ?? "Invalid credentials" },
      { status: fastapiRes.status }
    );
  }

  const { access_token, refresh_token } = await fastapiRes.json();

  // Fetch full user profile using the new token
  const profileRes = await fetch(`${BASE_URL}/users/me`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });

  if (!profileRes.ok) {
    return NextResponse.json(
      { detail: "Failed to load profile" },
      { status: 500 }
    );
  }

  const user = await profileRes.json();

  const cookieStore = await cookies();
  const cookieOpts = {
    httpOnly: true,
    sameSite: "strict" as const,
    path: "/",
    secure: process.env.NODE_ENV === "production",
  };

  cookieStore.set("ekshop_token", access_token, {
    ...cookieOpts,
    maxAge: 60 * 60 * 24 * 7,  // 7 days
  });

  cookieStore.set("ekshop_refresh", refresh_token, {
    ...cookieOpts,
    maxAge: 60 * 60 * 24 * 30, // 30 days
  });

  return NextResponse.json({ user });
}
