import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function auth() {
  const cookieStore = await cookies();
  return cookieStore.get("ekshop_token")?.value;
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ importId: string }> }) {
  const { importId } = await params;
  const token = await auth();
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const res = await fetch(`${BASE_URL}/product-imports/${importId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(_req: NextRequest, { params }: { params: Promise<{ importId: string }> }) {
  const { importId } = await params;
  const token = await auth();
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const res = await fetch(`${BASE_URL}/product-imports/${importId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  // 204 carries no body, and NextResponse.json(null) would make one.
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
