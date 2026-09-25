import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const lat = searchParams.get("lat");
  const lng = searchParams.get("lng");
  const radiusKm = searchParams.get("radius_km") ?? "20";

  if (!lat || !lng) {
    return NextResponse.json({ detail: "lat and lng are required" }, { status: 400 });
  }

  const res = await fetch(
    `${BASE_URL}/shops/nearby?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}&radius_km=${encodeURIComponent(radiusKm)}`
  );
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
