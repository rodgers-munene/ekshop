import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const res = await fetch(`${BASE_URL}/orders/${orderId}/cancel`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}` },
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
