import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

async function getToken() {
  const cookieStore = await cookies();
  return cookieStore.get("ekshop_agent_token")?.value;
}

/**
 * Upload one identity document.
 *
 * FormData is forwarded as-is so the browser sets the multipart boundary.
 * Re-serialising it would drop the boundary and the backend would see a
 * malformed body.
 */
export async function POST(req: NextRequest) {
  const token = await getToken();
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const form = await req.formData();
  const kind = form.get("kind") ?? "document";
  const file = form.get("file");

  if (!(file instanceof File)) {
    return NextResponse.json(
      { detail: "No file was sent. Choose a photo or PDF of the document." },
      { status: 400 },
    );
  }

  const outbound = new FormData();
  outbound.append("file", file, file.name);
  outbound.append("kind", String(kind));

  const res = await fetch(
    `${BASE_URL}/delivery/kyc/me/upload?kind=${encodeURIComponent(String(kind))}`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: outbound,
      cache: "no-store",
    },
  );

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}