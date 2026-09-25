import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function GET(req: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const url = new URL(req.url);
  const period = url.searchParams.get("period") || "month";
  const res = await fetch(`${BASE_URL}/admin/reports/margin-leakage.pdf?period=${period}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const blob = await res.blob();
  return new NextResponse(blob, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("content-type") || "application/pdf",
      "Content-Disposition": `attachment; filename=margin-leakage-${period}.pdf`,
    },
  });
}
