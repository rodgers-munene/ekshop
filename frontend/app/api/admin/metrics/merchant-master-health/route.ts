import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function getToken() {
  const cookieStore = await cookies();
  return cookieStore.get("ekshop_token")?.value;
}

export async function GET(req: Request) {
  const token = await getToken();
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const url = new URL(req.url);
  const qs = url.search;

  const res = await fetch(`${BASE_URL}/admin/metrics/merchant-master-health${qs}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
