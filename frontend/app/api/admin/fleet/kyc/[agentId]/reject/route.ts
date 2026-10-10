import { cookies } from "next/headers";
import { NextResponse, NextRequest } from "next/server";
import { withCsrf } from "@/lib/admin-csrf";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function handler(req: NextRequest, { params }: { params: Promise<{ agentId: string }> }) {
  const { agentId } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const body = await req.json();
  const res = await fetch(`${BASE_URL}/delivery/admin/kyc/${agentId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

export const POST = withCsrf(handler);