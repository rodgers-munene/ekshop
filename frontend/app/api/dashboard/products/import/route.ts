import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  // Forwarded as-is, and deliberately without a Content-Type header: fetch
  // derives the multipart boundary from the FormData, and setting the header by
  // hand sends the old boundary with the new body, which FastAPI reads as an
  // empty form.
  const formData = await req.formData();
  const categoryId = req.nextUrl.searchParams.get("category_id");
  const query = categoryId ? `?category_id=${encodeURIComponent(categoryId)}` : "";

  const res = await fetch(`${BASE_URL}/product-imports${query}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  // Same reason as the image upload route: nginx's 413 on an oversized
  // spreadsheet is HTML, so there is no `detail` to pass on.
  const body = await res.text();
  try {
    return NextResponse.json(JSON.parse(body), { status: res.status });
  } catch {
    const detail =
      res.status === 413
        ? "That spreadsheet is too large to upload."
        : `Upload failed (${res.status}).`;
    return NextResponse.json({ detail }, { status: res.status });
  }
}

export async function GET(req: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const search = req.nextUrl.search;
  const res = await fetch(`${BASE_URL}/product-imports${search}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
