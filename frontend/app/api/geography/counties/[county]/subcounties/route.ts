import { NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function GET(_req: Request, { params }: { params: Promise<{ county: string }> }) {
  const { county } = await params;
  const res = await fetch(`${BASE_URL}/geography/counties/${encodeURIComponent(county)}/subcounties`, {
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
