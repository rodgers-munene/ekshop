import { cookies } from "next/headers";
import { NextResponse, NextRequest } from "next/server";
import { withCsrf } from "@/lib/admin-csrf";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function handler(_req: NextRequest, { params }: { params: Promise<{ userId: string }> }) {
  const { userId } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const res = await fetch(`${BASE_URL}/admin/users/${userId}/reactivate`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

export const PATCH = withCsrf(handler);