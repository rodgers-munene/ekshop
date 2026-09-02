import { NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function GET(_req: Request, { params }: { params: Promise<{ subcountyId: string }> }) {
  const { subcountyId } = await params;
  const res = await fetch(`${BASE_URL}/geography/subcounties/${subcountyId}/wards`, {
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
