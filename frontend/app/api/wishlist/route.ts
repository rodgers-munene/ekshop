import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function getToken() {
  const cookieStore = await cookies();
  return cookieStore.get("ekshop_token")?.value;
}

export async function GET() {
  const token = await getToken();
  if (!token) return NextResponse.json([], { status: 200 });

  const res = await fetch(`${BASE_URL}/users/me/wishlist`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json().catch(() => []);
  return NextResponse.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
  const token = await getToken();
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { product_id } = await req.json();
  const res = await fetch(`${BASE_URL}/users/me/wishlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ product_id }),
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
