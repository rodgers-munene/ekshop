import { cookies } from "next/headers";
import { NextResponse, NextRequest } from "next/server";
import { withCsrf } from "@/lib/admin-csrf";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function patchHandler(req: NextRequest, { params }: { params: Promise<{ slideId: string }> }) {
  const { slideId } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const body = await req.json();
  const res = await fetch(`${BASE_URL}/admin/hero-slides/${slideId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

async function deleteHandler(_req: NextRequest, { params }: { params: Promise<{ slideId: string }> }) {
  const { slideId } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const res = await fetch(`${BASE_URL}/admin/hero-slides/${slideId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

export const PATCH = withCsrf(patchHandler);
export const DELETE = withCsrf(deleteHandler);