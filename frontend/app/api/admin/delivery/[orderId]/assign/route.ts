import { cookies } from "next/headers";
import { NextResponse, NextRequest } from "next/server";
import { withCsrf } from "@/lib/admin-csrf";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function handler(req: NextRequest, { params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { agent_id } = await req.json();
  const res = await fetch(
    `${BASE_URL}/delivery/${orderId}/assign?agent_id=${encodeURIComponent(agent_id)}`,
    { method: "POST", headers: { Authorization: `Bearer ${token}` } }
  );
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

export const POST = withCsrf(handler);