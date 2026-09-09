import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function POST(req: NextRequest, { params }: { params: Promise<{ productKey: string }> }) {
  const { productKey } = await params;
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const formData = await req.formData();
  const res = await fetch(`${BASE_URL}/products/${productKey}/images`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  // Rejections from the reverse proxy in front of the API (nginx's 413 when an
  // upload exceeds client_max_body_size, its 502/504 when the app is down) come
  // back as HTML, so there is no `detail` to forward. Synthesise one, otherwise
  // the client can only report a bare status code.
  const body = await res.text();
  try {
    return NextResponse.json(JSON.parse(body), { status: res.status });
  } catch {
    if (res.ok) return NextResponse.json({}, { status: res.status });
    const detail =
      res.status === 413
        ? "Image is too large to upload. Please use a smaller file."
        : `Upload failed (${res.status}).`;
    return NextResponse.json({ detail }, { status: res.status });
  }
}
