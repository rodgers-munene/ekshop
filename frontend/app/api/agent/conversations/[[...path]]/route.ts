import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

// Delivery agents sign in with their own cookie, so their messaging goes
// through here rather than /api/conversations (which forwards ekshop_token).
async function forward(req: NextRequest, params: Promise<{ path?: string[] }>) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_agent_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const { path = [] } = await params;
  const suffix = path.map(encodeURIComponent).join("/");
  const body = req.method === "GET" ? undefined : await req.text();

  const res = await fetch(`${BASE_URL}/conversations${suffix ? `/${suffix}` : ""}`, {
    method: req.method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body || undefined,
    cache: "no-store",
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

type Ctx = { params: Promise<{ path?: string[] }> };

export async function GET(req: NextRequest, { params }: Ctx) {
  return forward(req, params);
}

export async function POST(req: NextRequest, { params }: Ctx) {
  return forward(req, params);
}

export async function PATCH(req: NextRequest, { params }: Ctx) {
  return forward(req, params);
}
