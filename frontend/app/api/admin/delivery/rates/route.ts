import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  // This handler runs on the frontend host, so a failure here reaches neither
  // the backend's logs (the request may never arrive) nor the browser console.
  // Name the cause in the response instead of collapsing it to {}.
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/delivery/rates`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch (err) {
    console.error("[delivery/rates] could not reach the API", BASE_URL, err);
    return NextResponse.json(
      { detail: `Could not reach the API at ${BASE_URL ?? "(NEXT_PUBLIC_API_URL is not set)"}.` },
      { status: 502 },
    );
  }

  const text = await res.text();
  try {
    return NextResponse.json(JSON.parse(text), { status: res.status });
  } catch {
    console.error("[delivery/rates] non-JSON reply", res.status, res.url, text.slice(0, 300));
    return NextResponse.json(
      { detail: `The API answered HTTP ${res.status} from ${res.url} with a non-JSON body.` },
      { status: 502 },
    );
  }
}

export async function PUT(req: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get("ekshop_token")?.value;
  if (!token) return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });

  const body = await req.json();
  const res = await fetch(`${BASE_URL}/delivery/rates`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
